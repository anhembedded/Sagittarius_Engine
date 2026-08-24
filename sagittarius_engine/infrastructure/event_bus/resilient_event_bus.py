import threading
from collections.abc import Callable
from typing import Any

from sagittarius_engine.infrastructure.event_bus.bus_logger import (
    resolve_bus_logger,
)
from sagittarius_engine.infrastructure.event_bus.handler_reporting import (
    report_handler_failure,
)
from sagittarius_engine.interfaces import IEventBus, ILogger


class ResilientEventBus(IEventBus):
    """
    @brief A Decorator for IEventBus that adds Retry mechanisms and a Dead Letter Queue (DLQ).

    @details If a handler throws an exception while processing an event, the ResilientEventBus
    will attempt to call the handler again (Retry). If the max retries are exceeded,
    the event is pushed into the DLQ for manual processing later (Reprocess).

    @par Tutorial / Usage Example:
    @code
    # Wrap a basic event bus
    base_bus = MemoryEventBus()
    safe_bus = ResilientEventBus(inner_bus=base_bus, max_retries=3)

    # If an emit consistently fails, it goes to the DLQ
    safe_bus.emit("some.event", data)

    # Inspect failed events
    failed_events = safe_bus.get_dlq()

    # Attempt to re-run the failed events
    safe_bus.reprocess()
    @endcode
    """

    def __init__(
        self, inner_bus: IEventBus, max_retries: int = 3, logger: ILogger | None = None
    ) -> None:
        """
        @brief Constructor.

        @param inner_bus The base event bus to decorate.
        @param max_retries The maximum number of retries before adding to DLQ.
        @param logger Optional logger instance.
        """
        self.inner_bus = inner_bus
        self.max_retries = max_retries
        self._dlq: list[tuple[str, Any, Callable, Exception]] = []
        self.logger = resolve_bus_logger(logger)

        self._wrapper_map: dict[tuple[str, Callable], Callable] = {}
        self._lock = threading.Lock()

    def emit(self, event_name_or_obj: str | Any, data: Any = None) -> None:
        """
        @brief Emits an event through the inner event bus.

        @param event_name_or_obj The name of the event or BaseEvent object.
        @param data The data payload.

        @details Deliberately does not log the dispatch itself — the inner bus
        does that, with the handler count for *this* event. This decorator
        used to re-derive the event name here purely to write its own log
        line, which meant every emit resolved the key twice and produced two
        records for one dispatch. Its job is retry and the dead-letter queue;
        tracing belongs to whichever bus actually holds the handlers.
        """
        self.inner_bus.emit(event_name_or_obj, data)

    def on(self, event_name_or_type: str | Any, handler: Callable[..., Any]) -> None:
        """
        @brief Registers a handler with retry and DLQ protection on the inner bus.

        @param event_name_or_type The name of the event or event class type.
        @param handler The callback function.
        """
        event_name = (
            event_name_or_type
            if isinstance(event_name_or_type, str)
            else getattr(event_name_or_type, "__name__", str(event_name_or_type))
        )

        with self._lock:
            key = (event_name, handler)
            if key in self._wrapper_map:
                return

            def resilient_wrapper(data: Any) -> None:
                for attempt in range(self.max_retries + 1):
                    try:
                        handler(data)
                        break
                    except Exception as e:
                        if attempt == self.max_retries:
                            #: Reported before the DLQ append, not instead of
                            #: it. The DLQ is a recovery mechanism — something
                            #: has to call `reprocess()` for it to matter — and
                            #: before this, a handler that exhausted its
                            #: retries left no log line at all, so a failure
                            #: parked in the DLQ was invisible until someone
                            #: thought to call `get_dlq()`.
                            report_handler_failure(self.logger, event_name, handler, e)
                            with self._lock:
                                self._dlq.append((event_name, data, handler, e))

            self._wrapper_map[key] = resilient_wrapper

        self.inner_bus.on(event_name_or_type, resilient_wrapper)

    def off(self, event_name_or_type: str | Any, handler: Callable[..., Any]) -> None:
        """
        @brief Unregisters a handler from the inner bus.

        @param event_name_or_type The name of the event or event class type.
        @param handler The callback function.
        """
        event_name = (
            event_name_or_type
            if isinstance(event_name_or_type, str)
            else getattr(event_name_or_type, "__name__", str(event_name_or_type))
        )

        with self._lock:
            key = (event_name, handler)
            wrapper = self._wrapper_map.pop(key, None)

        if wrapper:
            self.inner_bus.off(event_name_or_type, wrapper)

    def get_dlq(self) -> list[tuple[str, Any, Callable, Exception]]:
        """
        @brief Retrieves the Dead Letter Queue.
        @return A list of failed events stored in the DLQ.
        """
        with self._lock:
            return list(self._dlq)

    def reprocess(self) -> None:
        """
        @brief Attempts to reprocess all events currently in the DLQ.
        """
        with self._lock:
            current_dlq = self._dlq
            self._dlq = []
        for event_name, data, handler, _ in current_dlq:
            for attempt in range(self.max_retries + 1):
                try:
                    handler(data)
                    break
                except Exception as e:
                    if attempt == self.max_retries:
                        report_handler_failure(self.logger, event_name, handler, e)
                        with self._lock:
                            self._dlq.append((event_name, data, handler, e))
