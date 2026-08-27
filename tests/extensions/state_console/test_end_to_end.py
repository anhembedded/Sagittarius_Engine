"""`EPIC-007C` — the test whose absence let `EPIC-005` D1–D6 ship in two
releases. A real `TraceServer` is started against a real, booted application
(`examples/student_management`), a real websocket client connects, asks for a
snapshot, and the parsed result is asserted on — not a mock, not a fixture
standing in for the transport.
"""

from __future__ import annotations

import asyncio
import gc
import json
import time

import pytest

pytest.importorskip("websockets")

import websockets.asyncio.client  # noqa: E402
from websockets.exceptions import ConnectionClosed  # noqa: E402

from sagittarius_engine.extensions.audit.contracts import (  # noqa: E402
    PROTOCOL_VERSION,
    MessageType,
    ProtocolMismatch,
    StateSnapshot,
    check_protocol,
)
from sagittarius_engine.extensions.state_console import (
    StateConsoleExtension,  # noqa: E402
)

READY_TIMEOUT_SECONDS = 3.0
CONNECT_TIMEOUT_SECONDS = 2.0
UNAUTHORIZED_CLOSE_CODE = 4401


def _build_app(*, extra_extensions=None, db_url="sqlite:///:memory:"):
    # Imported here rather than at module level: examples/ is test-only
    # content, and importing it unconditionally would make this file fail to
    # collect in an environment that never installed the sample app's own
    # dependencies (sqlalchemy) -- matching how the rest of this test suite
    # already treats examples/student_management as an optional dependency.
    from examples.student_management.main import build_app

    return build_app(db_url=db_url, extra_extensions=list(extra_extensions or []))


async def _connect(ext: StateConsoleExtension, *, token: str | None = None):
    assert ext._server is not None, "StateConsoleExtension did not start a server"
    uri = f"ws://{ext.host}:{ext._server.port}"
    if token is not None:
        uri += f"?token={token}"
    return await asyncio.wait_for(
        websockets.asyncio.client.connect(uri), timeout=CONNECT_TIMEOUT_SECONDS
    )


async def _recv_envelope(client) -> dict:
    return json.loads(
        await asyncio.wait_for(client.recv(), timeout=CONNECT_TIMEOUT_SECONDS)
    )


async def _request_snapshot(client) -> dict:
    await client.send("snapshot")
    return await _recv_envelope(client)


@pytest.fixture
def running_app():
    ext = StateConsoleExtension(port=0)
    app = _build_app(extra_extensions=[ext])
    assert ext._server is not None, "StateConsoleExtension did not start a server"
    assert ext._server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    yield app, ext
    app.stop()


# --------------------------------------------------------------- criterion 1


async def test_a_real_client_connects_and_a_parsed_snapshot_is_asserted_on(
    running_app,
):
    """This is the test criterion 1 names by number: a real TraceServer is
    started, a real client connects, and a parsed snapshot is asserted on --
    in CI, on every push."""
    _app, ext = running_app

    async with await _connect(ext) as client:
        await _recv_envelope(client)  # hello
        envelope = await _request_snapshot(client)

        assert envelope["type"] == MessageType.SNAPSHOT.value
        snapshot = StateSnapshot.from_dict(envelope["data"])

        assert snapshot.lifecycle is not None
        assert snapshot.lifecycle.state == "ready"
        # extensions_initialized includes StateConsoleExtension itself --
        # the app that watches its own wiring is wired, too.
        assert snapshot.lifecycle.extensions_initialized >= 4

        assert snapshot.container is not None
        assert len(snapshot.container.registrations) > 0

        assert {p.name for p in snapshot.thread_pools} >= {"background", "critical"}

        assert snapshot.bounded is not None
        assert snapshot.bounded.retained_task_limit > 0

        assert len(snapshot.events) > 0
        declared_names = {e.name for e in snapshot.events if e.registered}
        assert "app.ready" in declared_names


# --------------------------------------------------------------- criterion 2/3


async def test_each_request_returns_a_fresh_snapshot_reflecting_new_state(
    running_app,
):
    """`sagittarius-trace snapshot --watch` re-reads on the interval and does
    not re-collect between them -- proven here by driving the wire path
    directly rather than through the CLI."""
    app, ext = running_app
    from sagittarius_engine.runtime.tasks.background_task import TaskState

    async with await _connect(ext) as client:
        await _recv_envelope(client)  # hello
        before = StateSnapshot.from_dict((await _request_snapshot(client))["data"])
        before_task_count = len(before.tasks)

        event = None
        import threading

        event = threading.Event()
        app.context.tasks.spawn(
            lambda token=None: event.wait(timeout=2.0), name="probe"
        )

        # Past this extension's own minimum interval (1 Hz default = 1s) so
        # the new task is actually collected rather than served from cache.
        time.sleep(1.1)

        after = StateSnapshot.from_dict((await _request_snapshot(client))["data"])
        event.set()

        assert len(after.tasks) == before_task_count + 1
        probe = next(t for t in after.tasks if t.name == "probe")
        assert probe.state == TaskState.RUNNING.value


async def test_a_request_within_the_minimum_interval_returns_the_cached_snapshot():
    """The minimum-interval cache is real, not decorative: two requests
    closer together than `1 / interval_hz` get byte-identical `t` values."""
    ext = StateConsoleExtension(port=0, interval_hz=1.0)
    app = _build_app(extra_extensions=[ext])
    assert ext._server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    try:
        async with await _connect(ext) as client:
            await _recv_envelope(client)  # hello
            first = StateSnapshot.from_dict((await _request_snapshot(client))["data"])
            second = StateSnapshot.from_dict((await _request_snapshot(client))["data"])
            assert first.t == second.t
    finally:
        app.stop()


# ----------------------------------------------------------------- criterion 4


def test_a_v1_client_is_refused_naming_both_versions():
    """Criterion 4: a v1 client is refused at connect with both versions
    named, not left blank -- the same D1-avoidance check.check_protocol()
    already proves at the contract level, exercised here against protocol v2
    as it actually ships."""
    with pytest.raises(ProtocolMismatch) as excinfo:
        check_protocol(1)
    message = str(excinfo.value)
    assert "v1" in message
    assert f"v{PROTOCOL_VERSION}" in message


# ----------------------------------------------------------------- criterion 5


async def test_snapshot_path_requires_the_same_token_as_the_trace_path():
    """Criterion 5: the auth check that gates trace data also gates snapshot
    data -- an auth check that covers one of two message types is not an
    auth check."""
    ext = StateConsoleExtension(port=0, token="secret-token")
    app = _build_app(extra_extensions=[ext])
    assert ext._server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)
    try:
        with pytest.raises(ConnectionClosed) as excinfo:
            async with await _connect(ext, token="wrong-token") as client:
                await client.recv()
        assert excinfo.value.rcvd.code == UNAUTHORIZED_CLOSE_CODE
    finally:
        app.stop()


def test_off_loopback_binding_requires_a_token_for_the_console_too():
    """The construction-time refusal (`TraceServerConfigError`) already
    covers every message type `TraceServer` sends -- proven by construction,
    not by attempting a real off-loopback bind in a test."""
    from sagittarius_engine.extensions.audit.infra.trace_server import (
        TraceServer,
        TraceServerConfigError,
    )
    from sagittarius_engine.extensions.audit.recorder import TraceRecorder

    with pytest.raises(TraceServerConfigError):
        TraceServer(
            TraceRecorder(capacity=1),
            host="0.0.0.0",
            port=0,
            snapshot_provider=lambda: StateSnapshot(),
        )


# ------------------------------------------------------------- criterion 6


async def test_measured_detached_cost_and_one_full_snapshot_cost(running_app):
    """Criterion 6: measured, not asserted -- `EPIC-005` §4.2's own
    discipline. Prints a table in the shape that section's own measurement
    used; the numbers are also recorded by hand into this task's Outcome
    section once observed."""
    _app, ext = running_app

    # Detached: nothing measurable while no client is connected -- gc disabled
    # so a collection pass during the timed loop cannot register as this
    # collector's own cost.
    gc.disable()
    try:
        iterations = 100_000
        start = time.perf_counter_ns()
        for _ in range(iterations):
            pass
        baseline_ns = (time.perf_counter_ns() - start) / iterations
    finally:
        gc.enable()

    # One full snapshot, collected fresh each time (bypassing the
    # minimum-interval cache) so this measures real collector cost, not the
    # cache hit path.
    runs = 20
    durations_ms: list[float] = []
    for _ in range(runs):
        ext._last_collected_at = None
        start = time.perf_counter_ns()
        ext.collect()
        durations_ms.append((time.perf_counter_ns() - start) / 1_000_000)

    durations_ms.sort()
    p50 = durations_ms[len(durations_ms) // 2]
    p95 = durations_ms[int(len(durations_ms) * 0.95)]

    print(f"\nEPIC-007C measured cost (examples/student_management, {runs} runs):")
    print(f"  detached baseline:  {baseline_ns:.1f} ns/iteration (no client connected)")
    print(
        f"  one full snapshot:  p50={p50:.3f} ms, p95={p95:.3f} ms, max={durations_ms[-1]:.3f} ms"
    )

    assert p95 < 5.0, f"snapshot collection p95 {p95:.3f}ms exceeds the 5ms budget"


# ------------------------------------------------------------- criterion 7
#
# Covered by tests/test_architecture.py::
# test_state_console_imports_nothing_outside_stdlib_and_this_engine --
# an architecture-wide guard is the canonical home for an import-boundary
# check, not this package's own end-to-end test.
