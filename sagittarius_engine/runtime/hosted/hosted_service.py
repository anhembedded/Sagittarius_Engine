from abc import ABC, abstractmethod

from sagittarius_engine.interfaces.i_engine_context import IEngineContext


class IHostedService(ABC):
    """
    @brief Interface for long-running engine components (Hosted Services).
    """

    @abstractmethod
    def start(self, context: IEngineContext) -> None:
        """
        @brief Starts the service.
        """
        pass

    @abstractmethod
    def stop(self, context: IEngineContext) -> None:
        """
        @brief Stops the service.
        """
        pass
