import concurrent.futures
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PoolStats:
    """
    @brief One thread pool's occupancy — introduced by `EPIC-007B`.

    @details `queue_depth` is the reason this type exists: a queue that grows is the
    earliest visible sign an application is falling behind, and neither `IThreadManager`
    nor `ITaskManager`'s internal executors had any way to expose it before this.

    @details Computed, not read out of `ThreadPoolExecutor` internals. A submitted
    callable is either running on one of `max_workers` threads or waiting — there is no
    third state — so `queue_depth = max(0, in_flight - max_workers)` is exact without
    reaching into the executor's private `_work_queue`, which this engine's own
    discipline (`EPIC-006` criterion 2) treats as off-limits even for a stdlib type.

    @param name Which pool this is (`"background"`, `"critical"`, or an application's own
        label for a general-purpose `IThreadManager`). Empty only on a default/no-op
        instance — see `IThreadManager.stats()`.
    @param in_flight Submitted but not yet done — running or queued, no distinction made
        between the two beyond `queue_depth` below.
    """

    name: str
    max_workers: int
    in_flight: int
    queue_depth: int
    submitted: int
    completed: int


class IThreadManager(ABC):
    """!
    @brief Interface for managing a thread pool executor.

    This interface defines the contract for submitting tasks to be executed in
    a background thread pool and for shutting down the pool when no longer needed.
    """

    @abstractmethod
    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        """!
        @brief Submit a task to be executed by the thread pool.

        @param task The callable task to execute.
        @param args Positional arguments for the task.
        @param kwargs Keyword arguments for the task.
        @return A Future representing the execution of the task.
        """
        pass

    @abstractmethod
    def shutdown(self, wait: bool = True) -> None:
        """!
        @brief Shut down the thread pool.

        @param wait If True, blocks until all pending tasks are completed.
        """
        pass

    def stats(self) -> PoolStats | None:
        """
        @brief This pool's current occupancy, or `None` if not tracked.

        @details Concrete, not abstract (`code-rule.md` §L / `EPIC-005A`'s idiom for
        `ITraceRecorder`): a third-party `IThreadManager` written before this method
        existed must not fail to instantiate because of it. `None` is the honest default
        rather than a zeroed `PoolStats` — a struct reading `0/0 in flight` implies "this
        pool was observed and is idle," not "this implementation does not track
        occupancy," and `EPIC-007A`'s own schema draws that exact distinction for a
        reason: collapsing the two is how a panel reads as healthy while measuring
        nothing.
        """
        return None
