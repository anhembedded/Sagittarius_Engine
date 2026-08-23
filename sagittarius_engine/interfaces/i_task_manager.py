from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sagittarius_engine.runtime.tasks.background_task import TaskState
    from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


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
