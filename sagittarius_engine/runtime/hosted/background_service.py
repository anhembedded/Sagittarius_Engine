from abc import abstractmethod

from sagittarius_engine.interfaces import IEngineContext, ITaskHandle
from sagittarius_engine.runtime.hosted.hosted_service import IHostedService
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


class BackgroundService(IHostedService):
    """
    @brief Base abstract class for long-running background Hosted Services.

    @details
    Framework Design Pattern (Template Method Pattern):
    Automatically spawns a non-blocking background thread/task via `context.tasks.spawn()`,
    holds a strongly-typed `ITaskHandle`, manages `CancellationToken` lifecycle,
    and provides safe graceful shutdown when the Engine stops.

    Subclasses only need to implement the abstract `run(self, token: CancellationToken)` method!
    """

    def __init__(self) -> None:
        self.token = CancellationToken()
        self.task: ITaskHandle | None = None

    def start(self, context: IEngineContext) -> None:
        """
        @brief Automatically spawns background thread running the subclass `run()` loop.
        """
        self.task = context.tasks.spawn(
            self._run_wrapper, name=self.__class__.__name__, token=self.token
        )

    def _run_wrapper(self, token: CancellationToken) -> None:
        self.run(token)

    @abstractmethod
    def run(self, token: CancellationToken) -> None:
        """
        @brief Subclasses override this method to write their continuous execution loop.
        @param token CancellationToken used to cooperatively check `while not token.is_cancelled():`.
        """
        pass

    def stop(self, context: IEngineContext) -> None:
        """
        @brief Signals cancellation token to stop background execution.
        """
        self.token.cancel()

    def wait_for_exit(self) -> None:
        """
        @brief Blocks until background thread execution completes.
        """
        if self.task and self.task.future:
            try:
                self.task.future.result()
            except Exception as e:
                import logging

                logging.getLogger(__name__).error(
                    f"Error in background service task: {e}"
                )
