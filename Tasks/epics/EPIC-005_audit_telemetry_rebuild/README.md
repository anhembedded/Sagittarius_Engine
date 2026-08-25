# EPIC-005: Audit Telemetry — Teardown, and Rebuild as a Realtime Trace Viewer

- **Status**: 📋 **Spec awaiting approval — nothing deleted, nothing implemented yet**
- **Created**: 2026-08-25
- **Priority**: P2
- **Category**: Observability / Diagnostics
- **Supersedes**: `TASK-002` (`AuditExtension` & CLI Inspector, marked ✅ Completed 2026-07-28 — see §2)
- **Related**: `TASK-033` (renamed `audit_dashboard.py` → `audit_dashboard_cli.py`)

---

## 1. The target: SEGGER SystemView, for a Python engine

The requested model is **SEGGER SystemView** — the RTOS trace viewer. That is a much more
specific and more ambitious thing than "a dashboard", and it changes the design at the root, so
it is worth being precise about what it means.

SystemView does not poll a target for its current state. It **records a continuous stream of
timestamped events** off the target with near-zero overhead, and reconstructs from that stream
what actually happened: which task ran, on which core, starting when, for how long, what
pre-empted it, what it was waiting on. The value is in the **time axis**. A CPU-load number
tells you the system is busy; a timeline tells you *task B misses its deadline because task A
holds the lock for 40ms every time the scheduler fires*.

Mapped onto this engine:

| SystemView concept | Sagittarius equivalent |
| :--- | :--- |
| Task / thread context lanes | OS threads from `ThreadManager`, asyncio tasks, the scheduler thread |
| Context switch | A background task begins/ends running on a thread |
| ISR enter/exit | Asyncio callback / event-bus handler invocation |
| API call trace | `app.dispatch()` → middleware chain → handler |
| User markers (`SEGGER_SYSVIEW_Mark`) | `ctx.trace.mark("order-filled")` from application code |
| RTT ring buffer | In-process ring buffer, drained by a publisher thread |
| Continuous vs single-shot recording | Streaming to a live client vs. a retained buffer pulled on attach |
| `.SVdat` recording file | `.sagtrace` — save, re-open, analyse post-mortem |

**The consequence for this epic:** the current design — and the one I specified in the first
draft of this document — is snapshot-based. `_get_full_state()` walks every subsystem and sends
a picture of *now*. That answers "what is the state?" and cannot answer "what happened?", which
is the only question a trace viewer exists for. **Snapshots stay, demoted to one panel.** The
event stream becomes the primary data model.

This also makes the observer cheaper rather than more expensive. Today every event triggers a
full re-collection (§2 D9). A trace recorder appends a fixed-size tuple to a ring buffer and
returns — the expensive work moves off the hot path entirely.

### Why the two-process split stays

```
engine process                                    operator's machine
┌───────────────────────────────────┐             ┌──────────────────────────┐
│ App                               │             │  audit viewer            │
│   ├─ instrumentation (spans)      │             │   ├─ timeline (lanes×t)  │
│   ├─ ring buffer  ← O(1) append   │──ws://─────▶│   ├─ event log           │
│   └─ publisher thread (drains)    │  trace      │   ├─ task stats          │
└───────────────────────────────────┘  stream     │   └─ live state panel    │
                                                  └──────────────────────────┘
```

The console must not die with the app it observes, must attach to an already-running process,
and must add no UI dependency to the engine. The engine side stays a normal `IExtension`, so an
app opts in with one line and pays nothing when it is off. None of that changes.

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
| D7 | **The GUI never ships.** `tools/audit_dashboard/` has no `__init__.py`, so `find_packages(include=["sagittarius_engine*","tools*"])` returns `['tools']` alone. A `pip install` yields the `sagittarius-audit` command but not the package it points at. | `find_packages(...)` → `['tools']` |
| D8 | **The framework hard-codes demo-app events.** `_subscribe_events()` subscribes `student.added`, `student.updated`, `student.deleted`, `report.completed` — `examples/student_management` domain events, from inside the engine. A layering inversion, and useless for any other app. | `audit_service.py:96-100` |
| D9 | **Every event triggers a full state re-collection and broadcast.** `on_state_changed` calls `_get_full_state()` — health query, all tasks, extensions, services, scheduler jobs, config and event-bus internals — then serialises and sends the lot. A task-heavy workload makes the observer a load source on the thing it observes. No coalescing, no rate limit, no delta. | `audit_service.py:69-79` |
| D10 | **Zero client tests.** All 13 audit tests cover the engine side. Nothing tests any client, which is how D1–D6 survived. | `pytest -k audit --collect-only` → 13 tests, all under `tests/extensions/` |

Smaller, same cleanup: `AuditService` reaches into privates (`eb._handlers`, `config._config`);
`get_full_config()` guesses at four attribute names and returns `{"error": ...}` as if it were
data; `AuditExtension` docstrings still say *"Telemetry **HTTP** Server"* from before the
WebSocket refactor; `auth_token` defaults to `None`; `run_dashboard.ps1` is Windows-only.

**Assessment.** The engine half is real and tested; the collection logic in `AuditService` is
the genuinely valuable part, and its *content* is worth keeping as a specification of what to
collect even though the class is replaced. The client half is a scaffold — correct-looking
Clean Architecture folders wired to nothing, with the one line that matters printing a `dict`.
**Both clients are 100% non-functional today.** `TASK-002` declared this ✅ Completed on
2026-07-28 without an end-to-end check.

Against the SystemView target the gap is larger still: there is **no time axis anywhere**.
Timestamps are `datetime.now().strftime("%H:%M:%S")` — second resolution, wall-clock, formatted
at capture into a string like `"[10:30:15] TaskStarted"`. Second-resolution strings cannot
reconstruct a timeline, and wall-clock is the wrong clock for measuring durations.

---

## 3. Scope of the teardown

Approved direction: **delete all of it, server included, and redesign from scratch.**

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

**Not touched:** `HealthExtension` (depended on, independently useful) and
`examples/student_management` (D8 only couples in the other direction). Instrumenting the
runtime (§4.3) does touch `runtime/`, `kernel/` and `middleware/` — that is new work, not part
of the teardown, and §7 keeps it bounded.

**Before deleting:** `git tag pre-epic-005-audit`, so the old tree stays recoverable without
archaeology.

---

## 4. Design

### 4.1 The trace model

Two record types, on one monotonic clock:

- **Instant** — a point in time. Task enqueued, event published, job fired, log line, user marker.
- **Span** — a begin/end pair with a duration. Task run, handler execution, middleware frame,
  dispatch, extension boot.

Every record carries: `t` (ns since session epoch, monotonic), `lane` (thread or asyncio task),
`cat` (category), `name`, a correlation `id`, and optional `args`. Spans additionally carry
`dur` on close. **Nothing is formatted at capture** — no `strftime`, no f-strings, no `str()`
of a payload. Formatting is the viewer's job.

Lanes are what makes the timeline readable, and they are the direct analogue of SystemView's
context lanes: one horizontal track per thread, spans drawn as bars, so pre-emption and overlap
are visible as geometry rather than inferred from a log.

**Clock.** `time.perf_counter_ns()` — monotonic, unaffected by NTP or DST, which is what
duration measurement requires. Wall-clock is captured **once** at session start to anchor the
epoch, so a recording can still be correlated with log files. Realistic resolution is ~1µs;
sub-microsecond claims would be dishonest in CPython, where the instrumentation call itself
costs more than the clock read.

### 4.2 Ring buffer, and why it is the whole design

```
hot path:   record() → append 8-tuple to deque(maxlen=N) → return     ~O(1), no I/O, no lock
publisher:  drain in batches → encode → websocket send                separate thread
```

A bounded `collections.deque` gives an atomic append under the GIL and evicts the oldest record
when full — no allocation growth, no unbounded memory, no lock on the hot path. This is what
directly repairs D9.

Two recording modes, both from SystemView:

- **Streaming** — publisher drains continuously to an attached client. Unbounded history, costs
  a socket.
- **Retained buffer** (default) — the engine always records the last N events (default 100k)
  whether or not anyone is watching. **A client that attaches after the interesting thing
  happened still sees it.** This is the single most valuable property of the whole design and
  the current implementation has no equivalent — attach late today and you see only "now".

**Overhead budget, enforced as an acceptance criterion:** < 2µs per record when enabled, and
**exactly zero** when disabled — the recorder resolves to a no-op object at boot, so a disabled
build pays one attribute lookup, not a branch per event.

### 4.3 What gets instrumented

This is the list that decides whether the tool is useful. Existing task events
(`TaskStarted`/`TaskCompleted`/`TaskProgressUpdated`/`TaskFailed`) already give part of it.

| Subsystem | Spans | Instants |
| :--- | :--- | :--- |
| Task manager | task run (start → complete/fail/cancel) | enqueued, progress, cancellation requested |
| Dispatcher | `dispatch()` total, each middleware frame, handler | — |
| Event bus | `publish()` total, each handler invocation | — |
| Scheduler | job execution | job fired, job missed/overrun |
| Extensions | `register`, `boot`, `shutdown` — per extension | — |
| Hosted services | `start`, `stop` | — |
| Health | check execution | status transition |
| App | boot sequence | ready, stopping |

Two things fall out of this for free and are worth naming, because they are the kind of thing
people actually reach for a tracer to answer:

- **Boot profiling** — per-extension `register`/`boot` spans answer "why does startup take
  4 seconds?" directly, as a bar chart of the boot sequence.
- **Middleware cost** — a span per middleware frame shows which one in the chain is expensive,
  per dispatch, which is currently unanswerable.

**Application instrumentation replaces D8 properly.** Instead of the framework hard-coding
`student.added`, the app instruments itself:

```python
ctx.trace.mark("order-filled", price=101.5)          # instant
with ctx.trace.span("strategy-eval", symbol="BTC"):  # span
    ...
```

The framework then knows about zero application events, and the app can put anything it likes
on the timeline next to the runtime's own lanes — exactly SystemView's user-marker model.

### 4.4 Wire protocol v1

Event-first. Every frame is one JSON object:

```jsonc
{
  "v": 1,                  // PROTOCOL_VERSION — client refuses a major mismatch, loudly
  "type": "trace",         // "hello" | "trace" | "snapshot" | "error"
  "seq": 42,               // monotonic; client detects gaps
  "data": [ ]              // batch of records for "trace"
}
```

- `hello` — once, on connect: protocol version, session epoch (monotonic + wall-clock anchor),
  clock resolution, lane table, buffer capacity, and whether records were already dropped.
- `trace` — a **batch** of records. Batching is what keeps a 10k-events/sec workload from
  becoming 10k websocket frames.
- `snapshot` — the current-state payload (extensions, services, health, config, CPU/RSS) on
  connect and every 10s. This is the old design, correctly demoted to one panel of several.
- `error` — server-side failure surfaced to the operator, rather than swallowed into a log line
  (today: `except Exception: self._logger.error(...)` in eleven places, and the client just
  sees a field quietly go missing).

The version handshake in `hello` is the direct fix for D1: a transport or schema mismatch must
fail **visibly at connect**, not degrade into a blank panel.

**One contract, imported by both sides.** D3/D4 exist because two hand-maintained schemas
drifted. There will be exactly one, in `sagittarius_engine/extensions/audit/contracts.py`:
frozen dataclasses with explicit `to_dict()`/`from_dict()` and `PROTOCOL_VERSION`, stdlib only
(the engine's domain rule is stdlib-only, and `pydantic` is broken on 3.14rc2 regardless). The
client imports them and does not redeclare them, so a field rename becomes a one-file problem
instead of a silent runtime mismatch. Types are real types — `cpu_percent: float`, not
`"12.3%"`.

### 4.5 Viewer

SystemView parity, in priority order:

1. **Timeline** — lanes × time, zoom and pan, spans as bars, click for detail. The centrepiece.
2. **Event log** — chronological, filterable by lane/category/name, and synchronised with the
   timeline cursor.
3. **Task statistics** — per task: run count, total/min/max/mean duration, share of wall time.
   This is where a periodic-task overrun becomes obvious.
4. **Load graph** — events/sec and CPU/RSS over the same x-axis as the timeline.
5. **Live state panel** — the current design's entire content, as one panel.
6. **Recording controls** — start/stop, save `.sagtrace`, open a saved file offline.

Client layering (D5 — no `try/except ImportError` stubs anywhere; the client depends on the
engine package outright and fails at startup with a real message if that import fails):

```
transport  →  decode + version check  →  contracts  →  trace store  →  renderer
```

Packaging fixes D6/D7: a real `__init__.py`, absolute imports, entry point at `...main:main`,
verified by building a wheel and running the command from a clean venv — the check `TASK-002`
skipped.

---

## 5. Proposal: export to Perfetto before building any timeline UI

A zoomable, pannable, multi-lane timeline widget with span detail is genuinely hard —
realistically the largest single piece of work in this epic, and the piece most likely to end
up mediocre.

The trace model in §4.1 is deliberately shaped like the **Chrome Trace Event format** (`ph: "X"`
complete events, `ph: "i"` instants, `pid`/`tid` lanes, `ts` in µs). Emitting that format is
roughly a 100-line encoder, and it means a `.sagtrace` recording opens directly in
[ui.perfetto.dev](https://ui.perfetto.dev) — a mature, fast, keyboard-driven trace UI with
zoom, pan, span search, flow arrows and SQL-based analysis, at zero build cost.

**Recommendation: make this Milestone C, before any custom viewer.** It de-risks the epic
almost entirely — if the instrumentation and the trace model are wrong, that is visible in
Perfetto within a day, before a line of UI is written. The custom viewer (Milestone D) then
only has to earn its keep on the thing Perfetto cannot do: **live streaming**. Perfetto opens
a finished recording; watching a running system as it runs is the reason to build our own.

The two are complementary, not alternatives: `pyqtgraph` (already a dependency) is the right
basis for the live timeline, and Perfetto covers post-mortem from day one.

---

## 6. Milestones

| ID | Scope | Done when |
| :-- | :--- | :--- |
| **A** | Teardown + `contracts.py` + protocol v1 + ring-buffer recorder + rebuilt transport | Old tree tagged and deleted; recorder unit-tested including eviction and drop-count; overhead benchmark meets §4.2; auth + readiness tests restored green; a raw `websockets` client receives a schema-valid `hello` + `trace` batch |
| **B** | Instrumentation of the §4.3 subsystems + app-facing `ctx.trace` API | Running the demo app produces spans for every listed subsystem; task-run spans reconstruct to the same durations the task manager reports; zero-overhead-when-disabled benchmark passes |
| **C** | `.sagtrace` record/save/load + **Perfetto export** | A recording of the demo app opens in `ui.perfetto.dev` and shows the boot sequence, task lanes and dispatch spans correctly |
| **D** | Live viewer (form per §8) + packaging + docs | `pip install dist/*.whl` in a clean venv, `sagittarius-audit` attaches to a running app and renders a live timeline; `.agents/context/` updated; `TASK-002` marked superseded |

Order matters. **C before D**: Perfetto validates the trace model against a viewer we did not
write, which is the cheapest possible way to find out the model is wrong. And within A/B, the
round-trip test comes before any rendering — D1–D4 are all "the pipe was never tested end to
end", so the test that would have caught them has to exist first.

---

## 7. Acceptance criteria

1. `sagittarius-audit`, installed from a built wheel into a clean venv, attaches to a running
   engine and renders a live timeline. *(D1, D6, D7)*
2. No `str(dict)` anywhere; every panel in §4.5 renders structured data. *(D2)*
3. A round-trip test asserts a real engine's frames decode into the expected contract objects.
   Renaming a contract field breaks it. *(D3, D4)*
4. No `try/except ImportError` fallback stubs; no import of any package outside this repo. *(D5)*
5. No framework module names an application-specific event. *(D8)*
6. **Overhead**: < 2µs per record enabled; a benchmark shows *no measurable difference* with
   tracing disabled. 100k events in 10s stays bounded in memory and drops oldest-first with an
   accurate drop count reported in `hello`. *(D9)*
7. Client and protocol have their own tests; `pytest -k audit` covers both sides. *(D10)*
8. Auth: connecting without a token when one is configured is rejected. Binding to anything but
   loopback without a token is refused at startup.
9. A version-mismatched client fails at connect with a clear message, not a blank panel.
10. A `.sagtrace` recording of the demo app's boot opens in Perfetto with correct lanes and
    nested spans.
11. **Attach-late works**: start the app, run a workload, *then* attach — the client shows the
    workload that already finished, from the retained buffer.

---

## 8. Open decisions — need your call

1. **Live viewer form** (Milestone D). Reframed by the SystemView target: a timeline is a
   graphical object, and `pyqtgraph` — **already a dependency** — is built for exactly this
   (zoom/pan on large datasets). A TUI can do event log and task stats well, but a lane-based
   timeline in a terminal is a compromise.
   **Recommendation: PySide6 + pyqtgraph for the viewer, plus a small TUI for the live-state
   panel over SSH.** Perfetto (§5) covers the headless case for post-mortem, which is most of
   what SSH access is needed for anyway.
2. **Where the client lives.** `tools/audit_dashboard/` (dev tool, out of the wheel) or
   `sagittarius_engine/extensions/audit/client/` (ships on `pip install`)?
   **Recommendation: the latter** — criterion 1 is otherwise unmeetable without a second
   distribution.
3. **Tracing on by default?** Retained-buffer recording is what makes attach-late work, but it
   is only free if §4.2's budget holds. **Recommendation: off by default for v1; revisit once
   the benchmark exists.**
4. **Auth default.** **Recommendation: token required whenever the bind address is not
   `127.0.0.1`** — this is criterion 8.
5. **`psutil`.** Optional import degrading to `"N/A"` today. Declared extra under `[audit]`, or
   drop CPU/RSS from v1?
6. **Instrumentation blast radius.** §4.3 touches `runtime/`, `kernel/`, `middleware/`. If any
   subsystem needs more than a decorator or a context manager to instrument, it becomes its own
   task rather than growing this epic.

---

## 9. Risks

- **This is now a much larger epic than a dashboard rebuild.** §4.3 instruments the whole
  runtime. Milestones C and D are independently useful, so the natural stopping points are real
  — but A+B+C is the minimum that delivers anything, and that is a bigger commitment than the
  original scope. Worth deciding deliberately.
- **13 green tests are deleted before their replacements exist.** Mitigated by the tag, and by A
  restoring auth + readiness coverage before B starts.
- **Overhead is the feature.** A tracer that perturbs what it measures is worse than none.
  Criterion 6 exists to make this non-negotiable; if the budget cannot be met in CPython, that
  finding should surface in A, not D.
- **CPython is not an RTOS.** The GIL means "concurrent" threads are often serialised, and
  timing granularity is ~1µs, not ~1ns. The timeline will show real scheduling behaviour, but
  the tool should not imply precision it does not have — lane geometry is honest, sub-µs
  measurement would not be.
