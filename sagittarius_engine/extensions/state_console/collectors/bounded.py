"""`BoundedStructuresCollector` — `EPIC-007C`.

`ADR-001` §2.9's answer to "dynamic memory": occupancy of everything in the
engine that has a ceiling, all O(1) to read, none of it `tracemalloc`.
"""

from __future__ import annotations

import gc

from sagittarius_engine.extensions.audit.contracts import BoundedStructures
from sagittarius_engine.extensions.audit.recorder import TraceRecorder
from sagittarius_engine.extensions.state_console.collector import ISnapshotSection
from sagittarius_engine.interfaces import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


class BoundedStructuresCollector(ISnapshotSection[BoundedStructures]):
    """
    @brief Ring buffer fill, retained-task occupancy, subscription count, GC
    generation counts.

    @param recorder `None` when the application never called
        `context.enable_tracing(...)` — the ring fields all read `0` in that
        case, which is correct: there is no ring to report on, not a ring
        that happens to be empty.
    """

    def __init__(
        self,
        task_manager: ITaskManager,
        bus: IEventBus,
        recorder: TraceRecorder | None = None,
    ) -> None:
        self._task_manager = task_manager
        self._bus = bus
        self._recorder = recorder

    def collect(self) -> BoundedStructures:
        ring_used = 0
        ring_capacity = 0
        ring_dropped = 0
        if self._recorder is not None:
            ring_used = len(self._recorder)
            ring_capacity = self._recorder.capacity
            ring_dropped = self._recorder.dropped

        retained_limit = self._task_manager.max_retained_tasks()

        return BoundedStructures(
            ring_used=ring_used,
            ring_capacity=ring_capacity,
            ring_dropped=ring_dropped,
            retained_tasks=len(self._task_manager.snapshot()),
            retained_task_limit=retained_limit if retained_limit >= 0 else 0,
            subscriptions=sum(
                len(handlers) for handlers in self._bus.subscriptions().values()
            ),
            gc_counts=tuple(gc.get_count()),
        )
