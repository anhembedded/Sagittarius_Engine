from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sagittarius_engine.kernel.app import App
from sagittarius_engine.interfaces import (
    IConfig,
    IContainer,
    IEventBus,
    ILogger,
    ITaskManager,
)
from sagittarius_engine.kernel.bootstrap import Bootstrap
from sagittarius_engine.kernel.dispatcher import Dispatcher
from sagittarius_engine.kernel.extension_manager import ExtensionManager
from sagittarius_engine.kernel.i_kernel_context import IKernelContext
from sagittarius_engine.kernel.lifecycle import EngineLifecycle
from sagittarius_engine.kernel.middleware_pipeline import MiddlewarePipeline
from sagittarius_engine.kernel.module_loader import ModuleLoader


class EngineContext(IKernelContext):
    """The runtime composition root of the Sagittarius Engine.

    It owns every engine service and coordinates communication between engine subsystems.
    It does not contain application or business logic.
    """

    def __init__(self, app: "App", container: IContainer, event_bus: IEventBus) -> None:
        self.app = app
        self._container = container
        self._event_bus = event_bus
        self.middleware_pipeline = MiddlewarePipeline()
        self.extension_manager = ExtensionManager(self)

        # Instantiating subsystems with shared EngineContext
        self.lifecycle = EngineLifecycle(self)
        self.module_loader = ModuleLoader(self)
        self.bootstrap = Bootstrap(self)
        self.dispatcher = Dispatcher(self)

        # Runtime Infrastructure
        from sagittarius_engine.runtime.async_runtime.async_runtime import AsyncRuntime
        from sagittarius_engine.runtime.hosted.hosted_service_manager import (
            HostedServiceManager,
        )
        from sagittarius_engine.runtime.scheduler.scheduler import Scheduler
        from sagittarius_engine.runtime.tasks.task_manager import TaskManager

        self.async_runtime = AsyncRuntime(self)
        self._tasks: ITaskManager = TaskManager(self)
        self.scheduler = Scheduler(self)
        self.hosted_services = HostedServiceManager(self)

        # Register runtime in container as singletons
        self._container.singleton(AsyncRuntime, self.async_runtime)
        self._container.singleton(TaskManager, self._tasks)
        self._container.singleton(Scheduler, self.scheduler)
        self._container.singleton(HostedServiceManager, self.hosted_services)

        # Register core engine interfaces
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher

        self._container.singleton(IDispatcher, self.dispatcher)

    @property
    def container(self) -> IContainer:
        return self._container

    @container.setter
    def container(self, value: IContainer) -> None:
        self._container = value

    @property
    def event_bus(self) -> IEventBus:
        return self._event_bus

    @event_bus.setter
    def event_bus(self, value: IEventBus) -> None:
        self._event_bus = value

    @property
    def tasks(self) -> ITaskManager:
        return self._tasks

    @tasks.setter
    def tasks(self, value: ITaskManager) -> None:
        self._tasks = value

    @property
    def modules(self) -> list[Any]:
        return self.extension_manager.registered_extensions

    @property
    def logger(self) -> ILogger:
        try:
            return self.container.resolve(ILogger)
        except Exception:
            from sagittarius_engine.utils.null_logger import NullLogger

            return NullLogger()

    @property
    def config(self) -> IConfig | None:
        try:
            return self.container.resolve(IConfig)
        except Exception:
            return None
