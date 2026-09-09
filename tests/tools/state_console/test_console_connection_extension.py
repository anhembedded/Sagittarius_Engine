"""`ConsoleConnectionExtension` against a real `TraceServer` — `EPIC-007E`
criteria 10 and 11, extended by `EPIC-008B` (connecting/failed
classification, live re-target, no automatic retry). A real websocket
client connects, a real snapshot is received, and the task lifecycle is
asserted on, not observed once."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("websockets")

from sagittarius_engine.domain.event_registry import EventRegistry  # noqa: E402
from sagittarius_engine.extensions.state_console import (
    StateConsoleExtension,  # noqa: E402
)
from sagittarius_engine.infrastructure.container.std_container import (  # noqa: E402
    StdLibContainer,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import (  # noqa: E402
    MemoryEventBus,
)
from sagittarius_engine.kernel import App  # noqa: E402
from tools.state_console.domain.events import (  # noqa: E402
    ConsoleAttached,
    ConsoleConnecting,
    ConsoleDetached,
    ConsoleFailed,
    ConsoleFailureKind,
    SnapshotReceived,
)
from tools.state_console.infrastructure.console_connection_extension import (  # noqa: E402
    ConsoleConnectionExtension,
)

READY_TIMEOUT_SECONDS = 3.0
EVENT_TIMEOUT_SECONDS = 5.0
JOIN_TIMEOUT_SECONDS = 3.0


def _wait_until(predicate, timeout=EVENT_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def server_app():
    server_ext = StateConsoleExtension(port=0)
    app = App(StdLibContainer(), MemoryEventBus())
    app.use(server_ext)
    app.boot()
    assert server_ext._server is not None  # noqa: SLF001
    assert server_ext._server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)  # noqa: SLF001
    yield app, server_ext
    app.stop()


def _uri(server_ext) -> str:
    return f"ws://{server_ext.host}:{server_ext._server.port}"  # noqa: SLF001


def test_a_real_client_attaches_and_receives_a_snapshot(server_app):
    _server, server_ext = server_app
    events: list[tuple] = []

    client_ext = ConsoleConnectionExtension(_uri(server_ext))
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.event_bus.on(ConsoleAttached, lambda e: events.append(("attached",)))
    client_app.event_bus.on(
        SnapshotReceived, lambda e: events.append(("snapshot", e.snapshot))
    )
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert _wait_until(lambda: any(kind == "attached" for kind, *_ in events))
        assert _wait_until(lambda: any(kind == "snapshot" for kind, *_ in events))
    finally:
        client_app.stop()


def test_connecting_to_nothing_emits_console_failed_not_console_detached():
    """`EPIC-008B`: a connection that never attached is `ConsoleFailed`, not
    `ConsoleDetached` — the two now mean different things (see
    `ConsoleConnectionExtension`'s own docstring). Port 1 is a real,
    unassigned low port that reliably refuses on every platform this test
    suite runs on."""
    events: list[ConsoleFailed] = []
    client_ext = ConsoleConnectionExtension("ws://127.0.0.1:1")
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.event_bus.on(ConsoleFailed, events.append)
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert _wait_until(lambda: len(events) > 0)
        assert events[0].kind is ConsoleFailureKind.REFUSED
        assert events[0].code == "ECONNREFUSED"
        assert events[0].uri == "ws://127.0.0.1:1"
    finally:
        client_app.stop()


def test_connecting_to_nothing_does_not_retry_on_its_own():
    """`EPIC-008B`'s "no automatic retry" contract: one attempt, one
    `ConsoleFailed`, then silence — reconnecting is always a fresh
    `connect_to()` call, never a background timer."""
    events: list[ConsoleFailed] = []
    client_ext = ConsoleConnectionExtension("ws://127.0.0.1:1")
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.event_bus.on(ConsoleFailed, events.append)
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert _wait_until(lambda: len(events) > 0)
        # The old behaviour retried every 2s -- wait past that window and
        # confirm no second attempt happened on its own.
        time.sleep(2.5)
        assert len(events) == 1
    finally:
        client_app.stop()


def test_a_malformed_uri_emits_console_failed_with_kind_malformed():
    events: list[ConsoleFailed] = []
    client_ext = ConsoleConnectionExtension("not-a-valid-uri")
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.event_bus.on(ConsoleFailed, events.append)
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert _wait_until(lambda: len(events) > 0)
        assert events[0].kind is ConsoleFailureKind.MALFORMED
        assert events[0].code == "EINVAL"
    finally:
        client_app.stop()


def test_a_bad_token_emits_console_failed_with_kind_rejected(server_app):
    """A real `TraceServer` configured with a token, connected to without
    one — the real close-code-4401 path, not a simulated one."""
    from sagittarius_engine.extensions.audit.infra.trace_server import TraceServer
    from sagittarius_engine.extensions.audit.recorder import TraceRecorder

    _app, server_ext = server_app
    authed_server = TraceServer(
        TraceRecorder(capacity=100),
        host="127.0.0.1",
        port=0,
        token="right-token",
        snapshot_provider=server_ext.collect,
    )
    authed_server.start()
    try:
        assert authed_server.ready_event.wait(timeout=READY_TIMEOUT_SECONDS)

        events: list[ConsoleFailed] = []
        client_ext = ConsoleConnectionExtension(f"ws://127.0.0.1:{authed_server.port}")
        client_app = App(StdLibContainer(), MemoryEventBus())
        client_app.event_bus.on(ConsoleFailed, events.append)
        client_app.use(client_ext)
        client_app.boot()
        try:
            assert _wait_until(lambda: len(events) > 0)
            assert events[0].kind is ConsoleFailureKind.REJECTED
            assert events[0].code == "HTTP 401"
        finally:
            client_app.stop()
    finally:
        authed_server.stop()


def test_connecting_emits_console_connecting_before_the_result(server_app):
    _server, server_ext = server_app
    events: list[str] = []

    client_ext = ConsoleConnectionExtension(_uri(server_ext))
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.event_bus.on(ConsoleConnecting, lambda e: events.append("connecting"))
    client_app.event_bus.on(ConsoleAttached, lambda e: events.append("attached"))
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert _wait_until(lambda: events == ["connecting", "attached"])
    finally:
        client_app.stop()


def test_connect_to_switches_target_without_recreating_the_extension(server_app):
    """`EPIC-008B`'s live re-target requirement: attach from within the
    tool to a different address, without restarting."""
    _server, server_ext = server_app
    events: list[tuple] = []

    client_ext = ConsoleConnectionExtension()  # boots cold, no initial target
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.event_bus.on(
        ConsoleAttached, lambda e: events.append(("attached", client_ext.uri))
    )
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert client_app.context.tasks.get_active_tasks() == []

        client_ext.connect_to(_uri(server_ext))
        assert _wait_until(lambda: any(kind == "attached" for kind, *_ in events))
        assert events[-1][1] == _uri(server_ext)
    finally:
        client_app.stop()


def test_detach_stops_the_connection_and_emits_console_detached(server_app):
    _server, server_ext = server_app
    events: list[str] = []

    client_ext = ConsoleConnectionExtension(_uri(server_ext))
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.event_bus.on(ConsoleAttached, lambda e: events.append("attached"))
    client_app.event_bus.on(ConsoleDetached, lambda e: events.append("detached"))
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert _wait_until(lambda: "attached" in events)

        client_ext.detach()

        assert _wait_until(lambda: "detached" in events)
    finally:
        client_app.stop()


# ------------------------------------------------------------- criterion 10


def test_the_receive_loop_is_a_task_manager_task_visible_while_connected(server_app):
    _server, server_ext = server_app
    client_ext = ConsoleConnectionExtension(_uri(server_ext))
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert _wait_until(
            lambda: any(
                t.name == "ConsoleConnection"
                for t in client_app.context.tasks.get_active_tasks()
            )
        )
    finally:
        client_app.stop()


def test_stopping_the_app_leaves_nothing_running(server_app):
    _server, server_ext = server_app
    client_ext = ConsoleConnectionExtension(_uri(server_ext))
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.use(client_ext)
    client_app.boot()
    assert _wait_until(lambda: len(client_app.context.tasks.get_active_tasks()) > 0)

    client_app.stop()

    assert _wait_until(
        lambda: len(client_app.context.tasks.get_active_tasks()) == 0,
        timeout=JOIN_TIMEOUT_SECONDS,
    )


# ------------------------------------------------------------- criterion 11


def test_events_are_real_baseevent_subclasses_registered_in_event_registry():
    assert EventRegistry.get("SnapshotReceived") is not None
    assert EventRegistry.get("console.attached") is not None
    assert EventRegistry.get("console.detached") is not None
    assert EventRegistry.get("console.connecting") is not None
    assert EventRegistry.get("console.failed") is not None


def test_doctor_reports_zero_errors_against_the_consoles_own_build_app():
    """The same dogfooding check `EPIC-007D` §3 holds the sample app to."""
    from sagittarius_engine.extensions.diagnostics import WiringInspector

    app = App(StdLibContainer(), MemoryEventBus())
    app.use(ConsoleConnectionExtension("ws://127.0.0.1:1"))
    app.boot()
    try:
        report = WiringInspector().inspect(
            bus=app.context.event_bus, container=app.context.container
        )
        assert not report.errors, report.format()
    finally:
        app.stop()
