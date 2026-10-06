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

import contextlib
import gc
import threading
import weakref
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QObject, QThread

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


class TestNoReferenceCycle:
    """BUG-019: the gate's intermittent native crash. The bridge's forwarder
    closed over the bridge, and its bookkeeping held the subscribing
    presenter's bound methods, so every bridge, and every presenter that
    subscribed through one, was a reference cycle. Python frees a cycle only
    when its collector runs, which is on whatever thread allocates at that
    moment; a presenter freed there with an active `QTimer` (the state
    console's age tick) crashed the UI thread's event loop. Without the cycle,
    the last reference going frees them at once, where it goes."""

    def test_an_abandoned_bridge_is_freed_without_the_collector(self, bus) -> None:
        bridge = QtEventBridge(bus)
        bridge.on(_EVENT, lambda _payload: None)
        alive = weakref.ref(bridge)

        with _collector_off():
            del bridge
            assert alive() is None

    def test_a_subscriber_is_not_kept_alive_by_its_subscription(
        self, qtbot, bus
    ) -> None:
        class _Screen(QObject):
            def __init__(self) -> None:
                super().__init__()
                self.events = QtEventBridge(bus, parent=self)
                self.events.on(_EVENT, self.handle)

            def handle(self, payload: object) -> None:
                pass

        screen = _Screen()
        alive = weakref.ref(screen)

        with _collector_off():
            del screen
            assert alive() is None

    def test_a_freed_subscriber_receives_nothing(self, qtbot, bus) -> None:
        heard: list[object] = []

        class _Screen(QObject):
            def handle(self, payload: object) -> None:
                heard.append(payload)

        bridge = QtEventBridge(bus)
        screen = _Screen()
        bridge.on(_EVENT, screen.handle)
        del screen

        bus.emit(_EVENT, "late")

        assert heard == []

    def test_a_method_subscription_can_still_be_removed(self, qtbot, bus) -> None:
        heard: list[object] = []

        class _Screen(QObject):
            def handle(self, payload: object) -> None:
                heard.append(payload)

        bridge = QtEventBridge(bus)
        screen = _Screen()
        bridge.on(_EVENT, screen.handle)
        bridge.on(_EVENT, screen.handle)
        bus.emit(_EVENT, "first")
        bridge.off(_EVENT, screen.handle)
        bus.emit(_EVENT, "second")

        assert heard == ["first"]


@contextlib.contextmanager
def _collector_off() -> Iterator[None]:
    """Only reference counting frees anything inside: what is freed here was
    in no cycle."""
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def test_a_method_of_an_object_without_weak_references_is_still_delivered(
    qtbot, bus
) -> None:
    heard: list[object] = []

    class _Slotted:
        __slots__ = ()

        def handle(self, payload: object) -> None:
            heard.append(payload)

    subscriber = _Slotted()
    bridge = QtEventBridge(bus)
    bridge.on(_EVENT, subscriber.handle)

    bus.emit(_EVENT, "payload")

    assert heard == ["payload"]


def test_a_new_subscriber_reusing_a_freed_ones_identity_is_subscribed(
    qtbot, bus, monkeypatch
) -> None:
    """A subscription is keyed by its method's object identity, and Python
    reuses the identity of a freed object. A new subscriber whose key matches
    a freed one's must be subscribed, not taken for a duplicate and dropped.
    Every method here gets the same key, which is what identity reuse does."""
    monkeypatch.setattr(
        "sagittarius_engine.extensions.pyside_mvc.mvc.qt_event_bridge._handler_key",
        lambda handler: "reused",
    )
    heard: list[str] = []

    class _Screen(QObject):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

        def handle(self, payload: object) -> None:
            heard.append(self.name)

    bridge = QtEventBridge(bus)
    first = _Screen("first")
    bridge.on(_EVENT, first.handle)
    del first
    second = _Screen("second")

    bridge.on(_EVENT, second.handle)
    bus.emit(_EVENT, "payload")

    assert heard == ["second"]
