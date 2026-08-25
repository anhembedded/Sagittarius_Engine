# EPIC-005: Audit Telemetry — Teardown, and Rebuild as a Trace *Recorder*

- **Status**: ⏸️ **On hold — spec complete and approved in principle; deferred behind `EPIC-006`**
- **Created**: 2026-08-25 · **Revised**: 2026-08-25 (scope cut §5; then deferred §0.1)
- **Priority**: P2 — *behind `EPIC-006`, which answers the more urgent question*
- **Category**: Observability / Diagnostics
- **Supersedes**: `TASK-002` (`AuditExtension` & CLI Inspector, marked ✅ Completed 2026-07-28 — see §2)
- **Related**: `TASK-033` (renamed `audit_dashboard.py` → `audit_dashboard_cli.py`);
  **`EPIC-006`** (Wiring & Readiness Diagnostics — the work that goes first)

---

## 0.1 Why this is on hold

Nothing below is withdrawn — the analysis in §2 stands, the teardown in §3 is still the right
call, and the scope cut in §5 still holds. What changed is **priority**, once the maintainer
stated what the tool is actually for:

> *"…always detect anomalies early at runtime, and trace whether the system has stabilised,
> whether all events are loaded, what the handlers are…"*

Those are questions about **wiring correctness**, not about **execution cost**. A trace recorder
answers "what ran, and for how long". It cannot answer "is this handler bound to an event name
that exists". Both are worth having; only one of them is what was being asked for, and it is an
order of magnitude cheaper — see `EPIC-006` §1.2 for the comparison.

`EPIC-006` also has the stronger claim to the argument this epic makes for itself in §5: that
the framework's unique contribution is knowing the *meaning* of its own internals. Nothing
outside the engine can audit its DI wiring, whereas `py-spy`, `viztracer` and Perfetto already
cover much of what a tracer would do.

**Resume this epic when the live question becomes "why is it slow" rather than "why is it
wrong".** The specification is complete and does not need rework to be picked up.

---

## 0. The one-paragraph version

Both audit dashboard clients are 100% non-functional and have been since at least the WebSocket
refactor; the engine half works but answers the wrong question. Delete all of it. Rebuild the
**recorder** — semantic instrumentation of the engine's own lifecycle, on a monotonic clock,
into a bounded ring buffer — and **do not rebuild the viewer**. Export to Perfetto and
OpenTelemetry instead, because mature tools already render timelines better than we would, and
because the half only *we* can build is the semantic instrumentation, not the pixels.

---

## 1. The target, and the half of it we are actually building

The requested model is **SEGGER SystemView**, the RTOS trace viewer. SystemView is really two
things bolted together:

| SystemView half | What it does | Our decision |
| :--- | :--- | :--- |
| **Recorder** (RTT + instrumentation) | Captures timestamped task/ISR/API events off the target with near-zero overhead | **Build it.** Only the framework knows the meaning of its own lifecycle. |
| **Viewer** (the desktop timeline UI) | Renders lanes, spans, zoom/pan, statistics | **Borrow it.** Perfetto already is this, and better. |

That split is the whole revision in §5. Everything else about the SystemView model stands, and
it is what makes this different from the dashboard being deleted:

> SystemView does not poll a target for its state. It records a **continuous stream of
> timestamped events** and reconstructs what happened. **The value is in the time axis.** A
> CPU-load number tells you the system is busy. A timeline tells you that task B misses its
> deadline because task A holds the lock for 40ms every time the scheduler fires.

Mapped onto this engine:

| SystemView concept | Sagittarius equivalent |
| :--- | :--- |
| Task / thread context lanes | OS threads from `ThreadManager`, asyncio tasks, the scheduler thread |
| Context switch | A background task begins or ends running on a thread |
| ISR enter / exit | Asyncio callback, event-bus handler invocation |
| API call trace | `app.dispatch()` → middleware chain → handler |
| User markers (`SEGGER_SYSVIEW_Mark`) | `ctx.trace.mark("order-filled")` from application code |
| RTT ring buffer | In-process bounded ring buffer, drained by a publisher thread |
| Continuous vs single-shot | Streaming to an attached client vs. a retained buffer pulled on attach |
| `.SVdat` recording | `.sagtrace` → opens in Perfetto |

**Consequence for the design.** The current implementation is snapshot-based:
`_get_full_state()` walks every subsystem and sends a picture of *now*. That answers "what is
the state?" and can never answer "what happened?", which is the only question a trace tool
exists for. **Snapshots stay, demoted to one message type among several.** The event stream
becomes the primary data model.

This makes the observer *cheaper*, not more expensive. Today every event triggers a full
re-collection (§2, D9). A recorder appends a fixed-size tuple and returns.

### Why the two-process split stays

```
engine process                                      consumers
┌───────────────────────────────────┐          ┌──────────────────────────────┐
│ App                               │          │ sagittarius-audit  (live CLI)│
│   ├─ instrumentation (spans)      │─ws://───▶│ Perfetto UI        (timeline)│
│   ├─ ring buffer  ← O(1) append   │  trace   │ Jaeger / Tempo / Datadog     │
│   └─ publisher thread (drains)    │  stream  │                    (via OTel)│
└───────────────────────────────────┘          └──────────────────────────────┘
```

The recorder must not die with the app it observes, must attach to an already-running process,
and must add no UI dependency to the engine. The engine side stays a normal `IExtension`, so an
app opts in with one line and pays nothing when it is off.

---

## 2. Verified current state

Every row was reproduced on this branch (Python 3.14.0rc2, this repo's `.venv`), not inferred
by reading.

| # | Defect | Evidence |
| :-- | :--- | :--- |
| D1 | **The CLI client can never connect.** `audit_dashboard_cli.py` polls `http://localhost:9999/` with `urllib.request`. The engine only ever opens a **WebSocket** on that port — there is no HTTP server anywhere in `sagittarius_engine/` (`grep` for `HTTPServer`/`http.server`/`socketserver` returns nothing). It renders `🔴 Connection Error` on every refresh, forever. | Started the real `WebsocketBroadcaster`, called the CLI's own `fetch_telemetry()` against it → returned `None`. |
| D2 | **The GUI client renders a raw Python dict.** `MainWindow.on_telemetry_received()` is `self.log_area.append(str(data))` — the payload `str()`-dumped into a read-only `QTextEdit`. | `presentation/main_window.py:53` |
| D3 | **The client's Domain layer is dead code.** `EngineTelemetry`, `SystemHealth`, `EnvironmentMetrics`, `TaskDetail`, `ExtensionInfo` are defined, re-exported, and constructed *nowhere*. No mapper from payload to entity exists. | `grep` for each name outside `Domain/`: only `Domain/__init__.py` re-exports. |
| D4 | **The two schemas do not match**, so D3 could not be fixed by calling the constructor. Server sends `uptime`, `tasks`, `extensions`, `environment{os, os_release, python_version, cpu_percent, ram_mb}`; the entity expects `uptime_seconds`, `active_tasks`, `loaded_extensions`, `environment{hostname, os_name, python_version, memory_usage_mb: float, cpu_cores: int}`. Different names, different types (`cpu_percent` is a formatted `str` like `"12.3%"`), fields on each side the other never produces. | `audit_service.py:49-61` vs `Domain/entities.py` |
| D5 | **The client imports a package that does not exist.** `from src.base_event import ...`, `from src.interfaces import ICommand, IEventBus` — there is no `src/` here (it is `sagittarius_engine/`). Both sit behind `try/except ImportError` that substitutes stubs, so the use-case and event layers are decorative: `ICommand.execute` is `pass`, `IEventBus.emit` is `pass`. | `event/dashboard_events.py:4`, `application/receive_audit_use_case.py:8`; `ls src` → not found |
| D6 | **`sagittarius-audit` is broken twice.** (a) Bare inner imports (`from application...`) only resolve if cwd is `tools/audit_dashboard/` → `ModuleNotFoundError: No module named 'application'`. (b) The entry point `tools.audit_dashboard:main` binds `main` to the **module**, so `sys.exit(main())` would raise `TypeError: 'module' object is not callable` even after (a) is fixed. | Ran `.venv/bin/sagittarius-audit`; inspected the generated script and `pyproject.toml:31` |
| D7 | **The console script's dependencies are undeclared.** The wheel is zero-dependency by design, but `tools/audit_dashboard/main.py` imports `PySide6.QtWidgets` at module level. A real `pip install sagittarius-engine` therefore yields a `sagittarius-audit` command that dies on `ModuleNotFoundError: No module named 'PySide6'` before reaching any of its own code. The `[audit]` extra covers only `rich` (for the CLI); nothing declares the GUI's needs. | Installed the built wheel into a clean venv and ran the command |
| D8 | **The framework hard-codes demo-app events.** `_subscribe_events()` subscribes `student.added`, `student.updated`, `student.deleted`, `report.completed` — `examples/student_management` domain events, from inside the engine. A layering inversion, and useless for any other app. | `audit_service.py:96-100` |
| D9 | **Every event triggers a full state re-collection and broadcast.** No coalescing, no rate limit, no delta. A task-heavy workload makes the observer a load source on the thing it observes. | `audit_service.py:69-79` |
| D10 | **Zero client tests.** All 13 audit tests cover the engine side. Nothing tests any client, which is how D1–D6 survived. | `pytest -k audit --collect-only` → 13 tests, all under `tests/extensions/` |

**Correction (2026-08-25).** D7 originally read *"the GUI never ships — `find_packages(...)`
returns `['tools']` alone"*. **That was wrong.** `[tool.setuptools.packages.find]` in
`pyproject.toml` defaults to `namespaces = true`, so the build uses
`find_namespace_packages`, which resolves `tools.audit_dashboard` and all five of its
subpackages despite the missing `__init__.py`. The wheel does contain them — verified by
listing the built archive. The original claim came from calling `find_packages` by hand, which
defaults the other way. The corrected D7 above records what actually breaks the command instead.

Smaller, same cleanup: `AuditService` reaches into privates (`eb._handlers`, `config._config`);
`get_full_config()` guesses at four attribute names and returns `{"error": ...}` as if it were
data; `AuditExtension` docstrings still say *"Telemetry **HTTP** Server"* from before the
WebSocket refactor; `auth_token` defaults to `None`; `run_dashboard.ps1` is Windows-only.

Against the trace target the gap is wider still: **there is no time axis anywhere.** Timestamps
are `datetime.now().strftime("%H:%M:%S")` — second resolution, wall-clock, formatted at capture
into strings like `"[10:30:15] TaskStarted"`. Second-resolution strings cannot reconstruct a
timeline, and wall-clock is the wrong clock for measuring durations.

**Assessment.** The engine half is real and tested, and its collection logic is worth keeping as
a specification of *what* to collect even though the class is replaced. The client half is a
scaffold: correct-looking Clean Architecture folders wired to nothing, with the one line that
matters printing a dict. `TASK-002` declared this ✅ Completed on 2026-07-28 without an
end-to-end check — see §9.

---

## 3. Scope of the teardown

| Path | Notes |
| :--- | :--- |
| `tools/audit_dashboard/` | GUI client, 13 files |
| `tools/audit_dashboard_cli.py` | TUI client (D1 — never worked) |
| `sagittarius_engine/extensions/audit/` | `audit_extension.py`, `audit_service.py`, `ports.py`, `infra/websocket_broadcaster.py` |
| `tests/extensions/test_audit_extension.py`<br>`tests/extensions/test_audit_integration.py`<br>`tests/extensions/test_websocket_broadcaster_auth.py` | 13 currently-passing tests |
| `[project.scripts] sagittarius-audit` | Re-added in Milestone D at the correct target |

**Cost.** 13 green tests go, and `WebsocketBroadcaster` — the one piece that genuinely works,
including `TASK-017`'s token auth and the ephemeral-port/`_ready_event` handling that makes it
testable — gets rewritten. Milestone A must not lose those behaviours: the auth test and the
bind-readiness test come back as tests against the new transport.

**Not touched:** `HealthExtension` and `examples/student_management`. Instrumenting the runtime
(§4.3) does touch `runtime/`, `kernel/` and `middleware/` — new work, not teardown, bounded by
§7.6.

**Before deleting:** `git tag pre-epic-005-audit`.

---

## 4. Design

### 4.1 Two record types, one monotonic clock

An **instant** is a point in time (task enqueued, job fired, user marker). A **span** is a
begin/end pair with a duration (task run, handler execution, middleware frame, extension boot).
Every record carries `t` (ns since session epoch), `lane`, `cat`, `name`, a correlation `id`,
and optional `args`; spans carry `dur` on close.

**Nothing is formatted at capture** — no `strftime`, no f-strings, no `str()` of a payload.
Formatting is the consumer's job.

**Clock:** `time.perf_counter_ns()` — monotonic, immune to NTP and DST, which is what duration
measurement requires. Wall-clock is captured once to anchor the epoch so recordings correlate
with log files. Realistic resolution is ~1µs; claiming better would be dishonest in CPython,
where the instrumentation call costs more than the clock read.

### 4.2 The ring buffer is the whole design

```
hot path:   record() → append 8-tuple to deque(maxlen=N) → return     O(1), no I/O, no lock
publisher:  drain in batches → encode → send                          separate thread
```

A bounded `collections.deque` gives an atomic append under the GIL and evicts oldest-first — no
allocation growth, no lock on the hot path. That is the direct repair for D9.

Two modes, both from SystemView:

- **Streaming** — publisher drains continuously to an attached consumer.
- **Retained buffer** (default, 100k events) — the engine records whether or not anyone is
  watching, so **a consumer that attaches after the interesting thing happened still sees it.**
  Attach late today and you see only "now". This is the single most valuable property in the
  design, and it is the one thing `py-spy`/`viztracer` (§5) cannot give you either.

**Overhead budget, enforced as an acceptance criterion:** < 2µs per record enabled, and
**exactly zero** when disabled — the recorder resolves to a no-op object at boot, so a disabled
build pays one attribute lookup, not a branch per event.

### 4.3 What gets instrumented

This list is what decides whether the tool is useful, and it is the part **no generic profiler
can produce** (§5).

| Subsystem | Spans | Instants |
| :--- | :--- | :--- |
| Task manager | task run (start → complete/fail/cancel) | enqueued, progress, cancel requested |
| Dispatcher | `dispatch()` total, each middleware frame, handler | — |
| Event bus | `publish()` total, each handler invocation | — |
| Scheduler | job execution | fired, missed / overrun |
| Extensions | `register`, `boot`, `shutdown` — per extension | — |
| Hosted services | `start`, `stop` | — |
| Health | check execution | status transition |
| App | boot sequence | ready, stopping |

Two things fall out for free: **boot profiling** (per-extension spans answer "why does startup
take 4 seconds?" as a bar chart) and **middleware cost** (a span per frame shows which one in
the chain is expensive — currently unanswerable).

**Application instrumentation replaces D8 properly.** Instead of the framework hard-coding
`student.added`, the app instruments itself:

```python
ctx.trace.mark("order-filled", price=101.5)          # instant
with ctx.trace.span("strategy-eval", symbol="BTC"):  # span
    ...
```

The framework then knows about zero application events — exactly SystemView's user-marker model.

### 4.4 Wire protocol v1 — event-first

```jsonc
{
  "v": 1,                  // PROTOCOL_VERSION — consumer refuses a major mismatch, loudly
  "type": "trace",         // "hello" | "trace" | "snapshot" | "error"
  "seq": 42,               // monotonic; consumer detects gaps
  "data": [ ]              // batch of records for "trace"
}
```

- `hello` — once, on connect: protocol version, session epoch (monotonic + wall-clock anchor),
  clock resolution, lane table, buffer capacity, and drop count so far.
- `trace` — a **batch** of records. Batching keeps a 10k-events/sec workload from becoming 10k
  frames.
- `snapshot` — extensions, services, health, config, CPU/RSS. The old design, correctly demoted
  to one message type.
- `error` — server-side failure surfaced to the operator, rather than swallowed into a log line
  (today: eleven bare `except Exception: self._logger.error(...)` blocks, and the consumer just
  sees a field quietly go missing).

The version handshake is the direct fix for D1: a transport or schema mismatch must fail
**visibly at connect**, not degrade into a blank panel.

**One contract, imported by both sides.** D3/D4 exist because two hand-maintained schemas
drifted. There will be exactly one, in `sagittarius_engine/extensions/audit/contracts.py`:
frozen dataclasses with `to_dict()`/`from_dict()` and `PROTOCOL_VERSION`, stdlib only. The
client imports them and does not redeclare them. Types are real types — `cpu_percent: float`,
not `"12.3%"`.

### 4.5 Consumers

| Consumer | Role | Cost |
| :--- | :--- | :--- |
| **Perfetto** (`ui.perfetto.dev`) | The timeline. Zoom, pan, span search, SQL analysis, flow arrows. | ~100-line encoder |
| **OpenTelemetry** (optional extra) | Production observability — Jaeger, Grafana Tempo, Honeycomb, Datadog | A bridging exporter |
| **`sagittarius-audit`** (thin CLI) | Attach live: streaming event log, task stats, state panel, `--save trace.sagtrace` | Small — no timeline widget |

There is deliberately **no custom timeline UI**. See §5.

---

## 5. Scope cut: build the recorder, borrow the viewer

*Added on revision, 2026-08-25, and approved. This replaces an earlier "Milestone D: PySide6 +
pyqtgraph live timeline".*

**The reasoning.** No mainstream framework ships its own trace viewer. Django, FastAPI, Flask,
Spring Boot and Rails all ship *instrumentation hooks* and let established tools render.
The professional standard is OpenTelemetry: the framework emits spans, and Jaeger / Tempo /
Datadog draw them. Erlang/OTP's `observer` is the exception, not the pattern — and OTP is a
forty-year-old system that is an operating system in disguise.

In Python specifically, a large part of what a custom viewer would do **already exists and is
better than what we would write**:

- **`py-spy`** — attaches to a running process **by PID with no code changes**; `py-spy dump`
  prints every thread's stack right now, `py-spy record` produces flamegraphs.
- **`viztracer`** — deterministic function-call tracer that outputs **Perfetto-openable** JSON.

Weighed honestly, a bespoke timeline widget would be the largest single piece of work in this
epic, the most likely to end up mediocre, and substantially duplicated by the two tools above.

**What those tools cannot do — and only the framework can.** This is what Milestone B is for,
and why the epic is still worth doing:

1. **Semantic spans.** `py-spy` sees `_dispatch_inner()`. It does not know that is "query
   `GetRoster`, through three middleware, into its handler". Only the engine knows the meaning
   of its own lifecycle. "Db extension's `boot()` costs 412ms" is a framework fact; a generic
   profiler gives you a pile of function names instead.
2. **Correlation across thread and async boundaries.** A task enqueued on thread A and run on
   thread B is two unrelated stacks to a sampling profiler, and one span with a parent link to
   us.
3. **Always-on in production.** `py-spy` and `viztracer` are development tools. A ring buffer at
   ~µs cost runs permanently — which is what makes §4.2's attach-late property possible at all.

**Therefore:** build A + B + C (recorder, instrumentation, exporters) in full; ship D as a thin
attach CLI, not a GUI. Roughly 40% of the original cost for most of the value, and it removes
the "we spent weeks on a second-rate timeline" risk entirely.

### 5.1 OpenTelemetry exporter

For the stated goal — a framework credible in professional use — **OTel compatibility is worth
more than any bespoke viewer.** Professional shops already run Jaeger, Tempo, Grafana or
Datadog; emitting standard spans plugs straight into what they have, whereas a bespoke UI is
something they must learn and have no reason to trust.

Constraint: the engine's zero-mandatory-dependency rule holds. The core records into its own
stdlib ring buffer and knows nothing about OTel; a **separate optional exporter** under an
`[otel]` extra bridges records to the OTel SDK. Mapping:

| Sagittarius | OpenTelemetry |
| :--- | :--- |
| span | span (`start_time`/`end_time` from the monotonic clock, anchored to the wall-clock epoch) |
| correlation `id` / parent | span context / parent span id |
| lane (thread, asyncio task) | `thread.id` / `thread.name` resource + span attributes |
| instant / `ctx.trace.mark()` | span event |
| `cat` | instrumentation scope |
| `args` | span attributes |

Perfetto and OTel are complementary and neither is wasted: Perfetto is offline, zero-infra, and
free to open; OTel is live, aggregated, and already deployed where this framework wants to be
taken seriously.

---

## 6. Milestones

| ID | Scope | Done when |
| :-- | :--- | :--- |
| **A** | Teardown + `contracts.py` + protocol v1 + ring-buffer recorder + rebuilt transport | Old tree tagged and deleted; recorder unit-tested including eviction and drop-count; overhead benchmark meets §4.2; auth + readiness tests restored green; a raw `websockets` client receives a schema-valid `hello` + `trace` batch |
| **B** | Instrumentation of the §4.3 subsystems + app-facing `ctx.trace` API | The demo app produces spans for every listed subsystem; task-run spans reconstruct to the same durations the task manager reports; zero-overhead-when-disabled benchmark passes |
| **C** | Exporters: `.sagtrace` save/load, **Perfetto**, **OpenTelemetry** | A recording of the demo app opens in `ui.perfetto.dev` with correct lanes and nested spans; the same run appears as a trace in a local OTLP collector |
| **D** | `sagittarius-audit` thin attach CLI + packaging + docs | `pip install dist/*.whl` in a clean venv, the command attaches to a running app, streams the live event log and task stats, and saves a `.sagtrace`; `.agents/context/` updated; `TASK-002` marked superseded |

**Order matters.** C before D: Perfetto validates the trace model against a viewer we did not
write — the cheapest possible way to discover the model is wrong. And within A/B the round-trip
test comes before any rendering, because D1–D4 are all "the pipe was never tested end to end".

**D is now roughly a tenth of what it was.** The timeline widget it used to contain is Perfetto's
job.

---

## 7. Acceptance criteria

1. **Installs and attaches.** From a built wheel in a clean venv, `sagittarius-audit` attaches
   to a running engine, streams the live event log, and writes a `.sagtrace`. *(D1, D6, D7)*
2. **No `str(dict)` anywhere.** Every output is structured. *(D2)*
3. **Round-trip test.** A real engine's frames decode into the expected contract objects;
   renaming a contract field breaks the test. *(D3, D4)*
4. **No `try/except ImportError` fallback stubs**, and no import of any package outside this
   repo in the core path. *(D5)*
5. **No framework module names an application-specific event.** *(D8)*
6. **Overhead.** < 2µs per record enabled; no measurable difference when disabled; 100k events
   in 10s stays bounded in memory and drops oldest-first with an accurate drop count in `hello`.
   *(D9)*
7. **Both sides tested.** `pytest -k audit` covers recorder, protocol, exporters and client —
   not just the server. *(D10)*
8. **Auth.** Rejected without a token when one is configured; binding off-loopback without a
   token is refused at startup.
9. **Version mismatch fails loudly** at connect, never as a blank panel.
10. **Perfetto** opens a recording of the demo boot with correct lanes and nested spans.
11. **OpenTelemetry** — the same run appears in a local OTLP collector with correct parent/child
    structure, and the `[otel]` extra is genuinely optional: uninstalling it leaves the core
    working.
12. **Attach-late works.** Start the app, run a workload, *then* attach — the consumer sees the
    workload that already finished.

---

## 8. Open decisions

**Resolved on revision (2026-08-25):**

- ~~*Live viewer form*~~ → **No custom timeline.** Perfetto for post-mortem, OTel for production,
  a thin CLI for live attach. See §5.

**Still open:**

1. **Where the client lives.** `tools/` (dev tool, out of the wheel) or
   `sagittarius_engine/extensions/audit/client/` (ships on `pip install`)?
   *Recommendation: ships with the package* — criterion 1 is otherwise unmeetable without a
   second distribution.
2. **Tracing on by default?** Retained-buffer recording is what makes attach-late work, but only
   free if §4.2's budget holds. *Recommendation: off by default for v1; revisit once the
   benchmark exists.*
3. **Auth default.** *Recommendation: token required whenever the bind address is not
   `127.0.0.1`* — this is criterion 8.
4. **`psutil`.** Optional import degrading to `"N/A"` today. Declared `[audit]` extra, or drop
   CPU/RSS from v1?
5. **Instrumentation blast radius.** §4.3 touches `runtime/`, `kernel/`, `middleware/`.
   *Recommendation: if any subsystem needs more than a decorator or a context manager to
   instrument, it becomes its own task rather than growing this epic.*

---

## 9. Risks

- **This is still a larger epic than a dashboard rebuild.** §4.3 instruments the whole runtime.
  A, B and C are independently useful, so the stopping points are real — but A+B is the minimum
  that delivers anything.
- **13 green tests are deleted before their replacements exist.** Mitigated by the tag, and by A
  restoring auth and readiness coverage before B starts.
- **Overhead is the feature.** A tracer that perturbs what it measures is worse than none. If
  the budget cannot be met in CPython, that must surface in A, not D.
- **CPython is not an RTOS.** The GIL serialises much of what looks concurrent; granularity is
  ~1µs, not ~1ns. Lane geometry will be honest; the tool must not imply precision it lacks.
- **Do not re-grow the viewer.** The pressure to add "just a small timeline widget" will return.
  §5 is the standing answer; reopening it needs a reason `py-spy`, `viztracer` and Perfetto
  together cannot cover.
- **OTel is a dependency surface.** It must stay behind an extra and must never become a soft
  requirement of the core path — criterion 11 exists to enforce that.

---

## 10. Note for whoever picks this up

`TASK-002` marked this feature ✅ Completed on 2026-07-28 while **both of its clients were 100%
non-functional**, and that went unnoticed for a month. The repo's process discipline is good —
953 passing tests, bug-report workflow, doc-code-sync rules, a clean mypy baseline — and a
completely dead feature still shipped as done, because nobody ran it end to end once.

Criterion 1 is the direct guard against a repeat: **install from a built wheel into a clean venv
and actually run the command.** It is worth more to this repository than any single feature in
this epic. Do not close a milestone without it.

**Update (`49c941b`, landed after this spec was first written):** half of that guard now exists.
`scripts/verify_wheel_importable.py` builds the wheel, installs it into a throwaway venv,
`compileall`s it, and imports every shipped module — stronger than what this section asked for,
and it closes the defect class that shipped `v2.1.0` and `v2.2.0` broken.

The remaining gap is exactly the one `TASK-002` fell through: the guard sweeps
`sagittarius_engine` only, and it imports modules rather than resolving and invoking the declared
**console scripts**. `sagittarius-audit` fails three ways over — undeclared `PySide6` (D7), bare
inner imports needing a specific cwd, and an entry point binding a module rather than a function
(D6) — and none of the three is visible to an import sweep over a package the script does not
live in. Verified by installing the built wheel into a clean venv and running the command. See
`EPIC-006` §8; closing it is a few lines on infrastructure that already exists.
