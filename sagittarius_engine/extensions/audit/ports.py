from abc import ABC, abstractmethod
from typing import Any


class ITelemetryBroadcaster(ABC):
    """
    Abstract port for broadcasting telemetry data to connected clients.
    """

    @abstractmethod
    def start(self) -> None:
        """Start the broadcaster service."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the broadcaster service."""
        ...

    @abstractmethod
    def broadcast(self, event_name: str, payload: dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.

        Args:
            event_name: The type/name of the event.
            payload: The data to send.
        """
        ...
