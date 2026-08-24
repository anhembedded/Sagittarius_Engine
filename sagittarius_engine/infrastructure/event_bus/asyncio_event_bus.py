import asyncio
import inspect
import threading
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
from sagittarius_engine.interfaces import IAsyncEventBus, ILogger


class AsyncioEventBus(IAsyncEventBus):
    """
    @brief Asynchronous EventBus implementation using asyncio.

    @details Allows handlers to be standard sync functions or async coroutines.
    Handlers are awaited sequentially within the asyncio event loop.
    """

    def __init__(self, logger: ILogger | None = None) -> None:
        """
        @brief Constructor.
        @param logger Optional logger instance.
        """
        self._handlers: dict[str, tuple[Callable, ...]] = {}
        self._lock = threading.Lock()
        self.logger = resolve_bus_logger(logger)

    async def emit(self, event_name: str, data: Any = None) -> None:
        """
        @brief Asynchronously emits an event to all listening handlers sequentially.

        @param event_name The name of the event.
        @param data The data payload.
        """
        # ⚡ Bolt: Lock-free read using Copy-On-Write pattern to reduce contention
        handlers_snapshot = self._handlers.get(event_name, ())

        log_event_emitted(self.logger, event_name, len(handlers_snapshot))

        for handler in handlers_snapshot:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except asyncio.CancelledError as e:
                #: Caught separately and NOT re-raised, matching this bus's
                #: existing behaviour: one cancelled handler must not cancel
                #: the fan-out to its siblings. Reported through the same path
                #: as any other handler failure so it cannot go unnoticed.
                report_handler_failure(self.logger, event_name, handler, e)
            except Exception as e:
                report_handler_failure(self.logger, event_name, handler, e)

    def on(self, event_name: str, handler: Callable) -> None:
        """
        @brief Registers a handler.

        @param event_name The name of the event.
        @param handler The callback function (can be sync or async).
        """
        with self._lock:
            current_handlers = self._handlers.get(event_name, ())
            if handler not in current_handlers:
                self._handlers[event_name] = current_handlers + (handler,)

    def off(self, event_name: str, handler: Callable) -> None:
        """
        @brief Unregisters a handler.

        @param event_name The name of the event.
        @param handler The callback function to remove.
        """
        with self._lock:
            if event_name in self._handlers and handler in self._handlers[event_name]:
                self._handlers[event_name] = tuple(
                    h for h in self._handlers[event_name] if h != handler
                )
