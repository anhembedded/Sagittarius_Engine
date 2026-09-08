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
- **Trace recording** — `app.context.enable_tracing(TraceRecorder())` records what ran and for
  how long into a bounded ring buffer (~157 ns per record, monotonic clock). `sagittarius-trace
  attach ws://…` streams it live from outside the process — including what happened *before* you
  attached — and saves a `.sagtrace` that opens in Perfetto or replays into OpenTelemetry.
  See below.
- **Runtime state console** — `StateConsoleExtension` answers *"what does this application look
  like right now?"*: wiring, registrations, live tasks, thread-pool occupancy, and (opt-in) a
  dead-letter queue and watched state machines. `sagittarius-trace snapshot ws://…` reads it as
  text, or open the full PySide6+QML dashboard. Detached cost is unmeasurable — nothing runs
  until a client asks. See below.

> A **Remote Audit Dashboard (TUI)** was listed here until 2026-08-25 — "inspect live engine
> telemetry from a separate terminal via the built-in HTTP telemetry server". Every part of that
> sentence was wrong: there was no HTTP telemetry server (telemetry moved to WebSocket in
> `f0247bd` and the CLI was never updated, so it polled `http://localhost:9999` against a socket
> that speaks WebSocket), and neither client worked at all. `EPIC-005` rebuilt the recording half
> as the trace recorder above; `EPIC-007` rebuilt the live-inspection half properly as the
> runtime state console above, with real end-to-end tests against a live server this time — the
> original dashboard and both its non-functional clients were deleted on 2026-08-26.

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

### Watching a running application

Everything above inspects structure, in one pass at readiness. Two further checks watch
behaviour for the life of the process, and are opt-in for that reason:

```python
app.use(DiagnosticsExtension(watch_runtime=True))
```

- **R1** — an event was emitted and **nothing was listening**, with the line it came from. Not
  the same as the static check: this one fires only when something really published into the
  void.
- **R2** — a handler **raised**, how many times, and every exception type. The bus still
  isolates the failure so the other subscribers are notified; R2 makes it countable instead of
  one log line among thousands.

An application that leaves it off pays nothing measurable per emit; one that turns it on pays
about 98 ns.

Step-by-step for adopting it in your own project — writing the factory, the first run,
CI, and every way it refuses to run:
[`.agents/context/diagnostics_usage.md`](.agents/context/diagnostics_usage.md).

Full reference, including every check and its severity:
[`.agents/context/diagnostics.md`](.agents/context/diagnostics.md).

---

## Recording what your application did — `sagittarius-trace`

`sagittarius-doctor` above answers *"is this wired correctly?"* — a structural question, asked
once. This answers a different one: **"what actually happened, and how long did it take?"**

The model is [SEGGER SystemView](https://www.segger.com/products/development-tools/systemview/),
the RTOS trace viewer, which is really two things: a **recorder** that captures timestamped
events off the target at near-zero cost, and a **viewer** that draws them. This engine builds
the recorder and deliberately does **not** build the viewer — Perfetto and OpenTelemetry render
timelines better than a bespoke UI would, and the half only a framework can supply is knowing
the meaning of its own lifecycle.

### Turn it on — before `boot()`

```python
from sagittarius_engine.extensions.audit.recorder import TraceRecorder

app = App(container, event_bus)
app.context.enable_tracing(TraceRecorder())   # ← before boot()
app.boot()
```

Off by default. The ordering is not a style preference: extension `register`/`boot` spans only
exist if the recorder does before the extensions start, and those spans are the answer to *"why
does startup take four seconds"*.

### Two kinds of record, and the difference is the point

```console
$ python examples/trace_demo.py
  captured         : 24 records
  closed spans     : 10
  dropped (evicted): 0
  by lane          : {'user': 12, 'dispatch': 12}
  slowest span     : startup-warmup @ 10.13 ms
```

**The engine instruments itself.** One `app.dispatch()` produces four records sharing one
correlation id, the handler's interval nesting inside the dispatch total's:

```
[   11.915 ms] dispatch   GreetQuery cid=1     ← dispatch total opens
[   11.921 ms] dispatch   GreetQuery cid=1     ← handler opens
[   14.025 ms] dispatch   GreetQuery cid=1     ← handler closes,  dur 2132847 ns
[   14.033 ms] dispatch   GreetQuery cid=1     ← dispatch closes, dur 2156468 ns
```

That is the half a generic profiler cannot produce: `py-spy` sees `_dispatch_inner()`, not
*"query `GreetQuery`, through middleware, into its handler"*.

**Your application marks its own work**, and the framework knows about none of it:

```python
ctx.trace.mark("order-filled", price=101.5)          # instant
with ctx.trace.span("strategy-eval", symbol="BTC"):  # span
    ...
```

### Attach to a process that is already running

```python
from sagittarius_engine.extensions.audit.infra.trace_server import TraceServer

server = TraceServer(app.context.recorder, host="127.0.0.1", port=9999)
server.start()
```

```console
$ sagittarius-trace attach ws://127.0.0.1:9999 --save session.sagtrace
attached to ws://127.0.0.1:9999 — protocol v1, capacity=100000, dropped_before_connect=0
[    0.012442] user     startup-warmup dur=10241788ns args={'cache': 'cold'}
[    0.012595] dispatch GreetQuery cat=query cid=1
[    0.014778] user     order-filled args={'price': 101.5}
```

**Those lines describe work that finished before the client connected.** The recorder retains
~100k records whether or not anyone is watching, so you attach *when it goes wrong* and still
see what went wrong. `py-spy` and `viztracer` attach to *now*; this attaches to *then*, and it
is the one property they cannot offer. If records were evicted before you arrived,
`dropped_before_connect` says so rather than presenting a trace with holes as complete.

Binding off-loopback without a token is refused at construction, not warned about in a log
nobody reads — a trace stream is everything your application records.

### Then open it somewhere real

```python
save_sagtrace_from_recorder("demo.sagtrace", app.context.recorder)
hello, records = load_sagtrace("demo.sagtrace")
write_perfetto_trace("demo.perfetto.json", records)
```

Drag `demo.perfetto.json` onto <https://ui.perfetto.dev> — it parses in the browser, nothing is
uploaded. For Jaeger / Tempo / Grafana / Datadog there is an OpenTelemetry exporter behind the
`[otel]` extra; the recorder, `.sagtrace` and Perfetto are stdlib-only and work without it.

### What it costs

| | |
| :--- | ---: |
| one record, tracing on | ~157 ns |
| the budget it was measured against | 2000 ns |
| a call site with tracing off | ~3 ns over an empty call |
| for scale, one `MemoryEventBus` emit | ~490 ns |

About a third of one event-bus emit. That is what makes leaving it on in production reasonable,
which is what makes attaching late possible at all.

### Try it without writing anything

`examples/trace_demo.py` is a runnable tour — record, save, convert, and optionally serve:

```bash
python examples/trace_demo.py            # record → .sagtrace → Perfetto file
python examples/trace_demo.py --serve    # …and hold a live server open
```

Step-by-step guide, including every way it can look broken when it is not:
[`.agents/context/tracing_usage.md`](.agents/context/tracing_usage.md).

Full reference — the design, the wire protocol, the overhead measurements:
[`.agents/context/tracing.md`](.agents/context/tracing.md).

---

## Watching a running application from outside it — the runtime state console

`sagittarius-trace` above answers *"what happened, and how long did it take?"* This answers a
different question: **"what does this application look like right now?"** — what is wired,
what is registered, what is alive, and what looks wrong about that, without reconstructing it
from a log.

### Attach it

```python
from sagittarius_engine.extensions.state_console import StateConsoleExtension

app.use(StateConsoleExtension(port=8781))
app.boot()
```

Rides the same `TraceServer` transport `sagittarius-trace attach` uses. Nothing runs on a
timer and nothing subscribes to anything — a snapshot is built only when a connected client
actually asks for one, so a detached application pays nothing measurable for having it turned on.

### Read it as text, or open the dashboard

```console
$ sagittarius-trace snapshot ws://127.0.0.1:8781
snapshot @ 1543.349494s
lifecycle: state=ready extensions=5/5 hosted=0/0 scheduler_jobs=0 (without_next_run=0)
events: 20
container: 13 registration(s), open_scopes=0
thread pools:
  background: 0/20 in flight, queue_depth=0, submitted=0, completed=0
bounded: ring=0/0 (dropped=0), tasks=0/50, subscriptions=2, gc_counts=[259, 11, 0]
config: 3 entries
detached
```

```bash
# the full five-screen PySide6+QML dashboard instead — Overview, Events & wiring,
# Container, Tasks & threads, Signals — behind an optional [dashboard] extra
scripts/run-console.ps1 -Attach ws://127.0.0.1:8781
```

### The Signals panel is opt-in, not discovered

A dead-lettered event (`ResilientEventBus`'s retry queue) and a rejected state-machine
transition are both visible only to whatever explicitly watches them:

```python
console.watch_dlq(resilient_bus)
console.watch_state_machine("EnrolmentFlow", flow)   # before driving it
```

Explicit rather than a subclass registry — guessing at which state machines exist has already
cost this codebase a rewrite once; naming one cannot be wrong the way discovering it can.

Step-by-step guide, including how to wire the Signals panel into your own application:
[`.agents/context/state_console_usage.md`](.agents/context/state_console_usage.md).

Full reference — every collected section, the security model, where the pieces are:
[`.agents/context/state_console.md`](.agents/context/state_console.md).

---

## Examples

The `examples/` directory contains reference applications that demonstrate real-world Engine usage.

| Project | Directory | Description |
| --- | --- | --- |
| Student Management | `examples/student_management/` | Clean Architecture CLI + `pyside_mvc` QML desktop UI, real SQLite persistence, `IExtension`-based module registration, event-driven UI refresh, and a headless mode with the runtime state console attached (`console.py --demo-faults`, `EPIC-007`). Rebuilt 2026-08-23 (`EPIC-002`) — see `.agents/context/examples.md` for the full breakdown. |

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
