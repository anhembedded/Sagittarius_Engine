from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class IRealtimeConnector(ABC):
    """
    Abstract port for receiving real-time data from external sources.
    This can be implemented by WebSockets, IPC, ZeroMQ, etc.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish the connection."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    def on_message_received(self, callback: Callable[[Any], None]) -> None:
        """
        Register a callback to handle incoming messages.

        Args:
            callback: A function that takes the raw message payload.
        """
        ...
