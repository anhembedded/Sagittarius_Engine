"""`TaskCollector` — `EPIC-007C`.

Maps `ITaskManager.snapshot()`'s domain `TaskSnapshot` (`EPIC-007B`) into the
wire `TaskRecord` (`EPIC-007A`) — the same "domain type, mirrored not reused"
shape as `Registration` -> `RegistrationState` and `Finding` -> `FindingRecord`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sagittarius_engine.extensions.audit.contracts import TaskRecord
from sagittarius_engine.extensions.state_console.collector import ISnapshotSection
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


class TaskCollector(ISnapshotSection[tuple[TaskRecord, ...]]):
    """
    @brief Every retained task, as the wire shape.

    @warning `thread` is empty except for a failed sync task — see
    `TaskSnapshot`'s own corrected docstring (`EPIC-008E`) for why an async
    failure leaves it empty rather than naming the shared event-loop thread.
    `age_ns` is wall-clock-derived; see `TaskRecord.age_ns`'s corrected
    docstring for why that is the honest choice rather than a silent one.
    """

    def __init__(self, task_manager: ITaskManager) -> None:
        self._task_manager = task_manager

    def collect(self) -> tuple[TaskRecord, ...]:
        now = datetime.now(UTC)
        return tuple(
            TaskRecord(
                id=task.id,
                name=task.name,
                state=task.state.value,
                progress=task.progress,
                age_ns=int((now - task.started_at).total_seconds() * 1_000_000_000)
                if task.started_at is not None
                else 0,
                thread=task.thread or "",
                error=task.error or "",
                error_type=task.error_type or "",
                stack=task.stack or "",
            )
            for task in self._task_manager.snapshot()
        )
