# Sagittarius Engine

## Overview

Sagittarius Engine is a lightweight, modular application runtime for Python.

It is **not**:
- Web framework
- MVC framework
- Clean Architecture framework
- ORM
- DI library
- CQRS framework

Applications own architecture.
Sagittarius provides runtime capabilities only.

Supported architectures include:
- Clean Architecture
- DDD
- MVC
- Layered
- Event Driven
- Hexagonal
- Custom

---

## Philosophy

- Applications choose architecture
- Kernel provides capabilities
- Runtime orchestrates execution
- Extensions integrate technologies

---

## Architecture

| Layer | Responsibility |
|--------|----------------|
| Kernel | Host, Context, Dispatcher, Lifecycle, Bootstrap |
| Runtime | Hosted Services, Scheduler, Tasks, Async, Cancellation |
| Extensions | `audit`, `cqrs`, `fsm`, `health`, `logger`, `persistence` (SQLAlchemy-backed), `pyside_mvc` (PySide6/QML UI), `thread_manager` — exhaustive as of 2026-08-23 |
| Tools / Apps | Business Logic, Domain, UI. Reference: `examples/student_management` (Clean Architecture + `pyside_mvc` QML UI, see `examples.md`); `tools/audit_dashboard` (plain PySide6 QtWidgets) |

There was a fifth row here, `SDK | Templates, Generator, Project Setup` — the scaffolding
feature (`sagittarius_engine.sdk`, `tools/scaffold.py`) was deleted entirely on 2026-08-23
(`TASK-024`): both its documented invocations were broken, and it shipped no replacement.
See `CHANGELOG.md`'s `2.0.0` entry.

---

## Public API Rules

Documentation must:

- use `from sagittarius_engine import ...`
- avoid internal imports
- avoid private APIs
- avoid implementation details
- avoid deprecated APIs

---

## Runtime Capabilities

- DI Container
- Dispatcher
- Event Bus (Sync/Async/IPC)
- Middleware
- Extension Runtime
- Hosted Services (Daemon processes)
- Scheduler (Cron/Interval)
- Task Manager (Async/Sync execution)
- Async Runtime
- Cancellation Tokens
- Configuration
- Logging
- Metrics & Telemetry (WebSockets via Audit)
- Storage
- Persistence

---

## Extension Lifecycle

Corrected 2026-08-23 (was missing a whole layer): `initialize`/`start`/`stop`/`dispose` are
the **orchestrator** layer `ExtensionManager` actually calls — by default each just delegates
to the **author** layer you implement: `register`/`boot`/`shutdown`. Overriding `start()`
without calling `super().start(context)` silently skips your `boot()` — see `modules.md` and
`rules/architecture.md` for the full override-vs-call trap.

```
register → (initialize delegates here)
boot     → (start delegates here)
shutdown → (stop delegates here)
(dispose has no author-layer counterpart — a genuine 4th phase, safe to override directly)
```

Extension metadata (`ExtensionDescriptor`): `dependencies`, `optional_dependencies`,
`priority`, `name` (defaults to the class name).

**Dependency order is resolved automatically — if you declare it.** `dependencies` is a list
of strings matched against another extension's `descriptor.name`.
`ExtensionManager._build_and_sort()` topologically sorts by this graph; verified directly
(`examples/student_management`'s `docs/module_registration.md`): declaring
`dependencies = ["DatabaseExtension"]` makes boot succeed even if `app.use()` was called in
the wrong order. Without a declared dependency, `app.use()` call order is the *only* thing
establishing it, and getting that wrong fails loudly (`DependencyResolutionError`) at boot.

---

## Runtime Lifecycle

Startup

```
Container
↓
Runtime
↓
Extensions
↓
Hosted Services
↓
Scheduler
↓
Ready
```

Shutdown

```
Scheduler
↓
Hosted Services
↓
Extensions
↓
Task Manager
↓
Async Runtime
↓
Stopped
```

---

## Design Goals

Prioritize

- Simplicity
- Modularity
- Composability
- Testability
- Deterministic lifecycle
- Dependency inversion
- Runtime safety
- Graceful shutdown

Avoid

- Magic
- Hidden globals
- Architecture lock-in
- Business abstractions
- Framework-specific patterns

---

## Target Applications

- Trading Bots
- Desktop Apps (e.g. PySide6 / PyQt)
- Background Workers
- Automation
- ETL
- Long-running Services
- Plugin Systems
- CLI

---

## Non Goals

Sagittarius is not intended to replace:

- Django
- FastAPI
- Flask
- SQLAlchemy
- Celery
- APScheduler
- PySide

Instead, it integrates with them through Extensions and custom Adapters.

---

## Documentation Rules

For every feature:

1. Explain the concept
2. Explain why it exists
3. Explain when to use it
4. Explain when not to use it
5. Add diagrams when useful
6. Provide runnable examples
7. Mention related capabilities
8. Hide implementation details

Always write from the perspective of an application developer.