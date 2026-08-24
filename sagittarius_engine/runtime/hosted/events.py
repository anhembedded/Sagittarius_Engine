from dataclasses import dataclass
from typing import ClassVar

from sagittarius_engine.domain.event_registry import EventRegistry


@dataclass
class HostedServiceStarted:
    """Event emitted when a hosted service has started."""

    event_name: ClassVar[str] = "runtime.hosted.started"

    service_name: str


@dataclass
class HostedServiceStopped:
    """Event emitted when a hosted service has stopped."""

    event_name: ClassVar[str] = "runtime.hosted.stopped"

    service_name: str


EventRegistry.register_named(
    HostedServiceStarted.event_name, HostedServiceStarted, module=__name__
)
EventRegistry.register_named(
    HostedServiceStopped.event_name, HostedServiceStopped, module=__name__
)
