"""`ThreadPoolCollector` — `EPIC-007C`.

Two sources, both `EPIC-007B`: `ITaskManager.pool_stats()` — the `background`/
`critical` executors every application using `spawn()` already exercises —
and, if the application also registered one, `IThreadManager.stats()` — a
general-purpose pool most of this codebase does not use at all. Reporting
both is why this collector takes an optional second dependency rather than
picking one; conflating them would under-report whichever was left out (see
`EPIC-007B`'s own §2.2 outcome note).
"""

from __future__ import annotations

from sagittarius_engine.extensions.audit.contracts import ThreadPoolStats
from sagittarius_engine.extensions.state_console.collector import ISnapshotSection
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class ThreadPoolCollector(ISnapshotSection[tuple[ThreadPoolStats, ...]]):
    """@brief Occupancy of every pool this application's `ITaskManager`
    manages, plus its `IThreadManager` if one is registered."""

    def __init__(
        self, task_manager: ITaskManager, thread_manager: IThreadManager | None = None
    ) -> None:
        self._task_manager = task_manager
        self._thread_manager = thread_manager

    def collect(self) -> tuple[ThreadPoolStats, ...]:
        pools = [
            ThreadPoolStats(
                name=pool.name,
                max_workers=pool.max_workers,
                in_flight=pool.in_flight,
                queue_depth=pool.queue_depth,
                submitted=pool.submitted,
                completed=pool.completed,
            )
            for pool in self._task_manager.pool_stats()
        ]
        if self._thread_manager is not None:
            stats = self._thread_manager.stats()
            if stats is not None:
                pools.append(
                    ThreadPoolStats(
                        name=stats.name,
                        max_workers=stats.max_workers,
                        in_flight=stats.in_flight,
                        queue_depth=stats.queue_depth,
                        submitted=stats.submitted,
                        completed=stats.completed,
                    )
                )
        return tuple(pools)
