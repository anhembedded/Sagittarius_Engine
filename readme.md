# Sagittarius Engine

**A lightweight, modular Python Application Engine for building runtime-driven, extension-based applications.**

Sagittarius Engine is a runtime host — not a web framework, not an ORM, not a DDD framework. It provides the infrastructure layer for building long-running applications: background workers, desktop apps, trading bots, plugin systems, automation pipelines, and CLI tools.

---

## Why Sagittarius Engine?

Most Python frameworks force your application into a specific architecture. Sagittarius Engine takes a different approach: it provides runtime capabilities and gets out of the way.

### What the Engine provides

| Capability | Description |
| --- | --- |
| **Extension System** | First-class runtime plugins with full lifecycle management (`initialize → start → stop → dispose`). |
| **Dispatcher** | Unified request routing — dispatch commands and queries through registered handlers. |
| **Hosted Services** | Long-running background services managed by the Engine lifecycle. |
| **Scheduler** | Cron-style and interval-based task scheduling with cancellation support. |
| **Task Manager** | Background task pool with cooperative cancellation via `CancellationToken`. |
| **Async Runtime** | Integrated asyncio runtime with thread-safe bridge for sync/async coexistence. |
| **Event Bus** | In-process event publishing and subscription. Sync and async variants available. |
| **EngineContext** | Shared runtime context passed to Extensions and Hosted Services, providing safe access to all Engine capabilities. |
| **Dependency Injection** | Constructor injection with automatic resolution from type hints. |

### What you decide

Your architecture. Your domain. Your database. Your UI framework. Sagittarius Engine provides runtime infrastructure — your application provides the business logic.

---

## Requirements

- Python **3.14** or higher
- Zero mandatory external dependencies (built on the Python Standard Library)

---

## Features

- **Zero mandatory external dependencies** — built on the Python Standard Library core.
- **Extension-based architecture** — extend the Engine at runtime with isolated, reusable plugins (`IExtension` | `IModule`).
- **Full lifecycle management** — deterministic startup and shutdown with ordered extension resolution.
- **Multi-layer Configuration** — `ConfigManager` with chainable `from_json()`, `load_json()`, `load_env()`, and `load_dict()`.
- **Domain Event System** — `IDomainEvent` and `BaseEvent` providing automatic UUID `event_id` and UTC `occurred_on` metadata.
- **Cooperative cancellation** — cancel long-running background tasks gracefully using `CancellationToken`.
- **Unified dispatcher** — route commands and queries through a single `app.dispatch()` call.
- **Multiple Event Bus strategies** — synchronous, thread-pool, and asyncio variants.
- **Remote Audit Dashboard (TUI)** — inspect live engine telemetry (tasks, extensions, health) from a separate terminal via the built-in HTTP telemetry server.

---

## Installation & Integration

### Option 1: Install from GitHub

```bash
pip install git+https://github.com/anhembedded/Sagittarius-Engine.git
```

### Option 2: Local Editable Mode

```bash
pip install -e .
```

---

## Quick Start

```python
from sagittarius_engine import App
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces import IConfig, IContainer, IEventBus

# 1. Initialize core infrastructure
container = StdLibContainer()
event_bus = MemoryEventBus()
app = App(container, event_bus)

# 2. Load configuration seamlessly from file
config = ConfigManager().load_dict({"app.name": "My App"}).load_env()
container.singleton(IConfig, config)
container.singleton(IEventBus, event_bus)

# 3. Boot and stop engine cleanly
app.boot()
print(f"Engine booted: {config.get('app.name')}")
app.stop()
```

---

## Examples

The `examples/` directory contains reference applications that demonstrate real-world Engine usage.

| Project | Directory | Description |
| --- | --- | --- |
| Student Management | `examples/student_management/` | Clean Architecture CLI + `pyside_mvc` QML desktop UI, real SQLite persistence, `IExtension`-based module registration, event-driven UI refresh. Rebuilt 2026-08-23 (`EPIC-002`) — see `.agents/context/examples.md` for the full breakdown. |

`student_management` is the only example. Six other rows this table used to list —
`desktop/`, `worker/`, `trading_bot/`, `websocket/`, `plugin_system/`, `rest_api/` — were
removed on 2026-08-23: none of those directories exist, and none is planned.

---

## Documentation

**The `docs/` tree this section used to describe does not exist** — it was deleted in commit
`a338d42` ("Remove outdated tutorials and examples") and never rebuilt (confirmed 2026-08-23,
`git ls-tree -r HEAD` shows 0 files under `docs/`). `mkdocs.yml` still declares `docs_dir: docs`,
so `mkdocs serve` will fail until either the tree is rebuilt or `mkdocs.yml`/
`requirements-docs.txt` are removed. Until then, treat `.agents/context/` (start at
[`.agents/ONBOARDING.md`](.agents/ONBOARDING.md)) as the authoritative documentation for this
repository.

For the one real sample app's own design notes, see `examples/student_management/docs/`.

---

## Running Tests

```bash
# Run the full test suite
pytest

# Run with coverage
pytest --cov=sagittarius_engine
```

UI tests need an offscreen Qt platform in headless environments:

```bash
QT_QPA_PLATFORM=offscreen pytest
```

---

## Contributing

Please review our [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on branch strategy, coding standards, testing requirements, and PR workflows.

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Commit your changes following the existing code style.
4. Open a pull request against `develop`.

Please ensure all tests pass and the documentation builds without errors before submitting.

---

## License

MIT License — see [LICENSE](LICENSE).
