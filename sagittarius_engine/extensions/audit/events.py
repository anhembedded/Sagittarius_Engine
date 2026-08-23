from typing import Any

from sagittarius_engine.domain.base_event import BaseEvent


class SystemStateChangedEvent(BaseEvent):
    """
    Event emitted when the system state monitored by Audit Extension changes.
    """

    def __init__(self, state_snapshot: dict[str, Any]):
        super().__init__()
        self.state_snapshot = state_snapshot


class TaskCompletedEvent(BaseEvent):
    """Example specific audit event."""

    def __init__(self, task_id: str, status: str):
        super().__init__()
        self.task_id = task_id
        self.status = status
