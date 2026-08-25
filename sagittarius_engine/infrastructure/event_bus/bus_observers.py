"""
@brief The extension point that lets something watch bus activity without
being a handler (`EPIC-006F`).

@details
`EPIC-006A`–`EPIC-006E` inspect **structure**, which holds still while you look
at it: a set difference over registries, a walk of constructor signatures.
Runtime anomalies are the first thing in this epic that is only observable
*while the application runs*, and watching a running bus is where a diagnostic
can most easily become the problem it was meant to find.

@par Why here, and why nothing new in the hot path
Two funnels already exist and are already called on every dispatch:

- `dispatch_trace.log_event_emitted(logger, event_name, handler_count)`
- `handler_reporting.report_handler_failure(logger, event_name, handler, exc)`

Both were built for `EPIC-008C` so that no bus could get reporting wrong on its
own, and every bus — plus `QtEventBridge` — routes through them. That means the
two questions `EPIC-006F` asks ("was anything listening?" and "did a handler
raise?") are *already answered* at exactly one place each. Observing those
answers costs one call on an empty tuple; instrumenting the buses would have
meant six new call sites and six chances to diverge.

@par Layering
This is infrastructure, and the observer is an extension
(`extensions/diagnostics/runtime.py`) that registers *into* it. The dependency
points that way on purpose: infrastructure importing an extension to notify it
would invert the engine's layering, which `tests/test_architecture.py` forbids
and which this repository has removed twice already (`TASK-008`, `TASK-013`).
"""

from __future__ import annotations

import threading
from abc import ABC


class IBusObserver(ABC):
    """
    @brief Something that wants to know what the bus is doing.

    @details Both methods are **concrete no-ops**, not abstract. An observer
    that only cares about failures should not have to write an empty
    `event_emitted`, and `code-rule.md` §L forbids the usual alternative of
    raising `NotImplementedError` from an inherited method. This mirrors
    `IEventBus.get_handlers()` / `subscriptions()`.

    @warning These run **inside the dispatch path**, on whichever thread is
    emitting. An implementation must be fast, must not block, and must not
    raise — see `_notify()` for what happens if it does.
    """

    def event_emitted(self, event_name: str, handler_count: int) -> None:
        """@brief Called once per emit, before the handlers run."""

    def handler_failed(self, event_name: str, handler: str, exc: BaseException) -> None:
        """
        @brief Called when a handler raised.

        @param handler Already-described, because `report_handler_failure()`
            has computed it for its own log line — passing the callable would
            make every observer repeat that work.
        """


#: Copy-on-write, read without a lock. The same pattern `MemoryEventBus` uses
#: for `_handlers`, and for the same reason: reads happen on every dispatch,
#: writes happen at boot and shutdown.
_observers: tuple[IBusObserver, ...] = ()
_lock = threading.Lock()


def add_bus_observer(observer: IBusObserver) -> None:
    """@brief Registers an observer. Idempotent — registering twice would
    double-count, which is worse than the call being ignored."""
    global _observers
    with _lock:
        if observer not in _observers:
            _observers = (*_observers, observer)


def remove_bus_observer(observer: IBusObserver) -> None:
    """@brief Unregisters an observer. Silent if it was never registered, so a
    shutdown path does not have to track whether boot got that far."""
    global _observers
    with _lock:
        _observers = tuple(o for o in _observers if o is not observer)


def bus_observers() -> tuple[IBusObserver, ...]:
    """@brief The current observers. For tests and introspection."""
    return _observers


# Both functions below swallow whatever an observer raises, and duplicate the
# `try`/`except` rather than sharing a helper. Two deliberate decisions:
#
# **Why swallow.** This is the one place in this repository where it is right.
# An observer is a *diagnostic*; a broken one that could raise into the
# dispatch path would break the application it was installed to watch, turning
# an optional monitor into a failure mode strictly worse than the ones it
# reports. It cannot report the failure either — the only channel here is the
# bus logger, and an observer that raises on every emit would flood it. The
# honest trade, recorded rather than hidden: **a broken observer goes quiet,
# it does not go loud.**
#
# **Why duplicated.** The shared `_notify(method, *args)` helper this replaced
# cost an extra call frame per observer per emit — measured at ~65 ns, against
# ~210 ns of total observer overhead on a ~490 ns emit. Four duplicated lines
# for a third of the cost of the feature is worth it, and these two functions
# are the entire hot path of `EPIC-006F`.


def notify_event_emitted(event_name: str, handler_count: int) -> None:
    """@brief Fans an emit out to the observers. Called from the dispatch path.

    @warning Callers guard on `_observers` being non-empty before calling —
    see `dispatch_trace.log_event_emitted()` for the measurement that made
    that worth doing."""
    for observer in _observers:
        try:
            observer.event_emitted(event_name, handler_count)
        except Exception:  # noqa: BLE001 - see the note above
            pass


def notify_handler_failed(event_name: str, handler: str, exc: BaseException) -> None:
    """@brief Fans a handler failure out to the observers."""
    for observer in _observers:
        try:
            observer.handler_failed(event_name, handler, exc)
        except Exception:  # noqa: BLE001 - see the note above
            pass
