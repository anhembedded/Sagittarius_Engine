"""`TasksViewModel` — `EPIC-007E` §3, "Tasks & threads": task table, pool
saturation, queue depth, scheduler.

@details `ExclusiveAction.held_slot()` (`EPIC-007B`) has no field in
`StateSnapshot` yet -- `EPIC-007D`'s own documented gap, carried here
unchanged rather than invented a wire representation for."""

from __future__ import annotations

from PySide6.QtCore import Property, Signal

from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel
from tools.state_console.presentation.overview.overview_view_model import (
    NOT_ATTACHED,
)


class TasksViewModel(BaseQmlViewModel):
    connectionStateChanged = Signal()
    detachReasonChanged = Signal()
    tasksChanged = Signal()
    threadPoolsChanged = Signal()
    boundedChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._connection_state = NOT_ATTACHED
        self._detach_reason = ""
        self._tasks: list[dict] = []
        self._thread_pools: list[dict] = []
        self._retained_tasks = 0
        self._retained_task_limit = 0
        self._scheduler_jobs = 0
        self._scheduler_jobs_without_next_run = 0

    def _get_connection_state(self) -> str:
        return self._connection_state

    def set_connection_state(self, value: str) -> None:
        if value != self._connection_state:
            self._connection_state = value
            self.connectionStateChanged.emit()

    connectionState = Property(
        str, _get_connection_state, notify=connectionStateChanged
    )

    def _get_detach_reason(self) -> str:
        return self._detach_reason

    def set_detach_reason(self, value: str) -> None:
        if value != self._detach_reason:
            self._detach_reason = value
            self.detachReasonChanged.emit()

    detachReason = Property(str, _get_detach_reason, notify=detachReasonChanged)

    def _get_tasks(self) -> list:
        return self._tasks

    tasks = Property("QVariantList", _get_tasks, notify=tasksChanged)  # type: ignore[arg-type]

    def _get_thread_pools(self) -> list:
        return self._thread_pools

    threadPools = Property("QVariantList", _get_thread_pools, notify=threadPoolsChanged)  # type: ignore[arg-type]

    def _get_retained_tasks(self) -> int:
        return self._retained_tasks

    retainedTasks = Property(int, _get_retained_tasks, notify=boundedChanged)

    def _get_retained_task_limit(self) -> int:
        return self._retained_task_limit

    retainedTaskLimit = Property(int, _get_retained_task_limit, notify=boundedChanged)

    def _get_scheduler_jobs(self) -> int:
        return self._scheduler_jobs

    schedulerJobs = Property(int, _get_scheduler_jobs, notify=boundedChanged)

    def _get_scheduler_jobs_without_next_run(self) -> int:
        return self._scheduler_jobs_without_next_run

    schedulerJobsWithoutNextRun = Property(
        int, _get_scheduler_jobs_without_next_run, notify=boundedChanged
    )

    def set_tasks(self, tasks: list[dict]) -> None:
        self._tasks = tasks
        self.tasksChanged.emit()

    def set_thread_pools(self, pools: list[dict]) -> None:
        self._thread_pools = pools
        self.threadPoolsChanged.emit()

    def set_bounded(
        self,
        retained_tasks: int,
        retained_task_limit: int,
        scheduler_jobs: int,
        scheduler_jobs_without_next_run: int,
    ) -> None:
        self._retained_tasks = retained_tasks
        self._retained_task_limit = retained_task_limit
        self._scheduler_jobs = scheduler_jobs
        self._scheduler_jobs_without_next_run = scheduler_jobs_without_next_run
        self.boundedChanged.emit()
