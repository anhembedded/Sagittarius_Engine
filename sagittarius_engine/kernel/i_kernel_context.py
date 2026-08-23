from abc import abstractmethod
from typing import TYPE_CHECKING

from sagittarius_engine.interfaces.i_engine_context import IEngineContext

if TYPE_CHECKING:
    from sagittarius_engine.kernel.app import App
    from sagittarius_engine.kernel.bootstrap import Bootstrap
    from sagittarius_engine.kernel.dispatcher import Dispatcher
    from sagittarius_engine.kernel.extension_manager import ExtensionManager
    from sagittarius_engine.kernel.lifecycle import EngineLifecycle
    from sagittarius_engine.kernel.middleware_pipeline import MiddlewarePipeline
    from sagittarius_engine.kernel.module_loader import ModuleLoader
    from sagittarius_engine.runtime.async_runtime.async_runtime import AsyncRuntime
    from sagittarius_engine.runtime.hosted.hosted_service_manager import (
        HostedServiceManager,
    )
    from sagittarius_engine.runtime.scheduler.scheduler import Scheduler


class IKernelContext(IEngineContext):
    """
    @brief Internal interface for the Engine Context used within the Kernel.
    """

    app: "App"
    middleware_pipeline: "MiddlewarePipeline"
    lifecycle: "EngineLifecycle"
    module_loader: "ModuleLoader"
    bootstrap: "Bootstrap"
    dispatcher: "Dispatcher"
    extension_manager: "ExtensionManager"
    async_runtime: "AsyncRuntime"
    scheduler: "Scheduler"
    hosted_services: "HostedServiceManager"

    @property
    @abstractmethod
    def modules(self) -> list: ...
