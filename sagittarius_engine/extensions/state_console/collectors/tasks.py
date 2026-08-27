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

    @warning `thread` is always `""`. `TaskSnapshot` carries no thread
    identity — see its own docstring: which OS thread ran a submission is not
    tracked anywhere in this engine. `age_ns` is wall-clock-derived; see
    `TaskRecord.age_ns`'s corrected docstring for why that is the honest
    choice rather than a silent one.
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
                thread="",
                error=task.error or "",
            )
            for task in self._task_manager.snapshot()
        )
