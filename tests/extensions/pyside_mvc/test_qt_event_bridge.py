"""`QtEventBridge` — the one place an event-bus handler crosses onto the Qt
main thread (EPIC-008D).

Why this exists: `MemoryEventBus` invokes handlers on whatever thread called
`emit()`, which for a websocket or thread-pool producer is a worker thread.
Touching a QWidget from there is a crash. Before this class, every presenter
in the reference consuming app hand-rolled its own bridge — 48 Qt signals
across three presenters, in three different naming conventions, whose only
job was to hop threads. Thread safety was enforced by remembering to read a
`@warning` line in a docstring.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QThread

from sagittarius_engine.extensions.pyside_mvc.mvc.qt_event_bridge import QtEventBridge
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_EVENT = "some.event"


@pytest.fixture
def bus():
    return MemoryEventBus()


def test_handler_runs_on_the_main_thread_when_emitted_from_a_worker(qtbot, bus):
    """The whole reason this class exists."""
    bridge = QtEventBridge(bus)
    main_thread = QThread.currentThread()
    seen: list[QThread] = []

    bridge.on(_EVENT, lambda _payload: seen.append(QThread.currentThread()))

    worker = threading.Thread(target=lambda: bus.emit(_EVENT, "payload"))
    worker.start()
    worker.join()

    qtbot.waitUntil(lambda: len(seen) == 1, timeout=2000)
    assert seen[0] is main_thread


def test_payload_survives_the_hop(qtbot, bus):
    bridge = QtEventBridge(bus)
    seen: list[object] = []

    bridge.on(_EVENT, seen.append)

    worker = threading.Thread(target=lambda: bus.emit(_EVENT, {"symbol": "BTCUSDT"}))
    worker.start()
    worker.join()

    qtbot.waitUntil(lambda: len(seen) == 1, timeout=2000)
    assert seen[0] == {"symbol": "BTCUSDT"}


def test_emitting_from_the_main_thread_delivers_synchronously(qtbot, bus):
    """Qt's own `AutoConnection` semantics: same-thread emit is a direct call.
    Kept deliberately — forcing every delivery through the event loop would
    change *when* an already-safe handler runs, breaking call sites that
    reasonably expect `emit()` to have completed on return, for no safety
    gain (a main-thread emit is already on the main thread)."""
    bridge = QtEventBridge(bus)
    seen: list[object] = []

    bridge.on(_EVENT, seen.append)
    bus.emit(_EVENT, "payload")

    assert seen == ["payload"], (
        "A main-thread emit should reach its handler before emit() returns."
    )


def test_off_stops_delivery(qtbot, bus):
    bridge = QtEventBridge(bus)
    seen: list[object] = []

    def handler(payload: object) -> None:
        seen.append(payload)

    bridge.on(_EVENT, handler)
    bridge.off(_EVENT, handler)
    bus.emit(_EVENT, "payload")

    assert seen == []
    assert bus.get_handlers(_EVENT) == ()


def test_off_all_removes_every_subscription_this_bridge_made(qtbot, bus):
    bridge = QtEventBridge(bus)

    bridge.on("a", lambda _p: None)
    bridge.on("b", lambda _p: None)

    bridge.off_all()

    assert bus.get_handlers("a") == ()
    assert bus.get_handlers("b") == ()


def test_off_all_leaves_other_subscribers_alone(qtbot, bus):
    """A bridge must only unsubscribe what it itself registered — a presenter
    tearing down must not silently unsubscribe another presenter still on
    screen."""
    other_bridge = QtEventBridge(bus)
    bridge = QtEventBridge(bus)

    other_bridge.on(_EVENT, lambda _p: None)
    bridge.on(_EVENT, lambda _p: None)

    bridge.off_all()

    assert len(bus.get_handlers(_EVENT)) == 1


def test_subscribing_the_same_handler_twice_registers_it_once(qtbot, bus):
    bridge = QtEventBridge(bus)

    def handler(_payload: object) -> None:
        pass

    bridge.on(_EVENT, handler)
    bridge.on(_EVENT, handler)

    assert len(bus.get_handlers(_EVENT)) == 1


def _raises(_payload: object) -> None:
    raise ValueError("boom")


def test_a_handler_that_raises_does_not_take_down_the_bridge(qtbot, bus):
    """Isolation is the bus's job (`handler_reporting`, EPIC-008C), and it
    must survive the hop — a raising handler delivered through the bridge
    must still leave the bus and the bridge usable."""
    bridge = QtEventBridge(bus)
    seen: list[str] = []

    bridge.on(_EVENT, _raises)
    bridge.on(_EVENT, lambda _p: seen.append("second"))

    bus.emit(_EVENT, None)

    assert seen == ["second"]


def test_a_raising_handler_is_reported_not_merely_swallowed(qtbot, bus):
    """The trap this bridge could easily have fallen into: a Qt signal/slot
    boundary does not propagate exceptions back to the emitter — PySide6
    catches and prints whatever a slot raises. So the bus's own try/except,
    which `EPIC-008C` relies on, cannot see a failure on the far side of the
    hop. Catching it here without reporting it would have swapped one silent
    swallow for another."""
    logger = MagicMock()
    bridge = QtEventBridge(bus, logger=logger)

    bridge.on(_EVENT, _raises)
    bus.emit(_EVENT, None)

    logger.error.assert_called()
    _, kwargs = logger.error.call_args
    extra = kwargs.get("extra") or {}
    assert "traceback" in extra
    assert "ValueError" in extra["traceback"]
    assert extra["event_name"] == _EVENT


def test_a_raising_handler_is_reported_after_a_cross_thread_hop(qtbot, bus):
    """The queued path is where the bus's try/except is *doubly* unreachable:
    `forward()` returns immediately and the handler runs later, on another
    turn of the event loop."""
    logger = MagicMock()
    bridge = QtEventBridge(bus, logger=logger)

    bridge.on(_EVENT, _raises)

    worker = threading.Thread(target=lambda: bus.emit(_EVENT, None))
    worker.start()
    worker.join()

    qtbot.waitUntil(lambda: logger.error.called, timeout=2000)
