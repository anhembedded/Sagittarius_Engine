from dataclasses import dataclass

from sagittarius_engine.domain.event_registry import EventRegistry


@dataclass
class TaskStarted:
    """Event emitted when a background task has started."""

    event_name = "runtime.tasks.started"
    task_id: str
    task_name: str


@dataclass
class TaskCompleted:
    """Event emitted when a background task has completed successfully."""

    event_name = "runtime.tasks.completed"
    task_id: str
    task_name: str


@dataclass
class TaskProgressUpdated:
    """Event emitted when a background task updates its progress."""

    event_name = "runtime.tasks.progress"
    task_id: str
    progress: float
    message: str


@dataclass
class TaskFailed:
    """Event emitted when a background task has failed."""

    event_name = "runtime.tasks.failed"
    task_id: str
    task_name: str
    error: Exception


EventRegistry.register_named(TaskStarted.event_name, TaskStarted, module=__name__)
EventRegistry.register_named(TaskCompleted.event_name, TaskCompleted, module=__name__)
EventRegistry.register_named(
    TaskProgressUpdated.event_name, TaskProgressUpdated, module=__name__
)
EventRegistry.register_named(TaskFailed.event_name, TaskFailed, module=__name__)
