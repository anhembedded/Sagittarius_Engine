"""
@brief Application Health Check Extension.

@details
Registers `HealthCheckQuery` in the container, logs status through the engine
logger, emits `HealthUpdatedEvent` once at boot, and — since `EPIC-008E` —
answers `HealthCheckRequested` by re-measuring and publishing a fresh result.

The two event classes live in their own modules
(`health_updated_event.py`, `health_check_requested.py`): an event and the
extension that emits it sit at different abstraction levels. `HealthUpdatedEvent`
is re-exported here because `from ...health_module import HealthUpdatedEvent`
is an import path consuming applications already use.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.extensions.health.health_check_requested import (
    HealthCheckRequested,
)
from sagittarius_engine.extensions.health.health_updated_event import HealthUpdatedEvent
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_extension import IExtension

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_event_bus import IEventBus

logger = logging.getLogger(__name__)

#: Re-exported for backwards compatibility — see the module docstring.
__all__ = ["HealthCheckRequested", "HealthExtension", "HealthUpdatedEvent"]


class IHealthContext(Protocol):
    @property
    def container(self) -> IContainer: ...

    @property
    def event_bus(self) -> IEventBus | None: ...

    @property
    def logger(self) -> Any | None: ...


class HealthExtension(IExtension[IHealthContext]):
    """
    @brief Extension for Application Health Checks.
    """

    def register(self, context: IHealthContext) -> None:
        """@brief Registers the HealthCheckQuery in the container."""
        context.container.bind(HealthCheckQuery, HealthCheckQuery)

    def boot(self, context: IHealthContext) -> None:
        """
        @brief Reports health once, then keeps answering `HealthCheckRequested`.

        @details The boot-time report is kept exactly as it was — it is
        observable behaviour that consumers outside this repository rely on,
        and `EPIC-008E` adds the request path rather than replacing it.
        """
        self._report_health(context, trigger="HealthExtension.boot()")

        event_bus = getattr(context, "event_bus", None)
        if event_bus is not None:
            event_bus.on(
                HealthCheckRequested.event_name,
                lambda _payload: self._report_health(
                    context, trigger="HealthExtension handling HealthCheckRequested"
                ),
            )

    def _report_health(self, context: IHealthContext, *, trigger: str) -> None:
        """
        @brief Runs the health query, logs the result, and publishes
        `HealthUpdatedEvent`.

        @param trigger What asked for this report, named in the failure log so
        a reader can tell a boot-time failure from a failed request — the two
        have different causes and different blast radius, and a shared generic
        message would hide which one happened
        (`.agents/rules/logging-rule.md`: log what actually occurred).

        @details Exceptions are logged rather than raised, on two separate
        grounds. At boot (audited under `TASK-026` requirement 5): a health
        extension that fails to report health must not do so silently — that
        is worse than having no health extension, because the system is
        assumed to have one — but neither may it abort engine bootstrap over
        a check that could not run. On the request path: this executes inside
        a bus handler, where raising would be reported by
        `handler_reporting` and dropped anyway; catching here keeps the
        message specific to health rather than generic.
        """
        try:
            query = context.container.resolve(HealthCheckQuery)
            status = query.execute()
            status_str = str(status.get("status", "healthy")).upper()
            components = status.get("components", {})
            comp_str = ", ".join(
                f"{k.capitalize()}: {str(v).upper()}" for k, v in components.items()
            )
            log_msg = f"System Health: {status_str} ({comp_str})"

            context_logger = getattr(context, "logger", None)
            if context_logger is not None:
                context_logger.info(log_msg)

            event_bus = getattr(context, "event_bus", None)
            if event_bus is not None:
                event_bus.emit(
                    HealthUpdatedEvent.event_name, HealthUpdatedEvent(status)
                )
        except Exception:
            logger.exception("%s failed to report health status", trigger)

    def shutdown(self, context: IHealthContext) -> None:
        """@brief Shuts down the Health Extension."""
        pass
