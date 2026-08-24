import concurrent.futures
from collections.abc import Callable
from typing import Any

from sagittarius_engine.infrastructure.event_bus.bus_logger import (
    resolve_bus_logger,
)
from sagittarius_engine.infrastructure.event_bus.dispatch_trace import (
    log_event_emitted,
)
from sagittarius_engine.infrastructure.event_bus.handler_reporting import (
    report_handler_failure,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces import IEventBus, ILogger


class ThreadPoolEventBus(IEventBus):
    """
    @brief EventBus implementation that executes handlers in a ThreadPoolExecutor.

    @details Internally uses a thread-safe MemoryEventBus to manage handlers.
    When an event is emitted, handlers are submitted to a thread pool for execution.
    """

    def __init__(self, max_workers: int = 4, logger: ILogger | None = None) -> None:
        """
        @brief Constructor.
        @param max_workers Maximum number of threads in the pool.
        @param logger Optional logger instance.
        """
        #: The inner bus only stores the handler registry here — this class
        #: reads that registry and dispatches to the pool itself, never calling
        #: `inner.emit()`, so the inner bus never logs and there is no
        #: double-reporting.
        self._inner_bus = MemoryEventBus(logger=None)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.logger = resolve_bus_logger(logger)

    def emit(self, event_name_or_obj: str | Any, data: Any = None) -> None:
        """
        @brief Emits an event, executing its handlers concurrently in a thread pool.

        @param event_name_or_obj The name of the event or BaseEvent object.
        @param data The data payload.
        """
        if isinstance(event_name_or_obj, str):
            event_name = event_name_or_obj
            payload = data
        else:
            event_name = (
                getattr(
                    event_name_or_obj,
                    "event_name",
                    type(event_name_or_obj).__qualname__,
                )
                or type(event_name_or_obj).__qualname__
            )
            payload = data if data is not None else event_name_or_obj
        # Public handler access without inspecting private state
        if hasattr(self._inner_bus, "get_handlers"):
            handlers_snapshot = self._inner_bus.get_handlers(
                event_name_or_obj
                if not isinstance(event_name_or_obj, str)
                else event_name
            )
        else:
            handlers_snapshot = getattr(self._inner_bus, "_handlers", {}).get(
                event_name, ()
            )

        log_event_emitted(self.logger, event_name, len(handlers_snapshot))

        for handler in handlers_snapshot:
            future = self._executor.submit(handler, payload)

            def _report(f, event=event_name, h=handler):
                try:
                    f.result()
                except Exception as exc:
                    #: Re-raised inside this `except` so that
                    #: `report_handler_failure`'s `traceback.format_exc()` has
                    #: a live exception context to read. `Future.result()`
                    #: re-raises the original exception with its original
                    #: traceback attached, so the report still points at where
                    #: the handler actually failed on the worker thread, not
                    #: at this callback.
                    report_handler_failure(self.logger, event, h, exc)

            future.add_done_callback(_report)

    def on(self, event_name_or_type: str | Any, handler: Callable[..., Any]) -> None:
        """
        @brief Registers a handler.

        @param event_name_or_type The name of the event or event type.
        @param handler The callback function.
        """
        self._inner_bus.on(event_name_or_type, handler)

    def off(self, event_name_or_type: str | Any, handler: Callable[..., Any]) -> None:
        """
        @brief Unregisters a handler.

        @param event_name_or_type The name of the event or event type.
        @param handler The callback function to remove.
        """
        self._inner_bus.off(event_name_or_type, handler)

    def shutdown(self, wait: bool = True) -> None:
        """
        @brief Shuts down the thread pool executor.

        @param wait Whether to wait for pending futures to complete.
        """
        self._executor.shutdown(wait=wait)

    def get_handlers(
        self, event_name_or_type: str | Any
    ) -> tuple[Callable[..., Any], ...]:
        """
        @brief Returns registered handlers for an event.
        """
        if hasattr(self._inner_bus, "get_handlers"):
            return self._inner_bus.get_handlers(event_name_or_type)
        return ()
