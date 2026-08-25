"""
@brief The one place a failed event handler gets reported — so no bus, and no
thread-hop in front of one, can get it wrong on its own (EPIC-008C).

@details
Before this module, four buses (`MemoryEventBus`, `AsyncioEventBus`,
`ThreadPoolEventBus`, `ResilientEventBus`) each hand-rolled the same report,
and each got the same things wrong: the log was guarded by `if self.logger:`,
so a bus constructed without one lost handler exceptions entirely; and only
`str(exception)` was recorded, with no traceback, leaving nothing to locate
the failure by.

Fixing whichever bus a defect happened to be reported against would have left
the others broken, so the report lives here and every dispatcher calls it —
including `QtEventBridge`, which must report at its own delivery point
because a Qt signal boundary does not propagate exceptions back to the bus
that emitted through it.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from sagittarius_engine.infrastructure.event_bus import bus_observers
from sagittarius_engine.infrastructure.event_bus.diagnostic_labels import (
    describe_handler,
)
from sagittarius_engine.interfaces import ILogger


def report_handler_failure(
    logger: ILogger, event_name: str, handler: Callable[..., Any], exc: BaseException
) -> None:
    """
    @brief Reports a handler that raised, at ERROR, with a full traceback.

    @details Must be called from inside the `except` block — the traceback is
    read from the live exception context via `traceback.format_exc()`.

    The exception is reported rather than re-raised on purpose: a bus fans one
    event out to unrelated subscribers, and one broken subscriber must not
    stop the others from being notified. That isolation is only defensible
    while the failure is *visible*, which is what this function guarantees.
    """
    described = describe_handler(handler)
    # EPIC-006F. After the log, never instead of it: the report above is the
    # guarantee this module exists to make, and an observer must not be able to
    # take it away by being registered.
    if bus_observers._observers:
        bus_observers.notify_handler_failed(event_name, described, exc)
    logger.error(
        f"Handler {described} raised {type(exc).__name__} "
        f"while handling event '{event_name}': {exc}",
        extra={
            "event_name": event_name,
            "handler": described,
            "traceback": traceback.format_exc(),
        },
    )
