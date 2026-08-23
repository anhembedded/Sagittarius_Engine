import asyncio
import logging
import threading
from collections.abc import Coroutine
from typing import Any


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

    def stop(self) -> None:
        """
        @brief Stops and closes the background event loop gracefully.
        """
        if self.loop is None:
            return

        self._logger.info("Stopping AsyncRuntime event loop...")
        self.loop.call_soon_threadsafe(self.loop.stop)

        if self._thread is not None:
            self._thread.join(timeout=5.0)
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
