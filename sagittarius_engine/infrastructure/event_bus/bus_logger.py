"""
@brief How an event bus obtains the logger it reports through.

@details One line of policy, but it is policy shared by every bus and by the
Qt bridge in front of them: they all fall back to the *same* logger name, so
an application can route or silence event-bus diagnostics as one unit instead
of having to know how many bus implementations exist.

Kept out of `handler_reporting` because "which logger does this component
get" and "how is a failure formatted" are different decisions that change for
different reasons.
"""

from __future__ import annotations

from sagittarius_engine.infrastructure.logging.logger_resolution import resolve_logger
from sagittarius_engine.interfaces import ILogger

#: Shared by every bus and by `QtEventBridge`.
EVENT_BUS_LOGGER_NAME = "sagittarius_engine.event_bus"


def resolve_bus_logger(logger: ILogger | None) -> ILogger:
    """@brief The injected logger, or the shared event-bus fallback."""
    return resolve_logger(logger, fallback_name=EVENT_BUS_LOGGER_NAME)
