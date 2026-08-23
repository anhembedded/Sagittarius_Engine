import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sagittarius_engine.kernel.app import App
    from sagittarius_engine.kernel.i_kernel_context import IKernelContext
from sagittarius_engine.base.base_module import BaseModule
from sagittarius_engine.interfaces import ILogger, IModule


class ModuleLoader:
    """Responsible for discovering and loading engine extensions."""

    def __init__(self, context_or_app: "App | IKernelContext") -> None:
        self.context_or_app = context_or_app

    @property
    def context(self) -> "IKernelContext":
        if hasattr(self.context_or_app, "context"):
            return self.context_or_app.context
        return self.context_or_app

    def _get_logger(self) -> ILogger | None:
        try:
            return self.context.logger
        except Exception:
            try:
                return self.context.container.resolve(ILogger)
            except Exception:
                return None

    def discover_and_load(self, package_path: str) -> None:
        """
        @brief Scans the specified package, instantiates, and registers IModules.
        """
        logger = self._get_logger()
        try:
            package = importlib.import_module(package_path)
        except ImportError as e:
            if logger:
                logger.warning(f"Could not discover package {package_path}: {e}")
            return

        if not hasattr(package, "__path__"):
            return

        for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
            full_module_name = f"{package_path}.{name}"
            try:
                sub_package = importlib.import_module(full_module_name)
                for _, obj in inspect.getmembers(sub_package, inspect.isclass):
                    if (
                        issubclass(obj, IModule)
                        and obj is not IModule
                        and obj is not BaseModule
                    ):
                        if hasattr(self.context, "app") and self.context.app:
                            self.context.app.use(obj())
                        elif hasattr(self.context_or_app, "use"):
                            self.context_or_app.use(obj())
            except Exception as e:
                if logger:
                    logger.error(f"Failed to load module {full_module_name}: {e}")
