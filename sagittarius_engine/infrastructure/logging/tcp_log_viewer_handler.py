import json
import logging
import queue
import socket
import threading
import time
from datetime import UTC, datetime
from typing import Any


class TcpLogViewerHandler(logging.Handler):
    """
    @brief Non-blocking TCP Logging Handler for Sagittarius LogViewer.

    @details Enqueues log records into a thread-safe Queue and streams them asynchronously
    over a TCP socket as newline-delimited JSON objects.
    If the LogViewer server is down or un-reachable, log events are dropped safely or retried
    in the background without blocking the main application threads.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9999,
        module_name: str = "sagittarius-app",
        max_queue_size: int = 10000,
    ) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self.module_name = module_name
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._seq = 0

        self._worker_thread = threading.Thread(
            target=self._network_worker,
            name="Sagittarius-TcpLogWorker",
            daemon=True,
        )
        self._worker_thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        """
        @brief Formats and enqueues a log record for non-blocking TCP transmission.
        """
        try:
            raw_extra = getattr(record, "extra", {})
            if isinstance(raw_extra, dict):
                extra_data = raw_extra.copy()
            else:
                extra_data = {"raw_extra": str(raw_extra)} if raw_extra else {}

            self._seq += 1
            index = extra_data.pop("index", self._seq)

            submodule = extra_data.pop("submodule", None)
            if (
                not submodule
                and hasattr(record, "submodule")
                and getattr(record, "submodule")
            ):
                submodule = getattr(record, "submodule")

            msg = record.getMessage()

            # Automatic inference if message starts with [SubmoduleName]
            if not submodule and msg.startswith("[") and "]" in msg:
                bracket_content = msg[1 : msg.find("]")]
                if " " not in bracket_content:
                    submodule = bracket_content

            if not submodule and record.name and record.name != "App":
                submodule = record.name

            dt = datetime.fromtimestamp(record.created, tz=UTC)

            payload: dict[str, Any] = {
                "index": index,
                "timestamp": dt.isoformat(),
                "level": record.levelname,
                "message": msg,
                "module": self.module_name,
                "submodule": submodule,
                "extra": extra_data,
            }

            self._queue.put_nowait(payload)
        except queue.Full:
            # Prevent memory overflow if LogViewer server is offline for an extended duration
            pass
        except Exception:
            self.handleError(record)

    def _network_worker(self) -> None:
        sock: socket.socket | None = None
        while not self._stop_event.is_set():
            try:
                payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            data_bytes = (json.dumps(payload) + "\n").encode("utf-8")
            sent = False

            while not sent and not self._stop_event.is_set():
                try:
                    if sock is None:
                        sock = socket.create_connection(
                            (self.host, self.port), timeout=2.0
                        )
                    sock.sendall(data_bytes)
                    sent = True
                except OSError:
                    if sock:
                        try:
                            sock.close()
                        except Exception as e:
                            import logging

                            logging.getLogger(__name__).error(
                                f"Socket close error: {e}"
                            )
                        sock = None
                    # Short pause before next attempt if connection lost
                    time.sleep(1.0)
                    break

        if sock:
            try:
                sock.close()
            except Exception as e:
                import logging

                logging.getLogger(__name__).error(f"Socket close error: {e}")

    def close(self) -> None:
        """
        @brief Signals worker thread to stop and closes handler.
        """
        self._stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        super().close()
