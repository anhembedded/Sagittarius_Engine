import logging
import queue
import threading
from multiprocessing.queues import Queue

from sagittarius_engine.interfaces.i_logger import ILogger


class IPCBroker:
    """
    @brief Broker for events to multiple subscriber queues.
    """

    def __init__(self, publish_queue: Queue, logger: ILogger | None = None):
        self._publish_queue = publish_queue
        self._subscriber_queues: list[Queue] = []
        self._logger = logger
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def add_subscriber(self, sub_queue: Queue) -> None:
        """Adds a subscriber queue to receive broadcasted events."""
        with self._lock:
            if sub_queue not in self._subscriber_queues:
                self._subscriber_queues.append(sub_queue)

    def remove_subscriber(self, sub_queue: Queue) -> None:
        """Removes a subscriber queue."""
        with self._lock:
            if sub_queue in self._subscriber_queues:
                self._subscriber_queues.remove(sub_queue)

    def start(self) -> None:
        """Starts the broker loop in a background daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="IPCBrokerThread"
        )
        self._thread.start()
        if self._logger:
            self._logger.info("IPCBroker started.")

    def stop(self) -> None:
        """Stops the broker loop gracefully."""
        self._stop_event.set()
        try:
            self._publish_queue.put(("_STOP_", None))
        except Exception as e:
            if self._logger:
                self._logger.error(f"Error stopping IPCBroker: {e}")
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._logger:
            self._logger.info("IPCBroker stopped.")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                message = self._publish_queue.get(timeout=0.1)
                if (
                    isinstance(message, tuple)
                    and len(message) == 2
                    and (message[0] == "_STOP_")
                ):
                    break
                event_name, data = message
                with self._lock:
                    for sub_queue in self._subscriber_queues:
                        try:
                            sub_queue.put((event_name, data))
                        except Exception as e:
                            if self._logger:
                                self._logger.error(
                                    f"Failed to route event {event_name} to a subscriber: {e}"
                                )
                            else:
                                logging.error(
                                    f"Failed to route event {event_name} to a subscriber: {e}"
                                )
            except queue.Empty:
                continue
            except Exception as e:
                if self._logger:
                    self._logger.error(f"IPCBroker encountered an error: {e}")
                else:
                    logging.error(f"IPCBroker encountered an error: {e}")
