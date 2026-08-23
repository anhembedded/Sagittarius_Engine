# Architecture Design

AI cần hiểu project trước khi code.

## Architecture Overview Diagram

```mermaid
flowchart LR
    ClientApp[Application / Client] --> App[App Facade]
    App --> Dispatcher[Dispatcher]
    App --> Bootstrap[Bootstrap & Extensions]
    App --> Lifecycle[Runtime Lifecycle]

    Dispatcher --> Middleware[Middleware Pipeline]
    Middleware --> Handlers[Command / Query Handlers]

    Handlers --> EventBus[EventBus]
    Handlers --> Container[Container DI]

    EventBus --> Extensions[Registered Extensions]
```

## Extension Model

Extensions implement `IExtension` and act as plugins that hook into the Engine's lifecycle.
**Two layers, corrected 2026-08-23** (see `../modules.md` for the full account): you implement
`register`/`boot`/`shutdown`; `ExtensionManager` actually calls `initialize`/`start`/`stop`/
`dispose`, which delegate to your methods by default. Overriding the orchestrator layer
without calling `super()` silently skips your own lifecycle code.
They can register background daemon threads (e.g., `WebsocketBroadcaster` in `AuditExtension`) and listen to the `EventBus` to stream telemetry or intercept commands asynchronously without blocking the main engine thread.

## Tool Dashboard Architecture (PySide6)

Tools built around the engine (like `audit_dashboard`) strictly follow Clean Architecture.
Names corrected 2026-08-23 against the real source in `tools/audit_dashboard/` (the previous
version guessed at plausible-sounding names that don't exist in the code):

- **Domain**: Core UI models (`tools/audit_dashboard/Domain/entities.py`) and interfaces —
  `IRealtimeConnector` (not `IConnector`), in `tools/audit_dashboard/Domain/ports.py`.
- **Application**: Use cases orchestrating data flow — `StartRealtimeListenerCommand` (not
  `ReceiveAuditUseCase`), in `tools/audit_dashboard/application/receive_audit_use_case.py`.
- **Infrastructure**: Concrete adapters — `WebsocketConnector`, in
  `tools/audit_dashboard/infra/websocket_connector.py`, communicating with the engine.
- **Presentation**: PySide6 widgets — `MainWindow`, in
  `tools/audit_dashboard/presentation/main_window.py`, reacting to state updates via Qt Signals.

## EngineContext Subsystem Composition

```mermaid
flowchart LR
    App[Application Facade] --> EngineContext[EngineContext]

    subgraph Core Subsystems
        EngineContext --> Dispatcher[Dispatcher]
        EngineContext --> Bootstrap[Bootstrap]
        EngineContext --> Lifecycle[Lifecycle]
        EngineContext --> ExtensionManager[Extension Manager]
    end

    subgraph Runtime Infrastructure
        EngineContext --> AsyncRuntime[Async Runtime]
        EngineContext --> TaskManager[Task Manager]
        EngineContext --> Scheduler[Scheduler]
        EngineContext --> HostedServices[Hosted Services]
    end

    subgraph Abstractions
        EngineContext --> Container[Container DI]
        EngineContext --> EventBus[EventBus]
    end
```

## Class Diagrams (`App` Facade)

### High-Level Class Dependency Diagram

```mermaid
classDiagram
    class App
    class EngineContext
    class IContainer {
        <<interface>>
    }
    class IEventBus {
        <<interface>>
    }
    class IMiddleware {
        <<interface>>
    }

    App *-- EngineContext : delegates state & orchestration
    App ..> IContainer : receives & uses
    App ..> IEventBus : receives & uses
    App ..> IMiddleware : registers
```

### Detailed Class Diagram

```mermaid
classDiagram
    class App {
        +EngineContext context
        +container: IContainer
        +event_bus: IEventBus
        +modules: list
        +pipeline: Any
        +lifecycle: Any
        +use(extension_or_module: Any) void
        +use_middleware(middleware_instance: IMiddleware) void
        +boot(auto_discover: str) void
        +dispatch(handler_class: type, input_dto: Any) Any
        +stop() void
    }

    class EngineContext {
        +App app
        +IContainer container
        +IEventBus event_bus
        +middleware_pipeline: MiddlewarePipeline
        +extension_manager: ExtensionManager
        +bootstrap: Bootstrap
        +dispatcher: Dispatcher
        +lifecycle: RuntimeLifecycle
    }

    class IContainer {
        <<interface>>
        +bind(interface, concrete)
        +singleton(interface, instance_or_factory)
        +resolve(interface_or_type)
    }

    class IEventBus {
        <<interface>>
        +on(event_name, handler)
        +emit(event_name, event)
    }

    class IMiddleware {
        <<interface>>
        +process(request, next_call)
    }

    App *-- EngineContext : delegates operations
    App ..> IContainer : access & resolve
    App ..> IEventBus : event dispatching
    App ..> IMiddleware : pipeline extension
```
