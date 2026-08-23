import concurrent.futures
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


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
