"""`ConsoleConnectionExtension` against a real `TraceServer` — `EPIC-007E`
criteria 10 and 11. A real websocket client connects, a real snapshot is
received, and the task lifecycle is asserted on, not observed once."""

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
    ConsoleDetached,
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


def test_connecting_to_nothing_emits_console_detached_not_an_exception():
    events: list[str] = []
    client_ext = ConsoleConnectionExtension("ws://127.0.0.1:1")
    client_app = App(StdLibContainer(), MemoryEventBus())
    client_app.event_bus.on(ConsoleDetached, lambda e: events.append(e.reason))
    client_app.use(client_ext)
    client_app.boot()
    try:
        assert _wait_until(lambda: len(events) > 0)
        assert "could not connect" in events[0]
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
