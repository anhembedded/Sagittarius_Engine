from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    pass

TContext = TypeVar("TContext", contravariant=True)


@dataclass
class ExtensionDescriptor:
    """
    @brief Metadata describing an engine extension.
    """

    name: str
    version: str = "1.0.0"
    dependencies: list[str] = field(default_factory=list)
    optional_dependencies: list[str] = field(default_factory=list)
    enabled: bool = True
    priority: int = 0
    author: str = ""
    description: str = ""


# PEP 695 syntax not applied: TContext is declared `contravariant=True`, and
# ruff's own unsafe-fix for this rule drops that entirely (PEP 695 infers
# variance rather than declaring it) — verified by previewing the fix and
# reading the diff. Converting this one needs a deliberate mypy check that
# inferred variance still matches; not a mechanical cleanup. TASK-021.
class IExtension(ABC, Generic[TContext]):  # noqa: UP046
    """Interface for Sagittarius Engine Extensions."""

    @property
    def name(self) -> str:
        """
        @brief Return the extension's name. Defaults to the class name.
        """
        return self.__class__.__name__

    @property
    def descriptor(self) -> ExtensionDescriptor:
        """
        @brief Return the extension descriptor. Defaults to class name and attributes.
        """
        deps = getattr(self, "dependencies", [])
        opt_deps = getattr(self, "optional_dependencies", [])
        prio = getattr(self, "priority", 0)
        enabled = getattr(self, "enabled", True)
        return ExtensionDescriptor(
            name=self.__class__.__name__,
            dependencies=deps if isinstance(deps, list) else [],
            optional_dependencies=opt_deps if isinstance(opt_deps, list) else [],
            priority=prio if isinstance(prio, int) else 0,
            enabled=enabled if isinstance(enabled, bool) else True,
        )

    @abstractmethod
    def register(self, context: TContext) -> None:
        """
        @brief Called first when the extension is registered to bind dependencies.
        @param context The EngineContext instance.
        """
        ...

    @abstractmethod
    def boot(self, context: TContext) -> None:
        """
        @brief Called after all extensions have been registered to trigger startup logic.
        @param context The EngineContext instance.
        """
        ...

    @abstractmethod
    def shutdown(self, context: TContext) -> None:
        """
        @brief Called when the engine is stopping to release resources.
        @param context The EngineContext instance.
        """
        ...

    def initialize(self, context: TContext) -> None:
        """
        @brief Orchestrator initialization step. Defaults to calling register.
        """
        self.register(context)

    def start(self, context: TContext) -> None:
        """
        @brief Orchestrator start step. Defaults to calling boot.
        """
        self.boot(context)

    def stop(self, context: TContext) -> None:
        """
        @brief Orchestrator stop step. Defaults to calling shutdown.
        """
        self.shutdown(context)

    def dispose(self, context: TContext) -> None:
        """
        @brief Orchestrator cleanup/release step. Defaults to no-op.
        """
        pass

    async def boot_async(self, context: TContext) -> None:
        """
        @brief Optional async lifecycle hook called after boot().

        @details Override this method to perform heavy I/O-bound initialization
        (e.g., pinging a database, warming up a cache, fetching remote config)
        without blocking the main thread. The EngineLifecycle will schedule this
        coroutine on the background AsyncRuntime event loop.

        Default implementation is a no-op, so existing extensions do not need to change.
        """
        return

    async def shutdown_async(self, context: TContext) -> None:
        """
        @brief Optional async lifecycle hook called before shutdown().

        @details Override this method to gracefully close async resources
        (e.g., async DB sessions, WebSocket connections) during engine shutdown.

        Default implementation is a no-op, so existing extensions do not need to change.
        """
        return
