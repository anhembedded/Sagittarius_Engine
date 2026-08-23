# API & Interface Contracts

Rewritten 2026-08-23 — found wrong while writing `EPIC-002`'s `AUDIT_REPORT.md`, not before:
`auto_discover` documented as `bool` (it's `str | None`), `IExtension` omitted from "Key
Interfaces" entirely despite being what every real extension implements, and three interfaces
listed with incomplete method sets. See
[`AUDIT_REPORT.md`](../../Tasks/epics/EPIC-002_engine_sample_app_and_doc_rewrite/AUDIT_REPORT.md)
§1.2.

The engine uses explicit abstractions (`sagittarius_engine.interfaces.*`) for decoupled
architecture — depend on those, not concrete implementations.

## `App` facade

- **`app.use(extension_or_module)`**: registers an `IExtension` or (legacy) `IModule`.
- **`app.use_middleware(middleware)`**: adds a middleware to the dispatch pipeline.
- **`app.boot(auto_discover=None)`**: boots the container, runtime, and extensions.
  `auto_discover` is `str | None` — a package name to scan for auto-discoverable modules
  (e.g. `auto_discover="modules"`), **not** a boolean; see `kernel/bootstrap.py:17,31`, which
  passes it straight to `discover_and_load()`. Passing `True` matches no real usage. (The
  worked example this line used to cite lived under the SDK's "clean" project template,
  deleted with the whole scaffolding feature on 2026-08-23 — see
  [TASK-024](../../Tasks/completed/TASK-024_getting_started_scaffolders_broken.md).)
- **`app.dispatch(HandlerClass, input_dto)`**: resolves a handler via the DI container
  (constructor-injecting its dependencies) and calls `handler.execute(input_dto)` through the
  middleware pipeline.
- **`app.stop()`**: graceful shutdown — scheduler, hosted services, extensions (reverse
  registration order), task manager, async runtime, event bus, in that order
  (`kernel/app.py`'s `stop()`).

## `IEngineContext` — four ports, not three

Passed to extensions during `register`/`boot`/`shutdown` (never held long-term outside that
phase — see `rules/architecture.md`'s God-Object-prevention section):

- **`context.container`** — `IContainer`
- **`context.event_bus`** — `IEventBus`
- **`context.logger`** — `ILogger`
- **`context.tasks`** — `ITaskManager`

## Key interfaces

- **`IExtension[TContext]`** — the real, current extension model. Nine lifecycle methods in
  two layers (author: `register`/`boot`/`shutdown`; orchestrator: `initialize`/`start`/`stop`/
  `dispose`, delegating by default) — see `modules.md` and `rules/architecture.md`'s "override
  vs. call" section before implementing one. Generic over a narrow context Protocol
  (`IExtension[ILoggerContext]`, etc.) rather than the full `IEngineContext` — see
  `rules/architecture.md`.
- **`IModule`** — legacy (`kernel/extension_manager.py:22` calls it that in the engine's own
  code). `register(app)`, `boot(app)`, `shutdown(app)`. Adapted internally via
  `ModuleExtensionAdapter` to satisfy `IExtension`. Not the interface to reach for in new code.
- **`IHostedService`**: `start(context)`, `stop(context)`.
- **`IEventBus`**: `on(event_name_or_type, handler)`, `emit(event_name_or_obj, data=None)`,
  `off(event_name_or_type, handler)`. Accepts both string event names and `BaseEvent` subclass
  types.
- **`IContainer`**: `bind(abstract, concrete)` (transient), `singleton(abstract,
  instance_or_factory)`, `resolve(abstract)`, `scoped(abstract, concrete)` (per-scope),
  `create_scope()` (context manager for scoped resolution). Five methods, not three.

## A real, verified constructor gap

`App(container, event_bus)` does **not** register either argument into the container — only
`app.event_bus`/`context.event_bus` reach `event_bus` directly. `container.resolve(IEventBus)`
raises `DependencyResolutionError` unless the composition root explicitly does
`container.singleton(IEventBus, event_bus)` (same for `IConfig`) before `app.boot()`. Verified
building `examples/student_management/` — see its `docs/bootstrap.md`.
