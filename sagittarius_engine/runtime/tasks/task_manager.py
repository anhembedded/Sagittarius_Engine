import inspect
import logging
import threading
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from typing import Any

from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_task_manager import (
    ITaskHandle,
    ITaskManager,
    TaskSnapshot,
)
from sagittarius_engine.interfaces.i_thread_manager import PoolStats
from sagittarius_engine.interfaces.i_trace_recorder import Lane as TraceLane
from sagittarius_engine.runtime.tasks.background_task import BackgroundTask, TaskState
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken
from sagittarius_engine.runtime.tasks.events import (
    TaskCompleted,
    TaskFailed,
    TaskProgressUpdated,
    TaskStarted,
)


class TaskManager(ITaskManager):
    """
    @brief Unified manager for spawning, tracking, and coordinating sync and async tasks.
    """

    _DEFAULT_MAX_RETAINED_TASKS = 50
    _MAX_RETAINED_TASKS_CONFIG_KEY = "task_manager.max_retained_tasks"
    #: `EPIC-007B`'s `pool_stats()` reports these back — named here, not read
    #: from `ThreadPoolExecutor._max_workers`, which is private
    #: (`PoolStats`'s own docstring states the rule this follows: even a
    #: stdlib type's internals are off-limits to this engine's introspection
    #: surface).
    _BACKGROUND_MAX_WORKERS = 20
    _CRITICAL_MAX_WORKERS = 10

    def __init__(self, context: Any) -> None:
        self.context = context
        self.tasks: dict[str, BackgroundTask] = {}
        self._finished_task_ids: deque[str] = deque()
        self.background_executor = ThreadPoolExecutor(
            max_workers=self._BACKGROUND_MAX_WORKERS,
            thread_name_prefix="SagittariusBgTask",
        )
        self.critical_executor = ThreadPoolExecutor(
            max_workers=self._CRITICAL_MAX_WORKERS,
            thread_name_prefix="SagittariusCriticalTask",
        )
        # Backwards compatibility alias
        self.executor = self.background_executor
        self._lock = threading.Lock()
        # EPIC-007B: counted at submit/finish rather than read out of either
        # executor's own private `_work_queue` — see `PoolStats`'s docstring.
        # Only sync submissions pass through these two pools; an async
        # callable runs on `context.async_runtime` instead (see `spawn()`)
        # and has no "worker count" to report in this shape, so it is
        # deliberately absent from `pool_stats()` rather than force-fit.
        self._background_submitted = 0
        self._background_completed = 0
        self._critical_submitted = 0
        self._critical_completed = 0
        self._logger = logging.getLogger("App")
        # Resolved lazily (IConfig is normally registered by an extension
        # during boot, after this constructor already ran) and memoized —
        # this engine has no live config-reload story, so resolving once is
        # correct, not just an optimization.
        self._max_retained_tasks: int | None = None

    def _get_max_retained_tasks(self) -> int:
        if self._max_retained_tasks is not None:
            return self._max_retained_tasks

        limit = self._DEFAULT_MAX_RETAINED_TASKS
        try:
            config = self.context.container.resolve(IConfig)
            limit = config.get(
                self._MAX_RETAINED_TASKS_CONFIG_KEY,
                default=self._DEFAULT_MAX_RETAINED_TASKS,
                cast=int,
            )
        except Exception:
            # No IConfig registered (the common case for a minimal app) —
            # keep the built-in default rather than failing task cleanup.
            # Logged rather than swallowed: the common case and a genuinely
            # broken IConfig look identical from here, and only the log
            # tells them apart.
            self._logger.debug(
                "No usable IConfig for %s; keeping the built-in default of %d.",
                self._MAX_RETAINED_TASKS_CONFIG_KEY,
                self._DEFAULT_MAX_RETAINED_TASKS,
                exc_info=True,
            )

        self._max_retained_tasks = limit
        return limit

    def _emit(self, event_name: str, event_data: Any) -> None:
        try:
            self.context.event_bus.emit(event_name, event_data)
        except Exception as e:
            self.context.logger.error(f"Failed to emit event: {e}")

    def _cleanup_old_tasks(self) -> None:
        max_retained = self._get_max_retained_tasks()
        with self._lock:
            # Prevent memory leaks by capping the tracking list of finished tasks
            while len(self._finished_task_ids) > max_retained:
                tid = self._finished_task_ids.popleft()
                if tid in self.tasks:
                    del self.tasks[tid]

    def _make_pool_done_callback(self, critical: bool) -> Callable[[Any], None]:
        """@brief `EPIC-007B`: releases one pool's in-flight slot regardless of
        how the future finished."""

        def _on_done(_future: Any) -> None:
            with self._lock:
                if critical:
                    self._critical_completed += 1
                else:
                    self._background_completed += 1

        return _on_done

    def _wrap_sync(
        self, bg_task: BackgroundTask, fn: Callable[[], Any]
    ) -> Callable[[], Any]:
        def wrapper():
            # EPIC-005B requirement 2: a task-run span must reconstruct to the
            # same duration the task manager itself reports. It is opened and
            # closed around *exactly* the wrapped callable, so the span measures
            # the same work the status transitions bracket -- if the two ever
            # disagreed, the trace would be wrong and nothing built on it could
            # be trusted.
            recorder = self.context.recorder
            started = (
                recorder.span_begin(
                    TraceLane.TASK,
                    bg_task.name,
                    cat="run",
                    # The task id is a UUID *string*; `cid` is an int. It goes
                    # in `args` instead, which costs a dict per task run --
                    # affordable here in a way it would not be on the dispatch
                    # path, because a task run is already a heavyweight
                    # operation and two of these bracket the whole of it.
                    args={"task_id": bg_task.id},
                )
                if recorder is not None
                else 0
            )
            try:
                res = fn()
                bg_task.status = TaskState.COMPLETED
                self._emit(
                    TaskCompleted.event_name,
                    TaskCompleted(bg_task.id, bg_task.name),
                )
                return res
            except Exception as e:
                bg_task.status = TaskState.FAILED
                bg_task.error = e
                self._logger.error(f"Task '{bg_task.name}' failed: {e}")
                self._emit(
                    TaskFailed.event_name,
                    TaskFailed(bg_task.id, bg_task.name, e),
                )
                raise e
            finally:
                if recorder is not None:
                    recorder.span_end(
                        TraceLane.TASK,
                        bg_task.name,
                        started,
                        cat="run",
                        args={"task_id": bg_task.id},
                    )
                with self._lock:
                    self._finished_task_ids.append(bg_task.id)
                self._cleanup_old_tasks()

        return wrapper

    async def _wrap_coro(self, bg_task: BackgroundTask, coro: Any) -> Any:
        try:
            res = await coro
            bg_task.status = TaskState.COMPLETED
            self._emit(
                TaskCompleted.event_name, TaskCompleted(bg_task.id, bg_task.name)
            )
            return res
        except Exception as e:
            bg_task.status = TaskState.FAILED
            bg_task.error = e
            self._logger.error(f"Async task '{bg_task.name}' failed: {e}")
            self._emit(TaskFailed.event_name, TaskFailed(bg_task.id, bg_task.name, e))
            raise e
        finally:
            with self._lock:
                self._finished_task_ids.append(bg_task.id)
            self._cleanup_old_tasks()

    def spawn(
        self,
        callable_or_coro: Callable[..., Any] | Any,
        name: str | None = None,
        token: CancellationToken | None = None,
        critical: bool = False,
    ) -> BackgroundTask:
        """
        @brief Spawns a background execution (sync thread or async coroutine).
        @param callable_or_coro Callable function or coroutine object to run.
        @param name Optional descriptive task name.
        @param token Optional cancellation token.
        @param critical If True, runs on non-daemon critical thread pool with graceful shutdown timeout.
                        If False (default), runs on daemon background thread pool safe to kill on exit.
        """
        task_name = name or (
            callable_or_coro.__name__
            if hasattr(callable_or_coro, "__name__")
            else "UnnamedTask"
        )

        def _on_progress(val: float, msg: str):
            self._emit(
                TaskProgressUpdated.event_name,
                TaskProgressUpdated(bg_task.id, val, msg),
            )

        bg_task = BackgroundTask(
            task_name, token, critical=critical, on_progress_update=_on_progress
        )

        with self._lock:
            self.tasks[bg_task.id] = bg_task

        self._emit(TaskStarted.event_name, TaskStarted(bg_task.id, task_name))

        # Check if it's an async callable or a coroutine object
        if inspect.iscoroutinefunction(callable_or_coro) or inspect.iscoroutine(
            callable_or_coro
        ):
            # It's async
            coro = (
                callable_or_coro
                if inspect.iscoroutine(callable_or_coro)
                else callable_or_coro(bg_task.token)
            )
            bg_task.status = TaskState.RUNNING
            try:
                future = self.context.async_runtime.run_coroutine(
                    self._wrap_coro(bg_task, coro)
                )
                bg_task.future = future
            except Exception as e:
                bg_task.status = TaskState.FAILED
                bg_task.error = e
                self._emit(TaskFailed.event_name, TaskFailed(bg_task.id, task_name, e))
                with self._lock:
                    self._finished_task_ids.append(bg_task.id)
                self._cleanup_old_tasks()
                raise e
        else:
            # It's sync
            bg_task.status = TaskState.RUNNING
            try:
                sig = inspect.signature(callable_or_coro)
                if "token" in sig.parameters:

                    def fn():
                        return callable_or_coro(token=bg_task.token)
                else:

                    def fn():
                        return callable_or_coro()

                target_executor = (
                    self.critical_executor if critical else self.background_executor
                )
                with self._lock:
                    if critical:
                        self._critical_submitted += 1
                    else:
                        self._background_submitted += 1
                future = target_executor.submit(self._wrap_sync(bg_task, fn))
                # Not `_wrap_sync`'s own `finally`: a future cancelled before
                # it starts running never enters that body at all, which
                # would leave `in_flight` permanently inflated for every
                # cancel-before-start. `add_done_callback` fires on every
                # terminal state an executor future can reach -- completed,
                # raised, or cancelled -- so this is the one place that
                # cannot miss a completion.
                future.add_done_callback(self._make_pool_done_callback(critical))
                bg_task.future = future
            except Exception as e:
                bg_task.status = TaskState.FAILED
                bg_task.error = e
                self._emit(TaskFailed.event_name, TaskFailed(bg_task.id, task_name, e))
                with self._lock:
                    self._finished_task_ids.append(bg_task.id)
                self._cleanup_old_tasks()
                raise e

        return bg_task

    def get_active_tasks(self) -> list[ITaskHandle]:
        """
        @brief Returns a list of currently active (running or pending) background tasks.
        @return List of active ITaskHandle objects.
        """
        with self._lock:
            return [
                task
                for task in self.tasks.values()
                if task.status in (TaskState.RUNNING, TaskState.PENDING)
            ]

    def cancel_all(self) -> None:
        """
        @brief Cancels all currently running tasks.

        @details `task.cancel()` runs outside `self._lock` — found by `EPIC-007B`
        turning it from a latent hazard into a live deadlock: cancelling a future that
        has not yet started invokes its done callbacks *synchronously, on this thread*,
        and `_make_pool_done_callback`'s callback now acquires this same lock. Calling
        `.cancel()` while still holding the lock that its own callback needs is this
        thread deadlocking on its own non-reentrant `Lock`. The snapshot of which tasks
        to cancel is still taken under the lock — only the cancellation itself moves
        outside it.
        """
        with self._lock:
            running = [
                task for task in self.tasks.values() if task.status == TaskState.RUNNING
            ]
        for task in running:
            task.cancel()

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        @brief Gracefully stops all tasks and shuts down the thread pool executors.
        @details Critical tasks are given up to `timeout` seconds to complete gracefully.
                 Background daemon tasks are non-blockingly cancelled and shut down.
        """
        active_tasks = self.get_active_tasks()
        if active_tasks:
            task_descriptions = [
                f"'{t.name}' (id: {t.id}, status: {t.status.value if hasattr(t.status, 'value') else t.status})"
                for t in active_tasks
            ]
            self._logger.warning(
                f"TaskManager shutting down with {len(active_tasks)} active tasks still running: {', '.join(task_descriptions)}"
            )

        self.cancel_all()

        with self._lock:
            critical_futures = [
                t.future
                for t in self.tasks.values()
                if t.critical and t.status == TaskState.RUNNING and t.future is not None
            ]

        if critical_futures:
            wait(critical_futures, timeout=timeout)

        try:
            self.critical_executor.shutdown(wait=False, cancel_futures=True)
            self.background_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            self.critical_executor.shutdown(wait=False)
            self.background_executor.shutdown(wait=False)

    def snapshot(self) -> tuple[TaskSnapshot, ...]:
        """
        @brief Every retained task, frozen — `EPIC-007B`.

        @details Newest-first. Read under `self._lock`, same as `get_active_tasks()` —
        that bounds the dict from changing size mid-iteration, not each individual
        task's own field mutations, which a worker thread makes without acquiring this
        lock (`bg_task.status = ...` inside `_wrap_sync`). A field or two read a few
        nanoseconds apart from each other under the GIL is the same characteristic
        `get_active_tasks()` already has today, not a new one introduced here.
        """
        with self._lock:
            tasks = list(self.tasks.values())
        return tuple(
            TaskSnapshot(
                id=task.id,
                name=task.name,
                state=task.status,
                progress=task.progress,
                critical=task.critical,
                started_at=task.start_time,
                ended_at=task.end_time,
                error=str(task.error) if task.error is not None else None,
            )
            for task in reversed(tasks)
        )

    def pool_stats(self) -> tuple[PoolStats, ...]:
        """@brief Occupancy of the `background`/`critical` executors — `EPIC-007B`.
        See `PoolStats` for why `queue_depth` is derived rather than read from either
        executor's own private queue."""
        with self._lock:
            bg_submitted, bg_completed = (
                self._background_submitted,
                self._background_completed,
            )
            cr_submitted, cr_completed = (
                self._critical_submitted,
                self._critical_completed,
            )
        bg_in_flight = bg_submitted - bg_completed
        cr_in_flight = cr_submitted - cr_completed
        return (
            PoolStats(
                name="background",
                max_workers=self._BACKGROUND_MAX_WORKERS,
                in_flight=bg_in_flight,
                queue_depth=max(0, bg_in_flight - self._BACKGROUND_MAX_WORKERS),
                submitted=bg_submitted,
                completed=bg_completed,
            ),
            PoolStats(
                name="critical",
                max_workers=self._CRITICAL_MAX_WORKERS,
                in_flight=cr_in_flight,
                queue_depth=max(0, cr_in_flight - self._CRITICAL_MAX_WORKERS),
                submitted=cr_submitted,
                completed=cr_completed,
            ),
        )

    def max_retained_tasks(self) -> int:
        """@brief The configured retention limit `snapshot()` is bounded by —
        `EPIC-007C`. Delegates to the same resolution `_cleanup_old_tasks()`
        already uses, so the two can never disagree about the limit."""
        return self._get_max_retained_tasks()
