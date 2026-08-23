import inspect
import logging
import threading
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_task_manager import ITaskHandle, ITaskManager
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

    def __init__(self, context: Any) -> None:
        self.context = context
        self.tasks: dict[str, BackgroundTask] = {}
        self._finished_task_ids: deque[str] = deque()
        self.background_executor = ThreadPoolExecutor(
            max_workers=20,
            thread_name_prefix="SagittariusBgTask",
        )
        self.critical_executor = ThreadPoolExecutor(
            max_workers=10,
            thread_name_prefix="SagittariusCriticalTask",
        )
        # Backwards compatibility alias
        self.executor = self.background_executor
        self._lock = threading.Lock()
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
            pass

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

    def _wrap_sync(
        self, bg_task: BackgroundTask, fn: Callable[[], Any]
    ) -> Callable[[], Any]:
        def wrapper():
            try:
                res = fn()
                bg_task.status = TaskState.COMPLETED
                self._emit(
                    "runtime.tasks.completed",
                    TaskCompleted(bg_task.id, bg_task.name),
                )
                return res
            except Exception as e:
                bg_task.status = TaskState.FAILED
                bg_task.error = e
                self._logger.error(f"Task '{bg_task.name}' failed: {e}")
                self._emit(
                    "runtime.tasks.failed",
                    TaskFailed(bg_task.id, bg_task.name, e),
                )
                raise e
            finally:
                with self._lock:
                    self._finished_task_ids.append(bg_task.id)
                self._cleanup_old_tasks()

        return wrapper

    async def _wrap_coro(self, bg_task: BackgroundTask, coro: Any) -> Any:
        try:
            res = await coro
            bg_task.status = TaskState.COMPLETED
            self._emit(
                "runtime.tasks.completed", TaskCompleted(bg_task.id, bg_task.name)
            )
            return res
        except Exception as e:
            bg_task.status = TaskState.FAILED
            bg_task.error = e
            self._logger.error(f"Async task '{bg_task.name}' failed: {e}")
            self._emit("runtime.tasks.failed", TaskFailed(bg_task.id, bg_task.name, e))
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
                "runtime.tasks.progress", TaskProgressUpdated(bg_task.id, val, msg)
            )

        bg_task = BackgroundTask(
            task_name, token, critical=critical, on_progress_update=_on_progress
        )

        with self._lock:
            self.tasks[bg_task.id] = bg_task

        self._emit("runtime.tasks.started", TaskStarted(bg_task.id, task_name))

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
                self._emit("runtime.tasks.failed", TaskFailed(bg_task.id, task_name, e))
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
                future = target_executor.submit(self._wrap_sync(bg_task, fn))
                bg_task.future = future
            except Exception as e:
                bg_task.status = TaskState.FAILED
                bg_task.error = e
                self._emit("runtime.tasks.failed", TaskFailed(bg_task.id, task_name, e))
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
        """
        with self._lock:
            for task in self.tasks.values():
                if task.status == TaskState.RUNNING:
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
            from concurrent.futures import wait

            wait(critical_futures, timeout=timeout)

        try:
            self.critical_executor.shutdown(wait=False, cancel_futures=True)
            self.background_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            self.critical_executor.shutdown(wait=False)
            self.background_executor.shutdown(wait=False)
