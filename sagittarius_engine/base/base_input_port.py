from typing import Any

from sagittarius_engine.interfaces.i_input_port import IInputPort
from sagittarius_engine.interfaces.i_logger import ILogger


class BaseInputPort(IInputPort):
    """
    @brief Base class for input ports.
    """

    def __init__(self, logger: ILogger | None = None) -> None:
        self.logger = logger

    def receive(self) -> dict[str, Any]:
        """
        @brief Receives input. To be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement receive()")
