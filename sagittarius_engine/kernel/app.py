import threading
from collections.abc import Callable
from typing import Any, TypeVar

from sagittarius_engine.exceptions import ModuleRegistrationError
from sagittarius_engine.interfaces import (
    IContainer,
    IEventBus,
    IExtension,
    ILogger,
    IMiddleware,
    IModule,
)
from sagittarius_engine.interfaces.i_dispatchable import IDispatchable
from sagittarius_engine.kernel.context import EngineContext
from sagittarius_engine.kernel.lifecycle import EngineLifecycle
from sagittarius_engine.kernel.middleware_pipeline import MiddlewarePipeline

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


class App:
    """
    @brief The public façade of the Sagittarius Engine.

    @details App delegates runtime operations to EngineContext.
    """

    def __init__(self, container: IContainer, event_bus: IEventBus) -> None:
        """
        @brief Initializes the application with the core ports.

        @param container The dependency injection container.
        @param event_bus The event bus.
        """
        self.context = EngineContext(self, container, event_bus)

    @property
    def container(self) -> IContainer:
        return self.context.container

    @property
    def event_bus(self) -> IEventBus:
        return self.context.event_bus

    @property
    def modules(self) -> list[IExtension[Any]]:
        return self.context.modules

    @property
    def pipeline(self) -> MiddlewarePipeline:
        return self.context.middleware_pipeline

    @property
    def lifecycle(self) -> EngineLifecycle:
        return self.context.lifecycle

    def use(self, extension_or_module: IExtension[Any] | IModule) -> None:
        """
        @brief Manually adds an Extension or Module to the App.
        """
        try:
            self.context.extension_manager.register(extension_or_module)
        except TypeError as e:
            raise ModuleRegistrationError(str(e)) from e

    def use_middleware(self, middleware_instance: IMiddleware) -> None:
        """
        @brief Registers a Middleware for the application.
        @param middleware_instance The middleware instance.
        """
        self.context.middleware_pipeline.add(middleware_instance)

    def _get_logger(self) -> ILogger:
        return self.context.logger

    def boot(self, auto_discover: str | None = None) -> None:
        """
        @brief Boots the application.
        """
        self.context.bootstrap.boot(auto_discover)

    def dispatch(
        self, handler_class: type[IDispatchable], input_dto: object | None = None
    ) -> Any:
        """
        @brief Dispatches a command or query through the Middleware Pipeline.

        @param handler_class Any class implementing IDispatchable (ICommand, IQuery, or custom handler).
        @param input_dto Optional DTO to pass to the handler's execute() method.
        @return The result of the dispatched handler.
        """
        return self.context.dispatcher.dispatch(handler_class, input_dto)

    def execute(self, command_class: type, input_dto: object | None = None) -> Any:
        """
        @brief Deprecated. Use dispatch instead.
        """
        import warnings

        warnings.warn(
            "App.execute is deprecated. Use App.dispatch instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.dispatch(command_class, input_dto)

    def query(self, query_class: type, input_dto: object | None = None) -> Any:
        """
        @brief Deprecated. Use dispatch instead.
        """
        import warnings

        warnings.warn(
            "App.query is deprecated. Use App.dispatch instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.dispatch(query_class, input_dto)

    _DEFAULT_STOP_STEP_TIMEOUT_SECONDS = 10.0

    def _run_stop_step(
        self, step_name: str, fn: Callable[[], None], timeout: float, logger: ILogger
    ) -> None:
        """
        @brief Runs one shutdown step on a daemon thread, bounded by `timeout`.

        @details A step that hangs (e.g. a rogue extension's `stop()`) must not block
        every step after it — `App.stop()` has to always complete. The step's own
        thread is left to finish or hang in the background as a daemon; it cannot be
        forcibly killed, so a hung step is logged and the sequence moves on rather
        than waiting forever.
        """
        outcome: dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                fn()
            except Exception as e:  # noqa: BLE001 - reported below, not swallowed
                outcome["error"] = e

        thread = threading.Thread(
            target=_runner, name=f"AppStop-{step_name}", daemon=True
        )
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            logger.error(
                f"'{step_name}' did not stop within {timeout}s — continuing shutdown "
                "without waiting for it further"
            )
            return

        error = outcome.get("error")
        if error is not None:
            logger.error(f"Error stopping {step_name}: {error}")

    def stop(self, step_timeout: float = _DEFAULT_STOP_STEP_TIMEOUT_SECONDS) -> None:
        """
        @brief Shuts down the application gracefully.
        @details Stops the scheduler, hosted services, extensions, task manager, and
        async runtime in reverse order. Each step is bounded by `step_timeout` seconds
        so a single hanging step cannot block the rest of shutdown indefinitely.
        @param step_timeout Maximum seconds to wait for each individual step.
        """
        if self.context.lifecycle.is_stopping or self.context.lifecycle.is_stopped:
            return

        logger = self._get_logger()
        logger.info("App is stopping gracefully...")

        self.context.lifecycle.set_stopping()

        def _shutdown_event_bus() -> None:
            bus = self.context.event_bus
            if hasattr(bus, "shutdown") and callable(getattr(bus, "shutdown")):
                bus.shutdown()
            elif hasattr(bus, "dispose") and callable(getattr(bus, "dispose")):
                bus.dispose()

        steps: list[tuple[str, Callable[[], None]]] = [
            ("scheduler", self.context.scheduler.stop),
            ("hosted services", self.context.hosted_services.stop),
            ("extensions", self.context.extension_manager.stop_and_dispose),
            ("task manager", self.context.tasks.shutdown),
            ("async runtime", self.context.async_runtime.stop),
            ("event bus", _shutdown_event_bus),
        ]
        for step_name, fn in steps:
            self._run_stop_step(step_name, fn, step_timeout, logger)

        self.context.lifecycle.set_stopped()
        logger.info("App stopped.")
