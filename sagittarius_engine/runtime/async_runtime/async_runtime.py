import asyncio
import concurrent.futures
import logging
import threading
from collections.abc import Coroutine
from typing import Any

#: Extra wait on the drain's own future beyond the drain's `timeout`, so the
#: drain reports its own timeout instead of this thread giving up first.
_DRAIN_RESULT_MARGIN_SECONDS = 1.0


class AsyncRuntime:
    """
    @brief Manages the lifecycle of a background asyncio event loop on a dedicated thread.
    """

    def __init__(self, context: Any) -> None:
        self.context = context
        self.loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._logger = logging.getLogger("App")

    def start(self) -> None:
        """
        @brief Starts the background event loop.
        """
        if self._thread is not None:
            return

        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="AsyncRuntimeLoop", daemon=True
        )
        self._thread.start()
        self._logger.info("AsyncRuntime event loop started on background thread.")

    def _run_loop(self) -> None:
        if self.loop is not None:
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()

    def run_coroutine(self, coro: Coroutine) -> Any:
        """
        @brief Safely schedules a coroutine to run on the background loop from any thread.
        @return A concurrent.futures.Future representing the result of the coroutine.
        """
        if self.loop is None or not self.loop.is_running():
            raise RuntimeError("AsyncRuntime loop is not running")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self, timeout: float = 5.0) -> None:
        """
        @brief Stops and closes the background event loop gracefully.

        @details `BUG-014`: this used to join with a fixed timeout and then
        unconditionally clear `self._thread` and `close()` the loop, whether or not
        the background thread's own `run_forever()` had actually returned. Closing a
        loop while another thread is still iterating it is unsafe in asyncio (at best
        a `RuntimeError`, at worst native-level corruption — a live suspect for this
        bug's segfaults, not just its leaked threads). A thread still alive after
        `timeout` now stops this method before `close()` ever runs, and leaves
        `self._thread`/`self.loop` set rather than discarding them, so the state
        stays honest and a second `stop()` call can retry.

        `BUG-017`: the loop is drained before it stops (`_drain`). Cancelling a
        task only after its loop had stopped meant it never ran again, so every
        pending `finally` (an `aiohttp` session's close, a websocket's) was
        dropped and the task was destroyed while `cancelling`.
        """
        if self.loop is None:
            return

        self._logger.info("Stopping AsyncRuntime event loop...")
        self._drain(timeout)
        self.loop.call_soon_threadsafe(self.loop.stop)

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                self._logger.error(
                    "AsyncRuntime event loop thread did not stop within %ss — "
                    "leaving it and the loop tracked rather than closing a loop "
                    "still running on another thread; call stop() again to retry.",
                    timeout,
                )
                return
            self._thread = None

        try:
            pending = asyncio.all_tasks(self.loop)
            if pending:
                for task in pending:
                    task.cancel()
        except (RuntimeError, asyncio.InvalidStateError) as e:
            self._logger.warning(
                f"[AsyncRuntime] Error cancelling pending tasks during stop: {e}"
            )

        self.loop.close()
        self.loop = None
        self._logger.info("AsyncRuntime event loop stopped.")

    def _drain(self, timeout: float) -> None:
        """
        @brief Cancels every task on the running loop and waits, up to `timeout`,
        for each to finish its cancellation, then shuts down async generators.

        @details A task already `cancelling()` is not cancelled again: a second
        cancel would abort the `await` inside its `finally`, the very cleanup this
        exists to let run. Skipped when the loop is not running, or when called
        from the loop's own thread, where waiting on the loop would deadlock.
        """
        loop = self.loop
        if loop is None or not loop.is_running():
            return
        if self._thread is not None and threading.current_thread() is self._thread:
            return

        async def drain() -> None:
            current = asyncio.current_task()
            tasks = [task for task in asyncio.all_tasks() if task is not current]
            for task in tasks:
                if not task.cancelling():
                    task.cancel()
            if tasks:
                _, still_pending = await asyncio.wait(tasks, timeout=timeout)
                if still_pending:
                    self._logger.warning(
                        "AsyncRuntime: %d task(s) did not finish cancelling within "
                        "%ss and are left to the loop's close: %s",
                        len(still_pending),
                        timeout,
                        ", ".join(sorted(task.get_name() for task in still_pending)),
                    )
            await loop.shutdown_asyncgens()

        future = asyncio.run_coroutine_threadsafe(drain(), loop)
        try:
            future.result(timeout + _DRAIN_RESULT_MARGIN_SECONDS)
        except concurrent.futures.TimeoutError:
            future.cancel()
            self._logger.warning(
                "AsyncRuntime: draining the loop did not finish within %ss.", timeout
            )
