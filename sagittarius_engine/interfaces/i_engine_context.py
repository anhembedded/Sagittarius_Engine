from abc import ABC, abstractmethod

from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.interfaces.i_task_manager import ITaskManager


class IEngineContext(ABC):
    """
    @brief Core Abstract Interface (Port) for the shared Engine Context.

    @details
    Clean Architecture Principle:
    According to the Dependency Inversion Principle (DIP), high-level modules
    (such as IHostedService or IExtension) must not depend on low-level concrete classes
    (like EngineContext in the kernel). Instead, both must depend on abstractions (this IEngineContext interface).

    By passing IEngineContext to Hosted Services and Extensions:
    - High-level components get full access to core engine ports (DI Container, EventBus, Logger, TaskManager).
    - IDEs can provide 100% accurate IntelliSense auto-completion.
    - Test suites can easily inject mock implementations of IEngineContext.

    @par Architectural Usage Guidelines (God Object Prevention)
    IEngineContext is intentionally limited to the Bootstrap and Extension initialization phase.
    To prevent this interface from becoming a God Object Anti-Pattern, follow these strict rules:

    ✅ VALID usage of IEngineContext:
    - Inside IExtension.register(), boot(), shutdown() methods.
    - Inside IHostedService.start() and stop() methods.
    - Inside the Kernel's Bootstrap and AppRunner orchestrators.

    ❌ INVALID usage of IEngineContext:
    - Inside domain entities or value objects.
    - Inside application use cases or command/query handlers.
    - As a constructor-injected dependency in application-layer services.

    For application-layer components, use Dependency Injection via __init__() instead.
    Register your dependencies in the IExtension.register() phase using context.container,
    then let the DI Container auto-inject them into your use cases and handlers.
    """

    @property
    @abstractmethod
    def container(self) -> IContainer:
        """
        @brief The Dependency Injection Container interface.
        @return IContainer instance used for resolving registered dependencies.
        """
        ...

    @property
    @abstractmethod
    def event_bus(self) -> IEventBus:
        """
        @brief The Event Bus interface.
        @return IEventBus instance used for publishing and subscribing to events across modules.
        """
        ...

    @property
    @abstractmethod
    def logger(self) -> ILogger:
        """
        @brief The Logger interface.
        @return ILogger instance (returns a NullLogger if logging module is disabled, guaranteeing it is never None).
        """
        ...

    @property
    @abstractmethod
    def tasks(self) -> ITaskManager:
        """
        @brief The Task Manager interface for spawning and managing background tasks.
        @return ITaskManager instance used for cooperative thread/coroutine execution.
        """
        ...
