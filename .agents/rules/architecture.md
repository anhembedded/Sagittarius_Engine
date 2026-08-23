---
name: Architecture Rules
description: Module boundaries, dependency guidelines, and strict 4-layer Clean Architecture rules for the Sagittarius Engine and application layers.
trigger: model_decision
---

# Rules: Architecture

Module boundaries, dependency guidelines, and layout rules.

> **Two different trees.** This file governs *both* the engine's own package
> layout (`sagittarius_engine/`, §"Engine Package Layout") and the Clean
> Architecture shape the engine expects of a **consuming application**
> (§"Clean Architecture Layers"). They are not the same tree and do not share
> directory names — the engine has no `application/` package, and never will;
> that layer belongs to the consumer. Conflating the two is the most common
> way this document gets misread.

## IEngineContext — God Object Prevention

`IEngineContext` (`interfaces/i_engine_context.py`) exposes exactly four ports:
`container`, `event_bus`, `logger`, `tasks`. It must ONLY be used during the
engine's Bootstrap and Extension lifecycle phase. Anything holding it long-term
outside that phase has acquired the whole engine as a dependency, which is the
God Object it exists to prevent.

### ✅ Valid Usage
- Inside any `IExtension` lifecycle method. There are **nine**, in two
  layers — see "Extension lifecycle: override vs. call" below before
  overriding any of them.
- Inside `IHostedService.start()` and `stop()`
  (`runtime/hosted/hosted_service.py`).
- **Constructor-held by the engine's own orchestrators, and only these.** The
  set is closed and lives in `kernel/context.py`: `EngineContext` constructs
  `ExtensionManager`, `EngineLifecycle`, `ModuleLoader`, `Bootstrap`,
  `Dispatcher`, `AsyncRuntime`, `TaskManager`, `Scheduler` and
  `HostedServiceManager`, passing `self` to each. (`MiddlewarePipeline` is
  built context-free — keep it that way.) Adding a new class to this set is an
  architecture decision, not an implementation detail.

`IKernelContext` (`kernel/i_kernel_context.py`) **subclasses** `IEngineContext`
and adds the internal wiring handles (`app`, `lifecycle`, `bootstrap`,
`extension_manager`, `scheduler`, `hosted_services`, …). Kernel code therefore
does not "avoid" `IEngineContext` — it consumes a strict superset of it. The
distinction that matters is the direction: kernel internals may see the
superset; extensions and hosted services see only the four-port base.

> There is no `AppRunner` class. `kernel/app_runner.py` defines
> **`ApplicationRunner`**, and it takes `App` + `IInputPort` + `IOutputPort` —
> it never receives a context at all. Do not add one; the ports *are* its
> boundary.

### ❌ Invalid Usage
- Inside a consuming application's `domain/` layer (entities, value objects,
  domain services). The engine's own `sagittarius_engine/domain/` is likewise
  context-free and must stay that way.
- Inside a consuming application's `application/` layer (use cases,
  command/query handlers, application services).
- As a constructor parameter (`__init__`) of any class outside the closed
  orchestrator set above — extensions included. An extension receives the
  context as a *method argument* per call; it must not stash it on `self`.

### Correct Pattern
Register dependencies in `IExtension.register()` using `context.container`, then inject them
into use cases / handlers via the DI Container — never pass `IEngineContext` itself:

```python
# ✅ Correct
class MyExtension(IExtension):
    def register(self, context: IEngineContext) -> None:
        # StdLibContainer.singleton() accepts an instance, a class (lazy,
        # auto-injected on first resolve), or a factory callable.
        context.container.singleton(IMyRepo, ConcreteRepo)


class MyUseCase:  # Gets IMyRepo injected by container — NOT IEngineContext
    def __init__(self, repo: IMyRepo) -> None:
        self._repo = repo


# ❌ Wrong
class MyUseCase:
    def __init__(self, context: IEngineContext) -> None:  # God Object anti-pattern!
        self._context = context
```

### Extension lifecycle: override vs. call

`IExtension` declares nine lifecycle methods, and they are **not** nine phases.
They are two layers of a template-method pattern, and confusing them silently
disables your extension:

| Layer | Methods | Who touches them |
| :--- | :--- | :--- |
| **Author layer** — abstract, you implement these | `register`, `boot`, `shutdown` | You override. The engine never calls them directly on your class. |
| **Orchestrator layer** — concrete, default to delegating | `initialize`→`register`, `start`→`boot`, `stop`→`shutdown`, `dispose`→no-op | `ExtensionManager` calls **these**. Do not override without calling `super()`. |
| **Async hooks** — concrete, default no-op | `boot_async`, `shutdown_async` | Override freely; scheduled on the `AsyncRuntime` loop. |

> **The trap:** overriding `start()` without calling `super().start(context)`
> means your `boot()` never runs, and nothing errors — `ExtensionManager`
> calls `start()`, not `boot()` (`kernel/extension_manager.py:258`). Override
> the author layer unless you specifically need to wrap orchestration.

`dispose()` is the one orchestrator method with no author-layer counterpart:
it is a genuine fourth phase (called after `stop()`), and overriding it
directly is correct.

### Prefer a narrow context Protocol over `IEngineContext`

`IExtension` is generic in its context type (`IExtension[TContext]`), and every
extension shipped in this repo exploits that: `LoggerExtension` is
`IExtension[ILoggerContext]` where `ILoggerContext` is a local `Protocol`
exposing `container` and nothing else. Same shape for `IHealthContext`,
`IDatabaseContext`, `IThreadManagerContext`, `IAuditContext`.

This is the preferred form for new extensions, and it is stronger than the rule
above rather than an exception to it: an extension that structurally cannot
reach `event_bus` cannot accidentally grow a dependency on it, and its tests
need a two-line stub instead of a full engine. Reach for bare
`IExtension[IEngineContext]` only when the extension genuinely needs three or
more of the four ports.

## Engine Package Layout

Every top-level package under `sagittarius_engine/`, and the rule for each.
This list is exhaustive — a new top-level package is an architecture change.

- `interfaces/` — Ports. Abstract (`ABC`) declarations only; no concrete
  implementation, no framework import. This is the only package the whole tree
  is allowed to depend on freely.
  - **One live exception, unresolved:** `i_event_bus.py` imports the *concrete*
    `domain.base_event.BaseEvent` to bound its `TypeVar`
    (`E = TypeVar("E", bound=BaseEvent)`), while the abstraction `IDomainEvent`
    sits right next to it in `domain/`. This makes `interfaces/` the one
    package with an inward dependency on a concrete class, and it is a
    behavioural contract (`IEventBus.on`/`emit` typing) that consumers already
    bind against — narrowing it to `IDomainEvent` is a breaking change, not a
    cleanup. Do not add a second exception on this precedent.
- `domain/` — The engine's own event primitives (`IDomainEvent`, `BaseEvent`).
  Pure Python, no engine imports outward.
- `base/` — Shared abstract bases for consumer-facing types (`BaseModule`,
  `BaseInputPort`, `BaseOutputPort`).
- `kernel/` — Internal orchestration and the runtime composition root
  (`EngineContext`, `App`, `Bootstrap`, `ExtensionManager`, `Dispatcher`,
  `EngineLifecycle`, `ModuleLoader`, `ApplicationRunner`). Depends on
  `interfaces/`, `base/`, `runtime/`, `exceptions`. Must **not** import
  `extensions/` or `infrastructure/` concretes.
- `runtime/` — Execution machinery owned by the kernel but separable:
  `async_runtime/`, `hosted/`, `scheduler/`, `tasks/`.
- `infrastructure/` — Concrete adapters satisfying `interfaces/` ports:
  `config/`, `container/`, `event_bus/`, `logging/`, `persistence/`,
  `storage/`. **No `domain/` imports** — verified: zero references.
- `adapters/` — Delivery-mechanism ports for the host process: `cli/`,
  `batch/`. Input/output only; no business logic.
- `middleware/` — Dispatch pipeline stages (logging, timing, validation,
  pydantic validation).
- `extensions/` — Opt-in feature packages, each normally implementing
  `IExtension` against its own narrow context Protocol: `audit/`, `cqrs/`,
  `fsm/`, `health/`, `logger/`, `persistence/`, `thread_manager/`,
  `pyside_mvc/`, plus `dependency_validator.py`. An extension **may** import
  `infrastructure/` concretes — that is its job as a composition unit
  (`LoggerExtension` binds `StdLogger` to `ILogger`). It must not be imported
  *by* `kernel/` or `infrastructure/`.
- `sdk/` — Project scaffolding (`project_generator.py`, `cli.py`) plus the
  `templates/` the engine emits: `minimal`, `clean`, `ddd`, `mvc`. The
  `clean`/`ddd` templates are where the 4-layer shape below is materialised,
  including the `application/` directory the engine itself does not have.
- `utils/` — Leaf helpers with no engine dependencies (`NullLogger`,
  `PathUtils`).

### `pyside_mvc` — internals are not a public surface

`extensions/pyside_mvc/` is the one extension with enough internal structure to
need its own boundary rule, and `ui-architecture.md` owns the detail. The only
thing that belongs *here* is the dependency rule, because it constrains callers
outside the UI:

**A consumer imports from `sagittarius_engine.extensions.pyside_mvc` and nothing
deeper.** The subpackages (`tokens/`, `kit/`, `runtime/`, `mvc/`, `safety/`) and
the QML module at `Sagittarius/UI/` (one directory per component) are internal
layout, free to move without notice; the top-level `__init__.py` re-export list
is the contract. Enforced statically by
`import_boundary.find_deep_imports()`, importable by a consuming app's own test
suite, with a reviewed allowlist (`SANCTIONED_DEEP_IMPORTS` — today exactly
`base_view` and `QmlShared.log_list_model`, both backed by deprecation-warning
shims at the old paths for real pre-existing consumers).

See `ui-architecture.md` §8.1 for the rationale and §1–§7 for everything else
about the UI engine. Do not restate UI specifics in this file; if the two
disagree, `ui-architecture.md` wins on UI and this file is the one to fix.

## Clean Architecture Layers (The 4 Layers)

**Applies to a consuming application**, not to `sagittarius_engine/`'s own tree. Two
references: this repo's own sample, `examples/student_management/`, and the real consumer,
`Sagittarius_Elite_Warrior`. (This line used to also cite `sdk/templates/clean` and
`sdk/templates/ddd`; the scaffolding feature was deleted on 2026-08-23 — see
[TASK-024](../../Tasks/completed/TASK-024_getting_started_scaffolders_broken.md).)

### Layer 1 & 2: The Core (Lõi hệ thống)
**Responsibility:** Contains the business rules.
- **Layer 1 - Domain (Enterprise Business Rules):** Contains Entities and Value Objects (e.g., `MarketData` in `src/domain/entities/`, `TimeFrame` in `src/domain/value_objects/`). Must be **100% pure Python**. Must know absolutely nothing about the app, bot, framework (`sagittarius_engine`), or database. In the reference consumer this holds exactly: `src/domain/` contains zero `sagittarius_engine` imports.
- **Layer 2 - Application (Application Business Rules):** Contains Use Cases and Contracts/Ports. A use case is a **directory**, not a module — `src/application/use_cases/sync/sync_market_data/` holds `command.py` + `handler.py`, and the same shape repeats under `backtest/`, `database/`, `queries/`, `stream/`. Ports live in `src/application/ports/` (`IExchangeClient`, `IMarketDataRepository`, `ILiveStreamService`, `ISymbolMarketMetadataCache`, and the
`ICommandHandler`/`IQueryHandler` protocols in `i_cqrs.py`). Must NOT contain any API connection, framework lifecycle, or SQL logic.
  - **Permitted framework contact:** the engine *ports* — `IEventBus`, `IConfig`, `IDispatcher` — may be imported here, because they are abstractions the layer depends on inward, not machinery. Importing a concrete engine runtime type (e.g. `App`) into a use case or handler is a violation of this layer, not a grey area.

### Layer 3: Interface Adapters (Tầng Giao tiếp / Chuyển đổi)
**Responsibility:** Acts as the "translator" between the Core and the Outside World.
- Transforms data from formats convenient for Use Cases to formats convenient for Database/UI, and vice versa.
- **Example (Sagittarius_Elite_Warrior):** `src/presentation/cli/` takes raw text from the user, translates it into DTOs (e.g., `StartLiveStreamCommand`), and dispatches it to the Engine. It also takes results and prints them.
- **The GUI is here too, and it already exists.** `src/presentation/ui/` (screens, components, services) sits alongside `cli/` at the same layer. Both are drivers; the Application layer must remain completely unaware of which one is driving it. The engine-side contract for that GUI is `pyside_mvc` — see `ui-architecture.md`.

### Layer 4: Infrastructure & Frameworks (Tầng Cơ sở hạ tầng)
**Responsibility:** Where the system touches hardware, network, databases, and frameworks.
- This layer contains "dirty" code full of external libraries, SDKs, and network connections. It plugs Adapters into the Ports defined by Layer 2.
- **Examples (Sagittarius_Elite_Warrior):** `src/infrastructure/` and `src/main.py`.
- **External Libraries:** `python-binance` (for API), `sqlalchemy` (for DB), and `sagittarius_engine` (for framework).
- **Concrete Adapters:**
  - `PythonBinanceClient` (`src/infrastructure/binance/client.py`): uses `binance` to satisfy `IExchangeClient`.
  - `BinanceWebsocketService` (`src/infrastructure/binance/binance_websocket_service.py`): uses `BinanceSocketManager` to satisfy `ILiveStreamService`.
  - `SQLAlchemyMarketDataRepository`: uses `sqlalchemy` to satisfy `IMarketDataRepository`.
- **Composition Root:** `src/main.py` is the "dirtiest" place where everything is imported, the DI Container (`StdLibContainer`) is initialized, extensions are registered, all pieces are wired together, and the system is booted. This is the only file permitted to know every layer at once.
