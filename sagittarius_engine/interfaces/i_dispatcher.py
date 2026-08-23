from abc import ABC, abstractmethod
from typing import Any

from sagittarius_engine.interfaces.i_dispatchable import IDispatchable


class IDispatcher(ABC):
    """
    @brief Interface for dispatching commands and queries through the engine.
    """

    @abstractmethod
    def dispatch(
        self,
        handler_class: type[IDispatchable],
        input_dto: object | None = None,
    ) -> Any:
        """
        @brief Dispatches a handler (command or query).
        """
        ...
