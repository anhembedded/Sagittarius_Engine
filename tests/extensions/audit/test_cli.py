"""`sagittarius-trace attach` (`EPIC-005D` requirements 1 and 2)."""

from __future__ import annotations

import io
import json
import signal
import threading
import time

import pytest

pytest.importorskip("websockets")

import websockets.sync.server  # noqa: E402

from sagittarius_engine.extensions.audit.cli import (  # noqa: E402
    _format_snapshot,
    _parse_duration,
    attach,
    build_parser,
    main,
    snapshot,
)
from sagittarius_engine.extensions.audit.contracts import (  # noqa: E402
    PROTOCOL_VERSION,
    DeadLetterEntry,
    Lane,
    LifecycleState,
    SignalsState,
    StateMachineState,
    StateMachineTransition,
    StateSnapshot,
    UiThreadHealth,
)
from sagittarius_engine.extensions.audit.infra.trace_server import (  # noqa: E402
    TraceServer,
)
from sagittarius_engine.extensions.audit.recorder import TraceRecorder  # noqa: E402
from sagittarius_engine.extensions.audit.sagtrace import load_sagtrace  # noqa: E402

READY_TIMEOUT_SECONDS = 2.0
JOIN_TIMEOUT_SECONDS = 2.0


@pytest.fixture
def recorder():
    return TraceRecorder(capacity=1000)


@pytest.fixture
def running_server(recorder):
    server = TraceServer(recorder, host="127.0.0.1", port=0)
    server.start()
    assert server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    yield server
    server.stop()


def _wait_until(predicate, timeout=READY_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def snapshot_calls():
    return []


@pytest.fixture
def running_snapshot_server(recorder, snapshot_calls):
    def provider() -> StateSnapshot:
        snapshot_calls.append(1)
        return StateSnapshot(
            t=len(snapshot_calls),
            lifecycle=LifecycleState(
                state="ready", extensions_registered=1, extensions_initialized=1
            ),
        )

    server = TraceServer(recorder, host="127.0.0.1", port=0, snapshot_provider=provider)
    server.start()
    assert server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    yield server
    server.stop()


# ------------------------------------------------------------- requirement 1


def test_attach_streams_the_live_event_log_as_text(recorder, running_server):
    uri = f"ws://{running_server.host}:{running_server.port}"
    out = io.StringIO()
    result: dict = {}

    def run():
        result["code"] = attach(uri, save_path=None, out=out)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: len(running_server._clients) >= 1)  # noqa: SLF001
        recorder.instant(Lane.USER, "order-filled", args={"price": 101.5})
        assert _wait_until(lambda: "order-filled" in out.getvalue())
    finally:
        running_server.stop()
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert not thread.is_alive()
    assert result["code"] == 0
    text = out.getvalue()
    assert "attached to" in text
    assert "order-filled" in text
    assert "detached" in text


def test_attaching_late_prints_the_backlog(recorder):
    recorder.instant(Lane.USER, "already-happened")
    server = TraceServer(recorder, host="127.0.0.1", port=0)
    server.start()
    assert server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    uri = f"ws://{server.host}:{server.port}"
    out = io.StringIO()
    result: dict = {}

    def run():
        result["code"] = attach(uri, save_path=None, out=out)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: "already-happened" in out.getvalue())
    finally:
        server.stop()
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert result["code"] == 0


# ------------------------------------------------------------------ --save


def test_save_writes_a_sagtrace_file_with_everything_seen(
    recorder, running_server, tmp_path
):
    save_path = tmp_path / "session.sagtrace"
    uri = f"ws://{running_server.host}:{running_server.port}"
    out = io.StringIO()
    result: dict = {}

    def run():
        result["code"] = attach(uri, save_path=str(save_path), out=out)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: len(running_server._clients) >= 1)  # noqa: SLF001
        recorder.instant(Lane.USER, "saved-me")
        assert _wait_until(lambda: "saved-me" in out.getvalue())
    finally:
        running_server.stop()
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert result["code"] == 0
    assert save_path.exists()
    hello, records = load_sagtrace(save_path)
    assert hello.capacity == recorder.capacity
    assert [r.name for r in records] == ["saved-me"]


def test_without_save_no_file_is_written(recorder, running_server, tmp_path):
    save_path = tmp_path / "should-not-exist.sagtrace"
    uri = f"ws://{running_server.host}:{running_server.port}"
    thread = threading.Thread(
        target=attach, args=(uri,), kwargs={"save_path": None, "out": io.StringIO()}
    )
    thread.start()
    try:
        assert _wait_until(lambda: len(running_server._clients) >= 1)  # noqa: SLF001
    finally:
        running_server.stop()
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert not save_path.exists()


# ------------------------------------------------------------- requirement 2


def test_a_protocol_mismatch_at_connect_fails_loudly_not_as_a_blank_stream():
    """The literal wording of requirement 2: a version mismatch is refused at
    connect, with a clear message and a non-zero exit — never a connection
    that just sits there printing nothing."""

    def handler(websocket) -> None:
        websocket.send(json.dumps({"v": 999, "type": "hello", "seq": 0, "data": {}}))

    with websockets.sync.server.serve(handler, "127.0.0.1", 0) as server:
        host, port = server.socket.getsockname()[:2]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            out = io.StringIO()
            code = attach(f"ws://{host}:{port}", save_path=None, out=out)
        finally:
            server.shutdown()
            thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert code == 2
    assert "attached to" not in out.getvalue()


def test_a_peer_that_does_not_speak_hello_first_is_refused():
    def handler(websocket) -> None:
        # PROTOCOL_VERSION, not a literal 1. Hardcoding the version meant that
        # the moment v2 landed this peer was *also* a version mismatch, so the
        # refusal this test asserts would have come from `check_protocol()`
        # rather than from the missing `hello` the test is named for — passing
        # for the wrong reason, which is a detector turned into a rubber stamp.
        websocket.send(
            json.dumps({"v": PROTOCOL_VERSION, "type": "trace", "seq": 0, "data": []})
        )

    with websockets.sync.server.serve(handler, "127.0.0.1", 0) as server:
        host, port = server.socket.getsockname()[:2]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            out = io.StringIO()
            code = attach(f"ws://{host}:{port}", save_path=None, out=out)
        finally:
            server.shutdown()
            thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert code == 2


def test_connecting_to_nothing_is_a_usage_error():
    out = io.StringIO()
    code = attach("ws://127.0.0.1:1", save_path=None, out=out)
    assert code == 2


# ------------------------------------------------------ EPIC-007F rendering


def test_format_snapshot_omits_the_signals_section_when_absent():
    text = _format_snapshot(StateSnapshot())
    assert "dead letters" not in text
    assert "state machines" not in text
    assert "ui thread" not in text


def test_format_snapshot_renders_a_dead_letter():
    snapshot_obj = StateSnapshot(
        signals=SignalsState(
            dead_letters=(
                DeadLetterEntry(
                    event_name="demo.student_deleted",
                    handler="handlers._always_raises",
                    exception_type="KeyError",
                    exception_message="demo: enrolment record missing",
                    retries=1,
                ),
            )
        )
    )
    text = _format_snapshot(snapshot_obj)
    assert "dead letters: 1" in text
    assert "demo.student_deleted: KeyError: demo: enrolment record missing" in text
    assert "retries=1" in text


def test_format_snapshot_renders_a_rejected_transition_flagged():
    snapshot_obj = StateSnapshot(
        signals=SignalsState(
            state_machines=(
                StateMachineState(
                    name="EnrolmentFlow",
                    current_state="ENROLLED",
                    rejected_count=1,
                    transitions=(
                        StateMachineTransition(
                            from_state="DRAFT", to_state="SUBMITTED"
                        ),
                        StateMachineTransition(
                            from_state="ENROLLED", to_state="SUBMITTED", rejected=True
                        ),
                    ),
                ),
            )
        )
    )
    text = _format_snapshot(snapshot_obj)
    assert "state machines: 1" in text
    assert "EnrolmentFlow: state=ENROLLED rejected=1" in text
    assert "DRAFT -> SUBMITTED" in text
    assert "ENROLLED -> SUBMITTED [REJECTED]" in text
    # the accepted transition must NOT carry the flag
    accepted_line = next(
        line for line in text.splitlines() if "DRAFT -> SUBMITTED" in line
    )
    assert "[REJECTED]" not in accepted_line


def test_format_snapshot_renders_ui_thread_health_only_when_present():
    without = _format_snapshot(StateSnapshot(signals=SignalsState()))
    assert "ui thread" not in without

    with_health = _format_snapshot(
        StateSnapshot(
            signals=SignalsState(
                ui_thread=UiThreadHealth(
                    freeze_count=2, worst_freeze_ms=5200.0, off_thread_mutation_count=3
                )
            )
        )
    )
    assert "ui thread: freezes=2 (worst=5200ms), off_thread_mutations=3" in with_health


# ---------------------------------------------------------------- snapshot


def test_snapshot_prints_a_live_applications_state(running_snapshot_server):
    """`EPIC-007C` criterion 2: `sagittarius-trace snapshot` prints a live
    application's state in a terminal."""
    uri = f"ws://{running_snapshot_server.host}:{running_snapshot_server.port}"
    out = io.StringIO()

    code = snapshot(uri, None, out=out)

    assert code == 0
    text = out.getvalue()
    assert "lifecycle: state=ready extensions=1/1" in text
    assert "detached" in text


def test_watch_requests_exactly_one_snapshot_per_tick(
    running_snapshot_server, snapshot_calls
):
    """`EPIC-007C` criterion 3: `--watch` re-reads on the interval and does
    not re-collect between them — proven here by the count of printed
    snapshots matching the count of provider calls exactly, not some
    multiple of it."""
    uri = f"ws://{running_snapshot_server.host}:{running_snapshot_server.port}"
    out = io.StringIO()
    result: dict = {}

    def run():
        result["code"] = snapshot(uri, 0.05, out=out)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    try:
        assert _wait_until(lambda: len(snapshot_calls) >= 3)
    finally:
        running_snapshot_server.stop()
        thread.join(timeout=JOIN_TIMEOUT_SECONDS)

    assert not thread.is_alive()
    assert out.getvalue().count("snapshot @") == len(snapshot_calls)


def test_snapshot_connecting_to_nothing_is_a_usage_error():
    out = io.StringIO()
    code = snapshot("ws://127.0.0.1:1", None, out=out)
    assert code == 2


@pytest.mark.parametrize(
    ("text", "expected"), [("1s", 1.0), ("500ms", 0.5), ("2", 2.0), ("0.25s", 0.25)]
)
def test_parse_duration(text, expected):
    assert _parse_duration(text) == expected


def test_parse_duration_rejects_garbage():
    with pytest.raises(ValueError):
        _parse_duration("banana")


# -------------------------------------------------------------------- argparse


def test_build_parser_requires_a_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_build_parser_accepts_attach_with_save():
    args = build_parser().parse_args(
        ["attach", "ws://host:1234", "--save", "out.sagtrace"]
    )
    assert args.command == "attach"
    assert args.uri == "ws://host:1234"
    assert args.save == "out.sagtrace"


def test_build_parser_accepts_snapshot_with_watch():
    args = build_parser().parse_args(["snapshot", "ws://host:1234", "--watch", "1s"])
    assert args.command == "snapshot"
    assert args.uri == "ws://host:1234"
    assert args.watch == "1s"


def test_build_parser_accepts_snapshot_without_watch():
    args = build_parser().parse_args(["snapshot", "ws://host:1234"])
    assert args.watch is None


def test_main_rejects_an_unparseable_watch_duration():
    previous = signal.getsignal(signal.SIGTERM)
    try:
        out_code = main(["snapshot", "ws://127.0.0.1:1", "--watch", "banana"])
        assert out_code == 2
    finally:
        signal.signal(signal.SIGTERM, previous)


# --------------------------------------------------------------------- SIGTERM


def test_main_installs_a_sigterm_handler_so_save_still_runs(monkeypatch):
    """Found by running the acceptance case under `timeout`, which sends
    SIGTERM: Python's default terminates without unwinding, so `--save` never
    ran and the file was silently absent. A container stop, a systemd unit and
    a supervisor all send SIGTERM, so that is most of the ways this command
    will actually be ended."""
    previous = signal.getsignal(signal.SIGTERM)
    monkeypatch.setattr(
        "sagittarius_engine.extensions.audit.cli.attach",
        lambda *a, **k: 0,
    )
    try:
        assert main(["attach", "ws://127.0.0.1:1"]) == 0
        installed = signal.getsignal(signal.SIGTERM)
        assert installed is not previous
        with pytest.raises(KeyboardInterrupt):
            installed(signal.SIGTERM, None)
    finally:
        signal.signal(signal.SIGTERM, previous)
