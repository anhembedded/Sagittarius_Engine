import concurrent.futures
import threading
from collections.abc import Callable
from typing import Any

from sagittarius_engine.interfaces.i_thread_manager import (
    IThreadManager,
    PoolStats,
)


class ThreadManager(IThreadManager):
    """!
    @brief ThreadManager implementation using ThreadPoolExecutor.

    This class provides a centralized thread pool for executing background tasks.
    It implements the IThreadManager interface.
    """

    def __init__(self, max_workers: int = 4, name: str = "default") -> None:
        """!
        @brief Initialize the ThreadManager.

        @param max_workers The maximum number of threads to use in the pool.
        @param name Label this pool reports as from `stats()` (`EPIC-007B`) —
            distinguishes one `IThreadManager` instance from another when an
            application registers more than one.
        """
        self._max_workers = max_workers
        self._name = name
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self._max_workers
        )
        self._lock = threading.Lock()
        # `EPIC-007B`: counted rather than read from the executor's own
        # private `_work_queue` — see `PoolStats`'s own docstring for why
        # that boundary holds even for a stdlib type.
        self._submitted = 0
        self._completed = 0

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
        with self._lock:
            self._submitted += 1
            future = self._executor.submit(task, *args, **kwargs)
        future.add_done_callback(self._on_done)
        return future

    def _on_done(self, _future: concurrent.futures.Future[Any]) -> None:
        """@brief Counts a submission as finished — completed, failed, or
        cancelled all release the same in-flight slot."""
        with self._lock:
            self._completed += 1

    def shutdown(self, wait: bool = True) -> None:
        """!
        @brief Shut down the thread pool.

        @param wait If True, blocks until all pending tasks are completed.

        @details Deliberately NOT under `self._lock` (found by this changing from a
        latent to a live hazard in `EPIC-007B`): `cancel_futures=True` cancels every
        not-yet-started future, and `Future.cancel()` invokes that future's done
        callbacks *synchronously, on the calling thread* when it succeeds. `_on_done`
        below acquires the same lock — held here, that is this thread deadlocking on
        its own non-reentrant `Lock`. `ThreadPoolExecutor.shutdown()` is thread-safe on
        its own and never needed the lock for correctness.
        """
        self._executor.shutdown(wait=wait, cancel_futures=True)

    def stats(self) -> PoolStats:
        """@brief This pool's current occupancy — `EPIC-007B`."""
        with self._lock:
            submitted, completed = self._submitted, self._completed
        in_flight = submitted - completed
        return PoolStats(
            name=self._name,
            max_workers=self._max_workers,
            in_flight=in_flight,
            queue_depth=max(0, in_flight - self._max_workers),
            submitted=submitted,
            completed=completed,
        )
