# ADR-001: The runtime dashboard is a **state console**, not a second timeline

- **Status**: 🟠 Proposed
- **Date**: 2026-08-27
- **Category**: Observability / Diagnostics
- **Relates to**: `EPIC-005` (trace recorder — closed), `EPIC-006` (wiring diagnostics —
  5/6 done), `TASK-002` (the deleted dashboard)
- **Decides**: what the tool *is*, what data it carries, and how that data leaves the
  process. **Does not decide** what renders it — see [`ADR-002`](ADR-002_state_console_client_ui_framework.md).

---

## 1. Context

### 1.1 What was asked for

> *"A dashboard tool for this engine — when an app uses this engine, I could see how the
> app works. Static: events registered / not registered and their callbacks; sub-tasks and
> threads; all config; everything in the container (which base class, which concrete);
> threads or coroutines. Runtime: tasks running, tasks not running, tasks registered,
> dynamic memory. The main purpose is that I can check my app at runtime and spot red-flag
> behaviour early."*

### 1.2 This repository has already deleted one dashboard, for reasons that still bind

`EPIC-005` tore out `tools/audit_dashboard/`, `tools/audit_dashboard_cli.py` and
`AuditService` after reproducing ten defects. Four of them are not bugs in that code — they
are properties of the *shape* it had, and any new dashboard inherits them unless the shape
changes:

| Ref | The defect, restated as a constraint on this ADR |
| :--- | :--- |
| **D9** | Every emitted event triggered a full state re-collection and broadcast. The observer became a load source on the thing it observed. |
| **D3 / D4** | Producer and consumer each hand-maintained their own idea of the payload. They drifted until the consumer was reading fields the producer had stopped sending. |
| **D7** | The client imported `PySide6` at module scope inside a zero-dependency wheel, so the advertised command died on `ModuleNotFoundError` in any clean install. |
| **D10** | Zero client tests. That is *how* D1–D6 survived two releases. |

`EPIC-005` §5 then ruled, and the ruling was approved:

> **Build the recorder, borrow the viewer.** No mainstream framework ships its own trace
> viewer. A bespoke timeline widget would be the largest single piece of work in the epic,
> the most likely to end up mediocre, and substantially duplicated by `py-spy`, `viztracer`
> and Perfetto.

**That ruling is not withdrawn by this ADR.** It is load-bearing, and §2.1 below keeps it.

### 1.3 But the ruling has a hole, and the request lands exactly in it

`EPIC-005` §5's argument is entirely about the **time axis** — spans, durations, lanes,
flamegraphs. Every tool it names as "better than what we would write" renders *time*:

- `py-spy` samples stacks. It sees `_dispatch_inner()`. It does not know that frame is
  "query `GetRoster`, through three middleware, into its handler".
- `viztracer` traces function calls into a Perfetto-openable file.
- Perfetto draws lanes and nested spans.

**None of them can answer a single question in §1.1.** Perfetto cannot show what is bound
in a DI container. `py-spy` cannot tell you an event name has a handler subscribed to a
misspelling of it. No external profiler knows what an "extension" is, let alone that one is
registered-but-never-initialised.

`EPIC-005` §5 names this itself, as the reason the recorder was worth building at all:

> **Semantic spans.** … Only the engine knows the meaning of its own lifecycle.

The same sentence justifies a state console, more strongly — because for *state* there is
no external tool at all, not even a mediocre one.

### 1.4 Roughly 70% of the data already exists and is already public API

| Question from §1.1 | Already answered by | Since |
| :--- | :--- | :--- |
| Which events are declared? | `EventRegistry.all()` → `EventEntry(event_name, event_class, module)` | `EPIC-008` (Elite), ported |
| Which are subscribed, and to what callback? | `IEventBus.subscriptions()` → `{name: (handler, …)}` | `EPIC-006A` |
| Subscribed to a name that does not exist (typo)? | check **A2**, with a `difflib` near-match hint | `EPIC-006B` |
| Declared but unheard / multiple handlers / string-subscribed? | checks **A1**, **A3**, **A5** | `EPIC-006B` |
| Container: abstract → concrete, lifetime, built yet? | `IContainer.registrations()` → `Registration(abstract, concrete, lifetime, instantiated)` | `EPIC-006A` |
| Container: unsatisfiable dependency, cycle? | checks **C1**, **C2**, **C3** | `EPIC-006B` |
| Handler that cannot be constructed? | checks **B1**, **B2**, **B3** | `EPIC-006D` |
| Extension registered but never initialised? | check **D1** | `EPIC-006B` |
| Hosted service registered but never started? | check **D2** | `EPIC-006B` |
| Scheduler job that will never fire? | check **D3** | `EPIC-006B` |
| Event emitted with nobody listening (at runtime)? | check **R1**, with the first emit site | `EPIC-006F` |
| Handler that raised? | check **R2**, with exception types and count | `EPIC-006F` |
| How long did anything take? | `TraceRecorder` spans → `.sagtrace` → Perfetto / OTel | `EPIC-005B/C` |

**Consequence for scope.** The tool being asked for is overwhelmingly a *presentation and
transport* problem over data the engine already exposes — not a new instrumentation
programme. Anything in it that looks like new instrumentation deserves suspicion.

### 1.5 There is an empty seat reserved in the protocol

```python
# sagittarius_engine/extensions/audit/contracts.py:44
class MessageType(StrEnum):
    HELLO = "hello"
    TRACE = "trace"
    SNAPSHOT = "snapshot"    # <-- declared; constructed nowhere, handled nowhere
    ERROR = "error"
```

`grep` across `sagittarius_engine/` and `tests/` finds `MessageType.SNAPSHOT` referenced at
its own definition and nowhere else. `EPIC-005` §1 explains why it is there:

> **Snapshots stay, demoted to one message type among several.** The event stream becomes
> the primary data model.

The seat was left for exactly this feature. Taking it, rather than opening a second
transport, is the difference between one protocol with two message types and two protocols
that will drift — which is D3/D4 restated.

---

## 2. Decision

### 2.1 The tool is a **state console**. The time axis stays where it is.

It answers *"what is wired, what is registered, what is alive right now, and what looks
wrong about that"*. It does **not** draw a timeline, a flamegraph, a span tree, or a
duration histogram. "Why is it slow" remains `sagittarius-trace` → `.sagtrace` → Perfetto.

This is the boundary that keeps `EPIC-005` §5 intact. Any proposal to add a time axis to
this tool is a proposal to reverse `EPIC-005` §5 and must be argued there, as its own ADR
superseding it — not slipped in as a feature.

**The one deliberate overlap:** the console may show *aggregates* the recorder already has
(records captured, records dropped, ring-buffer fill). Those are state — "is my
instrumentation keeping up" — not a time axis.

### 2.2 The transport is the existing one. The message is `SNAPSHOT`.

No new server, no new port, no new auth scheme. `TraceServer` already provides the
WebSocket, `?token=` authentication rejected with close code `4401` before any data is
sent, refusal to bind off-loopback without a token, and ephemeral-port binding with a
readiness event.

`PROTOCOL_VERSION` goes **1 → 2** when the snapshot payload is added. `check_protocol()`
is an equality check today precisely so that widening happens in one function for both
sides of the wire; that is where it widens.

### 2.3 The snapshot schema lives in `contracts.py`, and the client **imports** it

Not "documents the same fields". Imports. `contracts.py` exists because D3/D4 were one
defect twice, and it states its own purpose:

> There is now exactly one schema, here, and **the client imports it rather than
> redeclaring it**. A drift of that kind should become an `ImportError` or a type error,
> not a panel that quietly goes blank.

Snapshot dataclasses are `frozen=True, slots=True`, stdlib-only, `to_dict()`/`from_dict()`
producing primitives, no formatting at capture. Same rules as `TraceRecord`.

### 2.4 Collection is **pull or fixed-interval**. Never event-driven.

A snapshot is collected when a client asks for one, or on a fixed interval a client opted
into (default 1 Hz). It is **never** triggered by an emit, a dispatch, a task transition,
or any other application activity.

This is the direct repair for D9, and it is not negotiable: the previous dashboard's
`AuditService` re-collected the whole world on every event, with no coalescing, no rate
limit and no delta, which made a task-heavy workload pay for its own observation.

### 2.5 Zero cost when nothing is attached

The collector runs only while at least one client is connected. Detached, the cost is a
boolean check on a connection count — not a periodic walk of the container, not a timer.

**Budget, to be enforced as an acceptance criterion like `EPIC-005` §4.2's was:** one full
snapshot ≤ **5 ms** on `examples/student_management`, at ≤ 1 Hz, and **nothing measurable**
when detached. This repository measures such claims rather than asserting them (21.5 /
24.5 / 48.8 ns for the no-op-object question; 157 ns per enabled trace record; 98 ns per
emit with the runtime monitor on). A budget stated without a benchmark is not a budget.

### 2.6 Every field is read through a **public** interface

`EPIC-006`'s acceptance criterion 2 — *"No diagnostic code touches `_handlers`,
`_bindings`, `_config` or any other private"* — applies unchanged. Where a public read API
does not exist, the interface is **extended as its own subtask**; the collector never
reaches in.

Two gaps exist today, and each is worth having on its own merits regardless of whether the
console ships:

| Gap | Today | Needed |
| :--- | :--- | :--- |
| **`ITaskManager`** | `get_active_tasks()` returns only `RUNNING`/`PENDING`. `TaskManager.tasks` is a public attribute but a *live, mutable, lock-protected* dict — publishing it hands out a structure that can be mutated mid-read from a pool thread. | `snapshot() -> tuple[TaskSnapshot, ...]` — every retained task including `COMPLETED`/`FAILED`/`CANCELLED`, frozen, taken under the existing `_lock`. This is what makes "task registered / running / not running" answerable at all. |
| **`IThreadManager`** | `submit()` and `shutdown()`. Nothing else. Pool size, queue depth and in-flight count live in `ThreadPoolExecutor` privates. | `stats() -> ThreadPoolStats` — `max_workers`, submitted, completed, in-flight. Queue depth is the backpressure signal, and it is currently unobservable. |

`Scheduler.jobs`, `HostedServiceManager.services` / `.started_services`,
`IContainer.registrations()`, `IEventBus.subscriptions()` and `IConfig.get_all()` are
already sufficient and public.

### 2.7 One requested signal does not exist and will not be faked

*"A hosted service that died after starting"* is the highest-value red flag in §1.1 and
**the engine cannot currently detect it**. `extensions/diagnostics/runtime.py` says so in
its own words:

> A service that fails to **start** raises, and boot aborts loudly … one that starts and
> later dies emits nothing and is caught nowhere, so detecting it needs new instrumentation
> in the runtime rather than observation of what already exists. That is a change to the
> runtime's contract, not a diagnostic.

The console will therefore show hosted services as **started / not started**, and will not
imply it knows whether a started one is still alive. Making it detectable is a separate
runtime change with its own task. Showing a green light the engine cannot actually verify
is worse than showing nothing — it is a rubber stamp, which `design-discipline.md` rules
out.

### 2.8 Config is **redacted by default**

`IConfig.get_all()` returns everything, including values loaded from `.env` and the process
environment. A console that opens a socket and ships that wholesale is a credential
disclosure path, not a feature.

Default behaviour: values whose key matches a secret-shaped pattern (`*secret*`, `*token*`,
`*password*`, `*key*`, `*dsn*`, and any URL carrying userinfo) are replaced with a fixed
mask. The **key and its source** (`json:config.json`, `env:APP_`) are still shown, because
"which layer won" is the question people actually open a config panel for. Unmasking
requires an explicit opt-in flag on the engine side, never a client-side request — a client
must not be able to ask a server to reveal more than it was configured to reveal.

### 2.9 "Dynamic memory" is answered as **bounded-structure occupancy**, not as a profiler

The wheel declares no dependencies, so `psutil` is not available. `tracemalloc` is stdlib
but costs a 2–4× slowdown while tracing — a diagnostic that perturbs what it measures by
that much is the problem it was meant to find.

What is reported continuously instead, because it is where a long-running engine actually
grows, and all of it is O(1) to read:

- ring-buffer fill and `dropped` count (the recorder already tracks both)
- retained task count against `max_retained_tasks`
- subscription count per event name — a monotonically rising count is a missing
  `unsubscribe`, and it is invisible today
- registered vs `instantiated` singletons
- `gc.get_count()` generational counts, as a coarse trend

`tracemalloc` remains available as an **explicit on-demand action** ("take a memory
snapshot now"), never as always-on collection.

### 2.10 Non-goal: the console never runs in the process it observes

`EPIC-005`'s two-process split holds — *"the recorder must not die with the app it
observes, must attach to an already-running process, and must add no UI dependency to the
engine."* An in-process panel would be reachable, tempting, and would forfeit all three.

---

## 3. Consequences

### Accepted

- **The console cannot answer "why is it slow."** By construction. Users will occasionally
  want one tool; they get two, and the console should link to `sagittarius-trace` where the
  question is a duration.
- **Protocol v2 breaks v1 clients.** `check_protocol()` is an equality check, so a v1
  `sagittarius-trace` refuses a v2 server loudly at connect. That is the designed
  behaviour and is better than the alternative it was written against (D1: a blank panel
  that looks like "nothing is happening"), but it does mean client and engine must be
  upgraded together.
- **Snapshot data is up to one interval stale.** At 1 Hz, a task that starts and finishes
  in 200 ms may never appear in any snapshot. This is inherent to sampling and is the
  correct trade for §2.4; the trace recorder is what catches the transient, and the console
  should say so rather than pretend completeness.
- **Two new interface methods** (§2.6) are public API surface the engine must then keep.

### Gained

- The console reports findings in the **same vocabulary** the CLI and CI already use —
  `Finding(check, severity, subject, message, hint)` — so `sagittarius-doctor`, a build
  log and the console agree on what "A2" means. An operator does not learn two report
  formats because two tools happened to run at different times.
- `MessageType.SNAPSHOT` stops being a lie in the protocol.
- `ITaskManager.snapshot()` and `IThreadManager.stats()` are useful to consuming
  applications and their tests independently of this tool.

### Risks, named

- **Scope creep back into a timeline.** Mitigated only by §2.1 being written down here and
  by review. The pull is real: once tasks are on screen, "show me when they ran" is one
  request away.
- **The console becomes the second consumer that shapes an engine API around itself** —
  the coupling `7a3ac18` removed. Mitigated by §2.6: the two new methods return frozen
  snapshots of state the manager already owns, not view-shaped payloads.

---

## 4. Alternatives considered

| Alternative | Why not |
| :--- | :--- |
| **Extend `sagittarius-doctor`** to print state as well as findings | `sagittarius-doctor` boots the app, prints, and exits. It cannot attach to an already-running process — which is the entire request. Boot-time and attach-time are different tools with different lifetimes. |
| **A second server (HTTP + JSON) beside the trace WebSocket** | This is D1 in reverse: the last dashboard died because one end spoke HTTP and the other WebSocket on the same port. Two transports means two auth stories, two version handshakes and two places to drift. |
| **Push a snapshot on every state change (delta stream)** | D9. Also makes the engine's hot paths responsible for notifying an observer, which inverts the layering `bus_observers.py` was carefully built to avoid. |
| **Reuse `HealthExtension`** | Health answers *"is it working now"*; this answers *"how is it assembled, and what is running"*. `EPIC-006` §7.2 already settled that these are different lifecycles with different consumers, and gave diagnostics its own extension for it. |
| **Rebuild the timeline UI after all** | `EPIC-005` §5, approved, and unchallenged by anything in §1.1. Perfetto is better than what would be built here and is free to open. |

---

## 5. What this ADR does not decide

- **What renders the snapshot** — terminal, Qt, browser. See
  [`ADR-002`](ADR-002_state_console_client_ui_framework.md).
- Whether the console ships as an epic or a task, and in what order its milestones run.
  That belongs in the tracking document that follows this ADR, not here.
- Whether hosted-service liveness detection (§2.7) is worth the runtime change. That is its
  own decision, and this ADR only records that the gap is real and must not be papered over.
