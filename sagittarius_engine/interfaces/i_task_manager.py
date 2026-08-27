from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sagittarius_engine.interfaces.i_thread_manager import PoolStats

if TYPE_CHECKING:
    from sagittarius_engine.runtime.tasks.background_task import TaskState
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    """
    @brief One retained task, frozen at the moment of `ITaskManager.snapshot()` —
    `EPIC-007B`.

    @details `get_active_tasks()` reports only `RUNNING`/`PENDING`; this is what makes
    "task registered / running / not running" answerable for the *retained* history too
    (`COMPLETED`/`FAILED`/`CANCELLED`), without handing out the manager's own live,
    lock-protected task dict — a structure that can mutate mid-read from a pool thread.

    @details No `thread` field. Which OS thread a submission actually ran on is not
    tracked anywhere in this engine — `ThreadPoolExecutor` does not expose it through its
    `Future`, and adding that tracking is not what this snapshot exists to do. `critical`
    is the honest substitute: it says which of the two pools (`EPIC-007B` §
    `ITaskManager.pool_stats()`) the task ran in, which is real, not which thread.

    @param state The engine's own `TaskState` enum, not a string — this is the domain
        type; a wire-format consumer (`extensions/audit/contracts.py`) stringifies it.
    @param error `str(exception)`, not the exception object — a snapshot is a plain value
        that may cross a thread or a wire; the traceback stays in the log line the
        failure already produced.
    """

    id: str
    name: str
    state: "TaskState"
    progress: float
    critical: bool
    started_at: datetime | None
    ended_at: datetime | None
    error: str | None


class ITaskHandle(ABC):
    """
    @brief Abstract Interface for background task handles spawned by the Engine.

    @details
    Why this interface is important for developers:
    1. Strong Typing: Replaces `Any` type annotations when holding task references.
    2. IDE Auto-Complete: Enables auto-completion for `.future`, `.status`, `.token`, and `.cancel()`.
    3. Decoupling: High-level application adapters can check task execution state without depending on
       concrete task implementation classes.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """
        @brief Unique UUID string assigned to this background task.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """
        @brief Human-readable identifier/name for debugging and task tracking.
        """
        ...

    @property
    @abstractmethod
    def token(self) -> "CancellationToken":
        """
        @brief CancellationToken instance associated with this task for cooperative cancellation.
        """
        ...

    @property
    @abstractmethod
    def future(self) -> Any | None:
        """
        @brief The underlying Concurrent Future (or Asyncio Task) executing in the background pool.
        @return Future object supporting `.result()` or `.cancel()`, or None if uninitialized.
        """
        ...

    @property
    @abstractmethod
    def status(self) -> "TaskState":
        """
        @brief Current lifecycle status of the task ('pending', 'running', 'completed', 'failed', 'cancelled').
        """
        ...

    @property
    @abstractmethod
    def progress(self) -> float:
        """
        @brief Current progress of the task, from 0.0 to 100.0.
        """
        ...

    @abstractmethod
    def cancel(self) -> None:
        """
        @brief Signals cooperative cancellation token and cancels the underlying future execution.
        """
        ...


class ITaskManager(ABC):
    """
    @brief Abstract Interface for spawning and coordinating background thread and coroutine tasks.
    """

    @abstractmethod
    def spawn(
        self,
        callable_or_coro: Callable[..., Any] | Any,
        name: str | None = None,
        token: "CancellationToken | None" = None,
        critical: bool = False,
    ) -> ITaskHandle:
        """
        @brief Spawns a synchronous callable function or asynchronous coroutine in the engine background pool.

        @param callable_or_coro Function or coroutine object to run in background.
        @param name Optional descriptive name for task tracking/logging.
        @param token Optional CancellationToken to allow caller to trigger cancellation externally.
        @param critical If True, failure of this task will trigger engine error alerts.
        @return ITaskHandle Strong-typed handle representing the running background task.
        """
        ...

    @abstractmethod
    def get_active_tasks(self) -> list[ITaskHandle]:
        """
        @brief Returns a list of currently active (running or pending) background tasks.
        @return List of active ITaskHandle objects.
        """
        ...

    @abstractmethod
    def shutdown(self, timeout: float = 5.0) -> None:
        """
        @brief Gracefully shuts down all background tasks.
        """
        ...

    def snapshot(self) -> tuple[TaskSnapshot, ...]:
        """
        @brief Every retained task — running, pending, and finished — frozen at this
        instant. `EPIC-007B`.

        @details Concrete, not abstract, for the same reason as
        `IThreadManager.stats()`: a third-party `ITaskManager` predating this method must
        not fail to instantiate over it. `()` is the honest default (`EPIC-007A`'s own
        "absent means not observed" convention) — never a fabricated task list.
        """
        return ()

    def pool_stats(self) -> tuple[PoolStats, ...]:
        """
        @brief Occupancy of this manager's own execution pools — `EPIC-007B`.

        @details Distinct from `IThreadManager.stats()` on purpose: an `ITaskManager`
        implementation may run its work on pools no application-level `IThreadManager`
        ever sees (the reference implementation's `background`/`critical` split is
        exactly this — neither pool is registered in the container as an
        `IThreadManager`). Conflating the two would under-report one or the other.

        @details `()` by default, for the same reason as `snapshot()`.
        """
        return ()

    def max_retained_tasks(self) -> int:
        """
        @brief The configured retention limit `snapshot()` is bounded by —
        `EPIC-007C`.

        @details Found while wiring `BoundedStructures.retained_task_limit`
        (`EPIC-007A`): reporting `retained_tasks` without the limit it is
        bounded by is actively misleading, not merely incomplete — every
        count would read as "approaching the limit" with no limit to compare
        against. `-1` means "no configured limit is known", never `0`, which
        is a real possible value some implementation might legitimately have.
        """
        return -1
