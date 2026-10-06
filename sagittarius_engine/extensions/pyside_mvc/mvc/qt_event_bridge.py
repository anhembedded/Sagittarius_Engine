"""
@brief `QtEventBridge` — the single place an `IEventBus` handler crosses onto
the Qt main thread (EPIC-008D).

@details
`MemoryEventBus` runs a handler on whichever thread called `emit()`. For a
websocket feed or a thread-pool worker that is not the Qt main thread, and
touching a widget from there crashes the process. Every presenter in the
reference consuming app therefore hand-rolled its own hop: 48 Qt signals
across three presenters, in three different naming conventions, whose entire
job was to move a call onto the main thread. Nothing enforced it — thread
safety rested on the next author reading a `@warning` line in a docstring.

This class is that hop, once, as a mechanism rather than a convention. A
presenter subscribes through it and its handler is simply *always* called on
the main thread.

@par Why the delivery signal uses Qt's default connection
`AutoConnection` resolves per emit, against the receiver's thread affinity:
a cross-thread emit is queued onto the main thread, a same-thread emit is a
direct call. Both satisfy "the handler runs on the main thread", and the
second preserves the synchronous behaviour call sites already depend on —
forcing every delivery through the event loop would change *when* an
already-safe handler runs for no safety gain. The bridge must therefore be
constructed on the main thread, which is where a presenter is built.

@par Why this class reports handler failures itself
A Qt signal/slot boundary does not propagate exceptions back to the emitter:
PySide6 catches whatever a slot raises and prints it ("Exceptions caught in
Qt event loop"). So the bus's own `try/except` — the guarantee `EPIC-008C`
established — cannot see a failure that happens on the far side of this hop,
and for a *queued* delivery it is doubly unreachable, since `forward()`
returned long before the handler ran. Left alone, routing a handler through
this bridge would have silently reverted the app to the very behaviour
`BUG-005`/`EPIC-008C` fixed. The bridge therefore catches at the delivery
point and reports through the same `handler_reporting` path every bus uses,
so a bridged failure and a direct one are reported identically.

@par Why nothing here refers back to the subscriber (`BUG-019`)
The bus holds each forwarder, and a forwarder holds the bridge and the
handler only weakly; a handler that is a bound method is held as a
`WeakMethod`. A presenter owns its bridge, so a strong reference back would
make presenter and bridge one reference cycle, freed only when Python's
collector next runs, on whichever thread allocates at that moment. A
presenter freed there with an active `QTimer` crashed the UI thread's event
loop (the gate's intermittent segmentation fault). Without the cycle, the
last reference going frees them at once, where it goes, and a subscriber that
is gone simply receives nothing.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from types import MethodType
from typing import Any

from PySide6.QtCore import QObject, Signal

from sagittarius_engine.extensions.pyside_mvc.mvc.event_delivery import EventDelivery
from sagittarius_engine.infrastructure.event_bus.bus_logger import resolve_bus_logger
from sagittarius_engine.infrastructure.event_bus.diagnostic_labels import describe_event
from sagittarius_engine.infrastructure.event_bus.handler_reporting import (
    report_handler_failure,
)
from sagittarius_engine.interfaces import IEventBus, ILogger

#: Gives the handler back, or `None` once a bound method's object is gone.
type _Target = Callable[[], Callable[..., Any] | None]


class QtEventBridge(QObject):
    """
    @brief Subscribes to an `IEventBus` on a presenter's behalf and delivers
    every payload on the Qt main thread.

    @details Owns its own subscription bookkeeping so that `off_all()` can
    remove exactly what this bridge registered and nothing else — one
    presenter tearing down must never unsubscribe another presenter that is
    still on screen. `BasePresenter` delegates to that bookkeeping rather
    than keeping a second copy of it.
    """

    #: Carries an `EventDelivery`. A single `object` argument rather than several
    #: typed ones: Qt would otherwise need a registered meta-type for the
    #: payload, which is arbitrary Python here.
    _deliver = Signal(object)

    def __init__(
        self,
        event_bus: IEventBus,
        logger: ILogger | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._event_bus = event_bus
        self._logger = resolve_bus_logger(logger)
        #: `(event, handler key) -> (forwarder registered on the bus, the
        #: handler as the forwarder holds it)`. The forwarder is what the bus
        #: holds, so `off()` must pass that same object back — the original
        #: handler was never registered directly.
        self._forwarders: dict[
            tuple[Any, object], tuple[Callable[..., Any], _Target]
        ] = {}
        self._deliver.connect(self._on_deliver)

    def on(
        self, event_name_or_type: str | type | Any, handler: Callable[..., Any]
    ) -> None:
        """
        @brief Subscribes `handler` to an event, delivered on the main thread.
        @details Subscribing the same `(event, handler)` pair twice is a
        no-op, matching `MemoryEventBus.on`'s own duplicate handling — a
        presenter re-running its wiring must not double-deliver.
        """
        key = (event_name_or_type, _handler_key(handler))
        existing = self._forwarders.get(key)
        if existing is not None:
            if existing[1]() is not None:
                return
            # The key's object is gone and a new one reuses its identity.
            self.off(event_name_or_type, handler)

        label = describe_event(event_name_or_type)
        bridge = weakref.ref(self)
        target = _weak_handler(handler)

        def forward(payload: Any) -> None:
            live_bridge = bridge()
            live_handler = target()
            if live_bridge is None or live_handler is None:
                return
            live_bridge._deliver.emit(EventDelivery(live_handler, payload, label))

        self._forwarders[key] = (forward, target)
        self._event_bus.on(event_name_or_type, forward)

    def off(
        self, event_name_or_type: str | type | Any, handler: Callable[..., Any]
    ) -> None:
        """@brief Unsubscribes a handler previously registered via `on()`."""
        entry = self._forwarders.pop((event_name_or_type, _handler_key(handler)), None)
        if entry is not None:
            self._event_bus.off(event_name_or_type, entry[0])

    def off_all(self) -> None:
        """
        @brief Unsubscribes everything this bridge registered.
        @details What makes a presenter's teardown complete without the
        presenter having to remember each individual subscription.
        """
        for (event, _handler), (forwarder, _target) in list(self._forwarders.items()):
            self._event_bus.off(event, forwarder)
        self._forwarders.clear()

    def _on_deliver(self, delivery: EventDelivery) -> None:
        try:
            delivery.handler(delivery.payload)
        except Exception as exc:
            report_handler_failure(
                self._logger, delivery.event_label, delivery.handler, exc
            )


def _handler_key(handler: Callable[..., Any]) -> object:
    """What identifies a subscription without holding its subscriber: a bound
    method by its object's identity and its function, anything else as it is
    (a bound method is a new object on every attribute access, so identity
    alone would never match it again)."""
    if isinstance(handler, MethodType):
        return (id(handler.__self__), handler.__func__)
    return handler


def _weak_handler(handler: Callable[..., Any]) -> _Target:
    """The handler, held without keeping its object alive when it is a bound
    method. Anything else is held as it is: a function, a method of an object
    that takes no weak reference, and a lambda or `functools.partial`, which
    keeps alive whatever it closes over (one closing over its subscriber
    brings the cycle back; subscribe the bound method instead)."""
    if isinstance(handler, MethodType):
        try:
            return weakref.WeakMethod(handler)
        except TypeError:
            pass
    return lambda: handler
