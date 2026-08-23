from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from typing import Protocol

from sagittarius_engine.infrastructure.logging.std_logger import StdLogger
from sagittarius_engine.interfaces import IConfig, ILogger
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_extension import IExtension


class ILoggerContext(Protocol):
    @property
    def container(self) -> IContainer: ...


class LoggerExtension(IExtension[ILoggerContext]):
    """
    @brief Extension for Logger setup.
    """

    def register(self, context: ILoggerContext) -> None:
        try:
            config: IConfig = context.container.resolve(IConfig)
        except Exception:
            config = None  # type: ignore[assignment]

        logger_instance = StdLogger(config)
        context.container.singleton(ILogger, logger_instance)

    def boot(self, context: ILoggerContext) -> None:
        pass

    def shutdown(self, context: ILoggerContext) -> None:
        pass
