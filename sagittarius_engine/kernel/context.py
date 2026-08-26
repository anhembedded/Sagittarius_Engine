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
from sagittarius_engine.interfaces.i_trace_recorder import ITraceRecorder
from sagittarius_engine.kernel.bootstrap import Bootstrap
from sagittarius_engine.kernel.dispatcher import Dispatcher
from sagittarius_engine.kernel.extension_manager import ExtensionManager
from sagittarius_engine.kernel.i_kernel_context import IKernelContext
from sagittarius_engine.kernel.lifecycle import EngineLifecycle
from sagittarius_engine.kernel.middleware_pipeline import MiddlewarePipeline
from sagittarius_engine.kernel.module_loader import ModuleLoader
from sagittarius_engine.kernel.tracing import TraceApi


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

        # EPIC-005B. `None` when tracing is off, and every instrumentation site
        # in the engine guards on that — measured in EPIC-005A as ~3 ns over an
        # empty call site, against ~27 ns for a call through a no-op object.
        # The type is the interface, not the concrete recorder: `kernel/` is
        # forbidden from importing `extensions/` (tests/test_architecture.py),
        # which is also why `Lane` lives in `interfaces/`.
        self.recorder: ITraceRecorder | None = None
        #: Always present, even when disabled — see `kernel/tracing.py` for why
        #: applications get a different mechanism from the engine's own sites.
        self.trace = TraceApi(self)

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

    def enable_tracing(self, recorder: ITraceRecorder) -> ITraceRecorder:
        """
        @brief Turns tracing on for this application.

        @details Takes the recorder rather than building one, because `kernel/`
        may not import `extensions/` — and because it lets a test pass a fake.

        Call it **before `boot()`** to get boot profiling: the extension spans
        are the answer to "why does startup take four seconds", and they are
        only recorded if the recorder exists before the extensions start.

        @code
        from sagittarius_engine.extensions.audit.recorder import TraceRecorder

        app = App(container, event_bus)
        app.context.enable_tracing(TraceRecorder())
        app.boot()
        @endcode
        """
        self.recorder = recorder
        return recorder

    def disable_tracing(self) -> None:
        """@brief Turns tracing off. What was already recorded stays in the
        recorder — that is usually when it is read."""
        self.recorder = None

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
