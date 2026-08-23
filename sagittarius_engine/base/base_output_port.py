from typing import Any

from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.interfaces.i_output_port import IOutputPort


class BaseOutputPort(IOutputPort):
    """
    @brief Base class for output ports.
    """

    def __init__(self, logger: ILogger | None = None) -> None:
        self.logger = logger

    def present(self, result: Any) -> None:
        """
        @brief Presents the result. Logs if logger exists, else prints.
        """
        if self.logger:
            self.logger.info(f"Result: {result}")
        else:
            print(result)

    def present_error(self, error: Exception) -> None:
        """
        @brief Presents the error. Logs if logger exists, else prints.
        """
        if self.logger:
            self.logger.error(f"Error: {error}")
        else:
            print(f"Error: {error}")
