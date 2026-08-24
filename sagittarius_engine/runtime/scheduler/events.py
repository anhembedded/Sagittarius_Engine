from dataclasses import dataclass
from typing import ClassVar

from sagittarius_engine.domain.event_registry import EventRegistry


@dataclass
class SchedulerStarted:
    """Event emitted when the scheduler has started."""

    event_name: ClassVar[str] = "runtime.scheduler.started"


@dataclass
class SchedulerStopped:
    """Event emitted when the scheduler has stopped."""

    event_name: ClassVar[str] = "runtime.scheduler.stopped"


EventRegistry.register_named(
    SchedulerStarted.event_name, SchedulerStarted, module=__name__
)
EventRegistry.register_named(
    SchedulerStopped.event_name, SchedulerStopped, module=__name__
)
