"""
@brief Application Health Check Extension.

@details
Registers the HealthCheckQuery in the container, logs status via the engine
logger, and automatically emits HealthUpdatedEvent via the EventBus on boot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from sagittarius_engine.domain.base_event import BaseEvent
from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_extension import IExtension

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_event_bus import IEventBus


class HealthUpdatedEvent(BaseEvent):
    """
    @brief Event emitted whenever health checks are executed.
    """

    event_name = "health.updated"

    def __init__(self, status: dict[str, Any]) -> None:
        super().__init__()
        self.status: dict[str, Any] = status


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
        """@brief Boots the Health Extension, logs status, and emits health event."""
        try:
            query = context.container.resolve(HealthCheckQuery)
            status = query.execute()
            status_str = str(status.get("status", "healthy")).upper()
            components = status.get("components", {})
            comp_str = ", ".join(
                f"{k.capitalize()}: {str(v).upper()}" for k, v in components.items()
            )
            log_msg = f"System Health: {status_str} ({comp_str})"

            if hasattr(context, "logger") and context.logger is not None:
                context.logger.info(log_msg)

            if hasattr(context, "event_bus") and context.event_bus is not None:
                context.event_bus.emit(
                    HealthUpdatedEvent.event_name, HealthUpdatedEvent(status)
                )
        except Exception:  # noqa: BLE001
            pass

    def shutdown(self, context: IHealthContext) -> None:
        """@brief Shuts down the Health Extension."""
        pass
