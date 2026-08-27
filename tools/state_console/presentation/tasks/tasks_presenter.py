from __future__ import annotations

from typing import Any

from sagittarius_engine.extensions.pyside_mvc import BasePresenter
from tools.state_console.domain.events import (
    ConsoleAttached,
    ConsoleDetached,
    SnapshotReceived,
)
from tools.state_console.presentation.overview.overview_view_model import (
    ATTACHED_IDLE,
    ATTACHED_READING,
    NOT_ATTACHED,
)
from tools.state_console.presentation.tasks.tasks_view_model import TasksViewModel


class TasksPresenter(BasePresenter):
    def __init__(self, view: Any, container: Any) -> None:
        super().__init__(view, container)
        self.view_model = TasksViewModel()
        self.view.bind(self.view_model)
        self._connect_engine_events()

    def _connect_engine_events(self) -> None:
        self.subscribe(ConsoleAttached, self._on_attached)
        self.subscribe(ConsoleDetached, self._on_detached)
        self.subscribe(SnapshotReceived, self._on_snapshot)

    def _on_attached(self, _event: ConsoleAttached) -> None:
        self.view_model.set_connection_state(ATTACHED_IDLE)

    def _on_detached(self, event: ConsoleDetached) -> None:
        self.view_model.set_connection_state(NOT_ATTACHED)
        self.view_model.set_detach_reason(event.reason)

    def _on_snapshot(self, event: SnapshotReceived) -> None:
        self.view_model.set_connection_state(ATTACHED_READING)
        snapshot = event.snapshot

        self.view_model.set_tasks(
            [
                {
                    "id": t.id,
                    "name": t.name,
                    "state": t.state,
                    "progress": t.progress,
                    "ageSeconds": t.age_ns / 1_000_000_000,
                    "error": t.error,
                }
                for t in snapshot.tasks
            ]
        )
        self.view_model.set_thread_pools(
            [
                {
                    "name": pool.name,
                    "inFlight": pool.in_flight,
                    "maxWorkers": pool.max_workers,
                    "queueDepth": pool.queue_depth,
                    "submitted": pool.submitted,
                    "completed": pool.completed,
                }
                for pool in snapshot.thread_pools
            ]
        )
        bounded = snapshot.bounded
        lifecycle = snapshot.lifecycle
        self.view_model.set_bounded(
            bounded.retained_tasks if bounded is not None else 0,
            bounded.retained_task_limit if bounded is not None else 0,
            lifecycle.scheduler_jobs if lifecycle is not None else 0,
            lifecycle.scheduler_jobs_without_next_run if lifecycle is not None else 0,
        )
