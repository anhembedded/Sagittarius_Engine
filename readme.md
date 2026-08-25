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

- Python **3.12** or higher
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
- **Wiring diagnostics** — `sagittarius-doctor` reports mis-wiring (typo'd event names, unbound dependencies, dependency cycles, extensions that never initialised) as a build failure instead of a runtime surprise. See below.
A **Remote Audit Dashboard (TUI)** was listed here until 2026-08-25 — "inspect live engine
telemetry from a separate terminal via the built-in HTTP telemetry server". Every part of that
sentence was wrong, so the bullet is gone rather than reworded:

- There is no HTTP telemetry server. Telemetry moved to WebSocket in `f0247bd` and the CLI was
  never updated, so it polls `http://localhost:9999` against a socket that speaks WebSocket and
  reports a connection error on every refresh.
- Neither client works at all. The GUI connects but renders `str(payload)` into a text box; the
  `sagittarius-audit` command has never started for any consumer (`TASK-039`) and is no longer
  advertised.

`EPIC-005` covers the rebuild. This line comes back when there is something behind it.

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

## Checking your wiring — `sagittarius-doctor`

Installing the package puts one command on your `PATH`. Point it at a factory that returns a
booted `App` and it reports what does not add up:

```console
$ sagittarius-doctor myapp.main:build_app --handler-package myapp
Wiring report: 1 error(s), 1 warning(s), 3 info.
  [A2] ERROR: order.cancelld — a handler is subscribed to this name, but no event is
       registered under it — the handler can never run
        → did you mean "order.cancelled"?
  [B2] WARNING: ReportHandler.store — needs IReportStore, which is not bound. This does not
       raise: the container will construct IReportStore itself and inject that
        → bind IReportStore explicitly if a real implementation was intended
```

Both of those are defects that a passing test suite will not show you. The first is a handler
wired to a name nothing emits — it simply never runs. The second is worse: nothing raises. The
container constructs the annotation itself and injects an empty stand-in, so the application
starts, serves, and behaves wrongly.

### The arguments

| | |
| :--- | :--- |
| `factory` | `package.module:callable` returning a booted `App`. The working directory is put on `sys.path`, so a factory in the project you are standing in resolves. |
| `--handler-package` | Search this package for command/query handlers. Repeatable. **Without it, handlers are not checked** — nothing registers them, so there is nothing to enumerate. |
| `--expect-unheard` | An event you deliberately do not listen to; stops it being reported. Repeatable. |
| `--json` | Machine-readable. Boot output goes to stderr, so the document is never corrupted by an application that prints while starting. |
| `--strict` | Exit non-zero on warnings as well as errors. |

Exit codes: `0` clean · `1` findings · `2` the doctor could not run. The last is separate on
purpose — *"your wiring is wrong"* and *"the tool never started"* need different responses from
whoever reads the build.

### In CI

```yaml
- run: |
    pip install -e .
    sagittarius-doctor myapp.main:build_app --handler-package myapp --strict
```

This repository runs exactly that against `examples/student_management`.

### Two things worth knowing

**It boots your application.** Wiring does not exist until something wires it, so there is no
way to inspect it without running your own composition — the factory you name runs, with
whatever side effects it has. Point it at one that uses a throwaway database, the way
[`examples/student_management/doctor_target.py`](examples/student_management/doctor_target.py)
does.

**It does not resolve, construct, emit, or start anything to produce a finding.** Every check is
a set difference or a static signature walk. A diagnostic that built objects in order to
describe them would run half your application as a side effect of a question — and could not
honestly run at boot, which is the only place it is worth running.

### Inside the engine, instead of as a command

```python
from sagittarius_engine.extensions.diagnostics import DiagnosticsExtension

app.use(DiagnosticsExtension(fail_fast=True))
app.boot()   # report is logged; a wiring error aborts here
```

`fail_fast` defaults to `False` — an engine that refuses to start over a diagnostic is a worse
default than one that says loudly what is wrong.

Step-by-step for adopting it in your own project — writing the factory, the first run,
CI, and every way it refuses to run:
[`.agents/context/diagnostics_usage.md`](.agents/context/diagnostics_usage.md).

Full reference, including every check and its severity:
[`.agents/context/diagnostics.md`](.agents/context/diagnostics.md).

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

There is no separate doc site. The `docs/`/MkDocs tree this section used to describe was deleted
in commit `a338d42` ("Remove outdated tutorials and examples"), and the leftover `mkdocs.yml` /
`requirements-docs.txt` / `scripts/docs.{sh,bat}` that still pointed at it were removed rather
than rebuilt (`BUG-002`) — `.agents/context/` is comprehensive and current, and there is no
present intent to publish a public doc site.

Treat `.agents/context/` (start at [`.agents/ONBOARDING.md`](.agents/ONBOARDING.md)) as the
authoritative documentation for this repository.

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
4. Open a pull request against `main` — there is no `develop` branch, despite what this line
   said until 2026-08-25. See [CONTRIBUTING.md](CONTRIBUTING.md).

Please ensure all tests pass before submitting.

> This asked for "the documentation builds without errors" until 2026-08-25 — contradicting the
> Documentation section above, which records that the MkDocs site was deleted in `a338d42`.
> There is no documentation build. `BUG-002` removed `mkdocs.yml`, `requirements-docs.txt` and
> `scripts/docs.{sh,bat}`, but missed the root `Makefile`, whose three targets all invoked
> `mkdocs`; `make build` failed with `No module named mkdocs`. That file is deleted too.

---

## License

MIT License — see [LICENSE](LICENSE).
