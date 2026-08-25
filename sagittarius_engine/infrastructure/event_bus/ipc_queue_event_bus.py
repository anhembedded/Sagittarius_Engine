import logging
import queue
import threading
from collections.abc import Callable, Mapping
from multiprocessing.queues import Queue
from typing import Any

from sagittarius_engine.infrastructure.event_bus.bus_logger import (
    resolve_bus_logger,
)
from sagittarius_engine.infrastructure.event_bus.handler_reporting import (
    report_handler_failure,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger


class IPCQueueEventBus(IEventBus):
    """
    @brief IPC Event Bus that uses Queue for cross-process Pub/Sub.
    """

    def __init__(
        self,
        subscriber_queue: Queue | None = None,
        publish_queue: Queue | None = None,
        logger: ILogger | None = None,
    ):
        self._subscriber_queue = subscriber_queue
        self._publish_queue = publish_queue
        self._logger = logger
        self._handlers: dict[str, tuple[Callable, ...]] = {}
        self._handlers_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def emit(self, event_name_or_obj: str | Any, data: Any = None) -> None:
        """
        @brief Publishes an event to the shared publish queue.
        """
        if isinstance(event_name_or_obj, str):
            event_name = event_name_or_obj
            payload = data
        else:
            event_name = type(event_name_or_obj).__qualname__
            payload = data if data is not None else event_name_or_obj
        if not self._publish_queue:
            if self._logger:
                self._logger.warning(
                    f"Cannot emit '{event_name}': publish_queue is None."
                )
            else:
                logging.warning(f"Cannot emit '{event_name}': publish_queue is None.")
            return
        try:
            self._publish_queue.put((event_name, payload))
        except Exception as e:
            if self._logger:
                self._logger.error(
                    f"Failed to emit event '{event_name}' to publish_queue: {e}"
                )
            else:
                logging.error(
                    f"Failed to emit event '{event_name}' to publish_queue: {e}"
                )

    def on(self, event_name_or_type: str | Any, handler: Callable[..., Any]) -> None:
        """
        @brief Subscribes a local handler to an event.
        """
        event_name = (
            event_name_or_type
            if isinstance(event_name_or_type, str)
            else getattr(event_name_or_type, "__name__", str(event_name_or_type))
        )
        with self._handlers_lock:
            current_handlers = self._handlers.get(event_name, ())
            if handler not in current_handlers:
                self._handlers[event_name] = current_handlers + (handler,)

    def subscriptions(self) -> Mapping[str, tuple[Callable[..., Any], ...]]:
        """
        @brief Every event name with at least one handler, mapped to them.

        @details Taken under the same lock `on()`/`off()` write with, so the
        snapshot cannot straddle a concurrent subscription change.

        `off()` leaves an empty tuple behind rather than deleting the key; an
        emptied name is not a subscription, so those are dropped here. Without
        that, a name that briefly had a handler would look subscribed forever,
        and `EPIC-006`'s registry-vs-bus diff would report it as live.
        """
        with self._handlers_lock:
            return {
                name: handlers for name, handlers in self._handlers.items() if handlers
            }

    def off(self, event_name_or_type: str | Any, handler: Callable[..., Any]) -> None:
        """
        @brief Unsubscribes a local handler from an event.
        """
        event_name = (
            event_name_or_type
            if isinstance(event_name_or_type, str)
            else getattr(event_name_or_type, "__name__", str(event_name_or_type))
        )
        with self._handlers_lock:
            if event_name in self._handlers and handler in self._handlers[event_name]:
                self._handlers[event_name] = tuple(
                    h for h in self._handlers[event_name] if h != handler
                )

    def start(self) -> None:
        """
        @brief Starts the daemon thread to listen on the subscriber queue.
        """
        if not self._subscriber_queue:
            if self._logger:
                self._logger.warning(
                    "No subscriber_queue provided; IPCQueueEventBus will not listen for events."
                )
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="IPCQueueEventBusListener"
        )
        self._thread.start()
        if self._logger:
            self._logger.info("IPCQueueEventBus listener started.")

    def stop(self) -> None:
        """
        @brief Stops the listener daemon thread gracefully.
        """
        self._stop_event.set()
        if self._subscriber_queue:
            try:
                self._subscriber_queue.put(("_STOP_", None))
            except Exception as e:
                if self._logger:
                    self._logger.error(f"Error stopping IPCQueueEventBus: {e}")
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._logger:
            self._logger.info("IPCQueueEventBus listener stopped.")

    def _run(self) -> None:
        if not self._subscriber_queue:
            return
        while not self._stop_event.is_set():
            try:
                message = self._subscriber_queue.get(timeout=0.1)
                if (
                    isinstance(message, tuple)
                    and len(message) == 2
                    and (message[0] == "_STOP_")
                ):
                    break
                event_name, data = message
                self._dispatch(event_name, data)
            except queue.Empty:
                continue
            except Exception as e:
                if self._logger:
                    self._logger.error(f"IPCQueueEventBus listener error: {e}")

    def _dispatch(self, event_name: str, data: Any) -> None:
        """Calls all local handlers registered for the event.

        @details Handler failures are reported through the shared
        `handler_reporting` path rather than this class's own
        `if self._logger:` idiom. Everywhere else in this file that guard has
        an explicit `else:` branch falling back to the standard `logging`
        module — this one method did not, so a handler exception here was the
        single place in the class that could disappear without a trace when no
        `ILogger` was injected."""
        # ⚡ Bolt: Lock-free read using Copy-On-Write pattern to reduce contention
        handlers = self._handlers.get(event_name, ())
        logger = resolve_bus_logger(self._logger)
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                report_handler_failure(logger, event_name, handler, e)
