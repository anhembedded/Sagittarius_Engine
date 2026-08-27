# EPIC-007: Runtime State Introspection & the Dashboard Question

- **Status**: 📋 **Proposed — design only, no implementation authorised**
- **Created**: 2026-08-27
- **Priority**: TBD by maintainer (§8 argues P1 for milestone `A`/`B`, and *not yet* for `D`)
- **Category**: Observability / Diagnostics
- **Related**: `EPIC-005` (trace recorder — owns the **time axis**), `EPIC-006` (wiring
  diagnostics — owns the **structure**), `BUG-010` (post-boot registration strands an
  extension silently — this epic gives it a visible marker)

---

## 0. The one-paragraph version

The request is *"a dashboard so I can watch my app run and spot red flags early."* Two thirds
of that already ships: `EPIC-006` answers *is it wired right* and `EPIC-005` answers *what
happened and when*. The missing third is **state** — a cheap, serialisable, whole-engine
snapshot of what is live *right now*, which no API in this repository returns and which every
item on the request list needs. Build that first, as a data structure with no UI attached,
plus a catalogue of **detectors** that turn a snapshot into findings. Ship it as terminal
output. Only then ask whether pixels are worth adding — and if they are, put them in a
**separate process**, never inside the app being observed.

---

## 1. The one distinction the whole design turns on

The request mixes three questions that need three different data models. This engine has
already learned that the hard way once, and the previous dashboard was deleted for exactly
this reason (`readme.md`, the note dated 2026-08-25; `EPIC-005` §2).

| | **Structure** | **State** | **Stream** |
| :--- | :--- | :--- | :--- |
| The question | *"is it wired right?"* | *"what is it doing **now**?"* | *"what happened, and why?"* |
| Changes | once, at readiness | continuously, but **bounded** | continuously, **unbounded** |
| Shape | a graph | a set of rows + counters | timestamped records |
| Read by | one pass | polling, 1 Hz | a tap on the hot path |
| Cost | free | microseconds per poll | needs a ns budget |
| **Status here** | ✅ `EPIC-006` | ❌ **does not exist** | ✅ `EPIC-005` |

**The deleted dashboard used one model — snapshot polling — for all three.** That is why it
could never answer *"why did task B miss its deadline"* (a snapshot has no time axis, see
`EPIC-005` §1) and why it was simultaneously over-built for the static half (structure does
not change after readiness, so polling it is pure waste).

So: **one dashboard, three panes, three transports.** The static pane is a request/response
read taken once. The live pane polls a snapshot. The timeline pane is a button that says
*record 10 seconds → open in Perfetto*, because `EPIC-005` §5 already decided we do not build
a timeline renderer and nothing about this request changes that argument.

---

## 2. The request, mapped honestly onto what exists

Every ✅ below was read in the source on 2026-08-27, not remembered.

### 2.1 Static

| Requested | Where it already lives | Gap |
| :--- | :--- | :--- |
| Events registered / not registered | `EventRegistry.all()` × `IEventBus.subscriptions()` | ✅ none — this is `EPIC-006`'s A1/A2/A3 three-way join |
| *Which callback* for each event | `bus.subscriptions()` returns the callables; `__qualname__`, `__module__`, `inspect.getsourcefile/getsourcelines` give a clickable `file:line` | ⚠️ nothing formats it; a `lambda`/`partial` degrades (§6.4) |
| Container contents — abstract vs concrete | `IContainer.registrations()` → `Registration(abstract, concrete, lifetime, instantiated)` | ✅ none — this API is *exactly* the request |
| Config | `IConfig.get_all()` | ⚠️ **no provenance, no redaction** — both mandatory (§6.5) |
| Sub-tasks / sub-threads | `TaskManager.tasks`, `threading.enumerate()`, pool name prefixes | ⚠️ no read API; direct access races (§6.1) |
| Threads vs coroutines | `threading.enumerate()` + `asyncio.all_tasks(loop)` | ❌ nothing joins them |
| Extensions and their lifecycle state | `ExtensionManager.registered_extensions` / `sorted_extensions`; `ExtensionDescriptor` | ❌ **no per-extension state** — see `BUG-010` |

### 2.2 Runtime

| Requested | Where it already lives | Gap |
| :--- | :--- | :--- |
| Task running | `TaskManager.get_active_tasks()`, `TaskState` | ✅ mostly |
| Task not running / finished | `TaskManager.tasks` | ⚠️ **capped at 50** by `task_manager.max_retained_tasks` (§6.2) |
| Task registered | — | ⚠️ a task is spawned, never "registered"; scheduled *jobs* are the closest concept, and `Scheduler` exposes no accessor (§6.1) |
| Hosted services | `HostedServiceManager.services` / `.started_services` | ❌ a service that dies **after** `start()` emits nothing and is caught nowhere — stated outright in `diagnostics/runtime.py`'s docstring |
| Engine lifecycle state | `EngineLifecycle.state` (`EngineState`) | ✅ none |
| **Dynamic memory** | — | ❌ nothing, **and mostly should stay that way — see §3** |

---

## 3. The one part of the request to push back on: "dynamic memory"

The engine cannot answer *"how much memory does my app use"* better than `tracemalloc`,
`memray`, or `psutil`, and building a worse version inside the engine is precisely the mistake
`EPIC-005` §5 exists to prevent. Process RSS is one number from `resource.getrusage()`
(stdlib, POSIX) or `psutil` (optional) and belongs in a header bar, not in a subsystem.

**What the engine *can* answer, and nothing else can: occupancy of the bounded structures it
owns.** That is the real leak detector, and it is nearly free:

| Structure | Its bound | What a rising number means |
| :--- | :--- | :--- |
| `TaskManager.tasks` | `max_retained_tasks` (default 50) | live count climbing → tasks are being spawned faster than they finish |
| `TraceRecorder._buffer` | `capacity` (100 000) | `_dropped > 0` → **you are silently losing trace records** |
| `Scheduler.jobs` | *unbounded* | length climbing → jobs re-added faster than they run |
| `bus._handlers[name]` | *unbounded* | handler count per event climbing → **subscribe leak**; the classic Qt defect, a view that subscribes on open and never `off()`s on close |
| asyncio loop | *unbounded* | `len(asyncio.all_tasks())` climbing → coroutines never awaited to completion |
| `TraceServer` per-connection queue | *unbounded, documented* | queue depth → a client that stopped reading |

Six real leak signals, all O(1) or O(n)-over-something-small, all specific to this engine.
That is the honest, buildable version of *"dynamic memory of this app"*, and it is more useful
for finding a red flag than an RSS graph is.

---

## 4. Proposed architecture

```text
engine process (stdlib only)                        consumers (optional, separate)
┌────────────────────────────────────────┐
│ App                                    │
│  ├ EventRegistry     ─┐                │
│  ├ IContainer        ─┤                │        ┌───────────────────────────┐
│  ├ ExtensionManager  ─┤  Layer 0       │        │ sagittarius-doctor --watch│
│  ├ TaskManager       ─┼→ EngineSnapshot│        │   (terminal, milestone B) │
│  ├ Scheduler         ─┤  (pull only)   │        └───────────────────────────┘
│  ├ HostedServices    ─┤      │         │
│  ├ AsyncRuntime      ─┤      ▼         │─ws────▶┌───────────────────────────┐
│  └ IConfig           ─┘  Layer 1       │  snap  │ dashboard client          │
│                          Detectors     │  shot  │   (milestone D, separate  │
│                          → Finding[]   │        │    process, IF justified) │
│                                        │        └───────────────────────────┘
│  └ TraceRecorder ──────── stream ──────│─ws────▶┌───────────────────────────┐
│      (EPIC-005, unchanged)             │  trace │ Perfetto UI / OTel        │
└────────────────────────────────────────┘        └───────────────────────────┘
```

### 4.1 The four layers, and why they are separated

| Layer | What | Depends on |
| :--- | :--- | :--- |
| **0 · Introspection** | `EngineSnapshot` — frozen dataclasses of primitives, produced by pure reads | stdlib only |
| **1 · Detectors** | snapshot(s) → `Finding[]`, reusing `EPIC-006`'s `Finding`/`WiringReport` | layer 0 |
| **2 · Transport** | a `snapshot` message type on the **existing** `TraceServer` | layers 0–1, `websockets` |
| **3 · Client** | renders it | nothing in the engine |

**The rule that stops this repeating the 2026 failure: layers 0 and 1 must be complete,
tested, and useful with no client in existence.** `app.context.snapshot()` returns a dataclass
you can assert on in a pytest; `Detectors().run(snap)` returns findings you can print. If
layer 3 is deleted tomorrow, everything of value survives. The deleted dashboard had 100% of
its worth in pixels that never rendered, and no test noticed for two releases.

### 4.2 Why the transport is the existing `TraceServer`, not a new server

`EPIC-005` §1 already committed to this in writing — *"Snapshots stay, demoted to one message
type among several."* It also already solved the security question that a second server would
have to re-litigate: bind off-loopback without a token and it raises
`TraceServerConfigError` **at construction**, and an unauthenticated client is closed with
code `4401` before a single byte of data is sent. A dashboard leaks strictly more than a trace
stream does — class names, file paths, config keys — so it inherits that rule rather than
inventing a weaker one.

### 4.3 Why the client is a separate process, and not Qt

The decisive argument is not taste:

> **A Qt dashboard living inside the app freezes at exactly the moment the app freezes —
> which is the moment you need it.** `pyside_mvc/safety/ui_watchdog.py` exists because
> blocking the Qt main thread is a real, recurring defect in this codebase's consuming apps.
> An in-process UI diagnostic is blind to the top-ranked red flag it was built to catch.

Secondary reasons: it survives the crash it is diagnosing; it works over SSH and headless; it
adds no UI-toolkit dependency to a wheel whose headline feature is *zero mandatory
dependencies*. If a GUI is built, a stdlib `http.server` serving one self-contained HTML file
beats every framework here — no build step, no npm, nothing to keep in sync.

### 4.4 Constraint check

- `tests/test_architecture.py` forbids `kernel/` importing `extensions/`. **Resolved without a
  kernel change**: the collector lives in `extensions/` and reads the context from outside.
  The kernel only gains small read accessors (§6.1), which is not a dependency.
- Zero mandatory dependencies: layers 0–1 are stdlib. Layer 2 needs `websockets`, already a
  declared dependency for `sagittarius-trace`. Layer 3 ships as an extra or a separate package.
- Off ⇒ free. A `DashboardExtension` that is not registered costs nothing; registered but with
  no client attached costs nothing per operation, because **the snapshot is pull-only and
  nothing is ever pushed from a hot path.**

---

## 5. The detector catalogue — what "red flag" actually means

A dashboard that shows everything shows nothing. The deliverable is not a data dump, it is
this list. Six of the thirteen are free today.

| # | Red flag | Signal | Today |
| :--- | :--- | :--- | :---: |
| 1 | Handler bound to a name nothing emits (typo) | `EPIC-006` A2 | ✅ |
| 2 | Event emitted, nobody listening | `EPIC-006` R1 | ✅ |
| 3 | Handler raised — count and exception types | `EPIC-006` R2 | ✅ |
| 4 | Unbound dependency silently auto-constructed | `EPIC-006` B2 | ✅ |
| 5 | Engine not `READY`, or readiness never reached | `EngineLifecycle.state` | ✅ |
| 6 | Qt main thread frozen > 5 s, with its stack | `ui_watchdog.py` (logs only) | ✅ needs surfacing |
| 7 | Extension registered but never initialised | `registered` − `initialized` | ❌ **`BUG-010`** |
| 8 | Task in `RUNNING` past a threshold | `start_time` (⚠️ §6.3) | ❌ |
| 9 | Live task count climbing across snapshots | §3 | ❌ |
| 10 | Handler count for one event climbing (subscribe leak) | §3 | ❌ |
| 11 | Scheduler job overrun — `next_run` already past | §6.1 | ❌ |
| 12 | Trace records being dropped | `TraceRecorder._dropped` | ❌ not exposed |
| 13 | Hosted service died after `start()` | — | ❌ **no signal exists at all** |

Findings reuse `EPIC-006`'s `Finding` dataclass. **Do not introduce a second finding type** —
`EPIC-005`'s own defects `D3`/`D4` were two schemas drifting apart, and `audit/contracts.py`
exists specifically to stop that happening again.

#13 deserves its own milestone: `diagnostics/runtime.py` documents that a service which starts
and later dies *"emits nothing and is caught nowhere, so detecting it needs new instrumentation
in the runtime rather than observation of what already exists. That is a change to the
runtime's contract, not a diagnostic, and it does not belong in the same commit as one."*
That reasoning still holds — hence milestone `E`.

---

## 6. Hazards found while reading the code — read before implementing

Each was verified in source on 2026-08-27.

### 6.1 A naive scheduler snapshot is lossy, and will invent phantom bugs

`Scheduler._run()` rebuilds `self.jobs` as `active_jobs` — **excluding jobs that are due** —
spawns them, and only then re-appends the recurring ones. Since the rebind is a plain atomic
assignment, a reader touching `.jobs` without `self._lock` during that window sees a job
**missing**. A dashboard that reports "job vanished" once an hour sends someone hunting a bug
that does not exist.

*Required:* `Scheduler.jobs_snapshot()` taken under `_lock`, and `ScheduledJob` gaining a
stable `id`, a `name`, `last_run`, and `last_error` — none of which it has today, so two
`every(5).do(tick)` jobs are indistinguishable in any UI.

### 6.2 Finished-task history is capped at 50 and is not a history

`_cleanup_old_tasks()` evicts by insertion order once `_finished_task_ids` exceeds
`max_retained_tasks`. "Tasks that did not run" is therefore only true of the last 50.

*Required:* label the pane *"last 50 finished"*, and expose **monotonic counters**
(`spawned_total`, `completed_total`, `failed_total`) alongside the retained list. A counter
cannot lie about what it dropped; a list silently does.

### 6.3 `BackgroundTask.start_time` is set at construction, not at start

`__init__` does `self.start_time = datetime.now(UTC)` while `status` is still `PENDING`. For a
task queued behind twenty others in a 20-worker pool, `now - start_time` measures **queue
time**, not run time — so detector #8 would report a phantom stuck task.

*Required:* separate `queued_at` from `started_at`, set the latter at the `RUNNING`
transition. Queue time is itself worth showing (it is pool starvation), but conflating the two
makes both meaningless.

### 6.4 Handler identity degrades, and must degrade visibly

`bus.subscriptions()` hands back callables. A module-level function or a bound method yields a
clean `module.Class.method` and a `file:line`. A `lambda` yields `<lambda>`; a
`functools.partial` yields nothing useful. Render what is available and mark the rest
`<lambda> at path/to/file.py:88` — never a blank cell, which reads as *"no handler"*.

### 6.5 Config must not be shipped raw — it is a credential leak

`ConfigManager.get_all()` merges `load_env()`, so it contains whatever is in the process
environment: `AWS_SECRET_ACCESS_KEY`, DB passwords, API tokens. Broadcasting that over a
socket is a security defect, not a feature.

*Required:* deny-by-default redaction on key patterns (`*password*`, `*secret*`, `*token*`,
`*key*`, `*credential*`, `*_dsn`) → `"***"`. And add **provenance** — which source won for
each key. Provenance is frequently the actual bug being hunted (*"why is it using the default?
— because the `.env` never loaded"*), and `ConfigManager` does not currently report it.

### 6.6 A third-party bus is indistinguishable from an empty one

`IEventBus.subscriptions()` ships a concrete `return {}` default so that buses implemented
outside this repository keep working. The interface documents the probe:

```python
introspectable = type(bus).subscriptions is not IEventBus.subscriptions
```

*Required:* use it, and render *"this bus does not support introspection"* rather than an
empty list, which reads as *"you have no handlers"* — a false red flag of the worst kind.

### 6.7 The snapshot must never resolve, construct, or start anything

The rule `IContainer.registrations()` already states in its own docstring — *describing a
registration must not construct it* — is binding on every collector here. A diagnostic that
opens a database connection because someone clicked a tab is a catastrophe, and it also makes
the tool unusable at boot, which is where it is worth most.

*Corollary:* `EngineSnapshot` holds **primitives only**. No live task objects, no `type`
objects, no callables — a snapshot that references a task keeps it alive, and a debugging tool
that leaks memory is a joke. Convert `type` → `"module.QualName"` at capture. This also makes
it serialisable by construction rather than by a later, drifting encoder.

---

## 7. Snapshot design notes

- **Poll at 1 Hz, no faster.** Cost is not the constraint — the collector takes the same locks
  the scheduler and task manager take, so poll rate is a *correctness* concern.
- **Every snapshot carries a monotonic `seq` and a wall clock.** Without it a client cannot
  distinguish *"nothing changed"* from *"the connection died"* — the exact failure a polling
  dashboard hides best.
- **Full snapshots in v1; deltas are a later optimisation.** A few KB at 1 Hz is not a problem
  worth a diffing protocol.
- **Detectors compare consecutive snapshots.** #9, #10 and #12 are *trends*, not values — a
  detector holding the previous snapshot is the whole mechanism, and it is why `Detectors` is
  a stateful object rather than a function.

---

## 8. Proposed milestones

| ID | Milestone | Ships | Priority |
| :--- | :--- | :--- | :---: |
| **A** | Introspection read API — `EngineSnapshot` + collectors + the missing accessors (§6.1–§6.5) | a dataclass and passing tests, **no UI** | P1 |
| **B** | Detector catalogue — §5 rows 7–12, on `EPIC-006`'s `Finding` type | `sagittarius-doctor --watch`, terminal output | P1 |
| **C** | Transport — `snapshot` message type on the existing `TraceServer` | remote read, same auth rule | P2 |
| **D** | Client — **only if `B`'s terminal output proves insufficient** | separate process, stdlib `http.server` + one HTML file | P3, gated |
| **E** | Hosted-service liveness instrumentation (§5 #13) | a runtime contract change, on its own | P2 |

**`A` and `B` are the whole recommendation.** They are a few hundred lines, they are stdlib,
they are testable without a UI, and they deliver every red flag in §5 that the engine can
currently see. `D` is deliberately gated: after `B` ships, the honest question is whether a
terminal report at 1 Hz already answers *"is my app behaving"* — and it may well.

---

## 9. Open questions for the maintainer

1. **Does milestone `B`'s terminal output settle it?** If yes, `C` and `D` never happen, and
   that is a *good* outcome — cf. `EPIC-005` §5 choosing Perfetto over a bespoke viewer.
2. **Is `BUG-010` fixed inside milestone `A`, or only surfaced by it?** A per-extension state
   field makes the strand *visible*; making a post-boot registration *retry* is a separate
   behavioural change.
3. **Does the live pane need to reach a `pyside_mvc` app's UI-thread health (#6),** or is the
   existing watchdog log enough? Surfacing it means the snapshot reaches into an extension,
   which is a layering question worth answering before, not during.
4. **Is a `.sagsnap` recording wanted** — snapshots appended to a file for later replay — or is
   live-only sufficient? `EPIC-005` already established that attach-late-and-still-see-history
   is the single most valuable property of the trace recorder; the same argument may apply here.
