# Runtime state console — `sagittarius-trace snapshot` and `sagittarius-console`

`EPIC-007`. Answers **"what is this application's state right now?"** — attach to a running
process and see what is wired, what is registered, what is alive, and what looks wrong about
that, without reconstructing it from a log afterwards.

---

> **Not the same tool as `sagittarius-trace`'s trace path.** That one
> ([`tracing.md`](tracing.md)) answers *"what happened, and how long did it take?"* — a
> timeline, built from records captured as they occurred. This one answers *"what does the
> application look like at this instant?"* — a snapshot, collected fresh on request. Both ride
> the same `TraceServer` transport (`extensions/audit/infra/trace_server.py`); which question
> you're actually asking decides which one to reach for.
>
> Not the same tool as `sagittarius-doctor` either
> ([`diagnostics.md`](diagnostics.md)): that one inspects wiring **before** anything runs, from
> a factory you hand it. This one inspects a **live, already-running** process from outside it,
> over a socket. `sagittarius-doctor --strict` in CI and this console attached to a staging
> deployment are complementary, not overlapping.

## 1. Attaching it to your own application

```python
from sagittarius_engine.extensions.state_console import StateConsoleExtension

console = StateConsoleExtension(port=8781)
app.use(console)
app.boot()
```

Attaches at the readiness milestone (`context.lifecycle.when_ready()`), the same way
`DiagnosticsExtension` does — a snapshot taken before every extension has finished starting
would describe a partially-wired app.

| Parameter | | Default |
| :--- | :--- | ---: |
| `port` / `host` | Forwarded to `TraceServer` unchanged — same `?token=` auth, same off-loopback refusal | `8781` / `127.0.0.1` |
| `token` | Require `?token=...` to connect, same as `sagittarius-trace` | `None` |
| `interval_hz` | Minimum spacing between two *actually collected* snapshots — a request sooner than `1 / interval_hz` gets the cached one back | `1.0` |
| `reveal_config` | Producer-side only. Unmasks config values in the `config` section. A client can never turn this on by asking | `False` |

**Detached cost is unmeasurable.** Nothing runs on a timer and nothing subscribes to anything —
a snapshot is built only when a connected client actually asks for one
(`StateConsoleExtension.collect()`, wired as `TraceServer`'s `snapshot_provider`). Measured
against `examples/student_management`: one full snapshot costs p50 ≈ 0.1 ms, p95 ≈ 0.4 ms
against a 5 ms budget.

## 2. Reading it — the text path

```bash
sagittarius-trace snapshot ws://127.0.0.1:8781
sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
```

```console
$ sagittarius-trace snapshot ws://127.0.0.1:8781
snapshot @ 1543.349494s
lifecycle: state=ready extensions=5/5 hosted=0/0 scheduler_jobs=0 (without_next_run=0)
events: 20
  StudentEnrolled handlers=0 emits=0 failures=0
  ...
container: 13 registration(s), open_scopes=0
  IEventBus -> MemoryEventBus [singleton] instantiated
  ...
thread pools:
  background: 0/20 in flight, queue_depth=0, submitted=0, completed=0
bounded: ring=0/0 (dropped=0), tasks=0/50, subscriptions=2, gc_counts=[259, 11, 0]
config: 3 entries
  ...
detached
```

Every section is its own line and an absent one is simply not there — a panel hiding a missing
field behind blank space is exactly the trap `EPIC-005`'s `D1` names (the old dashboard's CLI
polled HTTP against a socket that only ever spoke WebSocket and rendered an empty panel that
looked like "nothing is happening"). `--watch` re-requests on the interval; the CI/SSH path,
no display server needed.

## 3. Reading it — the QML dashboard

```bash
# one command: starts examples/student_management -Console -DemoFaults, waits for the port,
# opens the dashboard against it, stops the sample app when the window closes
scripts/run-console.ps1 -Demo

# or attach to an app you already started
scripts/run-console.ps1 -Attach ws://127.0.0.1:8781
```

`tools/state_console/` is a PySide6 + QML client, itself built as an `App` on this engine
(`tools/state_console/app.py`'s `build_console_app()`) — `ConsoleConnectionExtension` owns the
websocket client as a `TaskManager` task, and every screen is an ordinary
`BasePresenter`/`BaseQmlViewModel` pair subscribing to `SnapshotReceived`. Five screens, behind
a `PresenterManager`-driven sidebar (`tools/state_console/presentation/shell/console_shell_view.py`):

| Screen | Shows |
| :--- | :--- |
| Overview | connection state, lifecycle, thread-pool occupancy — folds in the "not attached" state |
| Events & wiring | the declared ⋈ subscribed join (`EventCollector`) |
| Container | registrations, lifetimes, what is built |
| Tasks & threads | the task table, thread-pool saturation, bounded-structures occupancy |
| Signals | dead-letter queue, watched state machines, UI-thread health — §5 below |

The console supplies its **own** palette (`tools/state_console/presentation/theme/palette.py`)
— it does not inherit the observed application's, since a diagnostic console that looks like
one of the apps it inspects is confusing when both are on screen.

**Three states, distinguished on purpose** (Overview screen): *not attached* (last snapshot,
frozen, labelled with its age), *attached, idle*, *attached, reading*. A client that renders
the first the same as the third is the defect `EPIC-005`'s `D1` traces back to.

## 4. The snapshot's sections

`extensions/audit/contracts.py`'s `StateSnapshot` — eight sections, every one optional and
defaulting to empty: an **absent** section means "not observed", a **present-and-empty** one
means "observed, none exist". Rendering those identically is how a panel comes to read as
healthy while measuring nothing.

| Section | Collector | |
| :--- | :--- | :--- |
| `lifecycle` | `LifecycleCollector` | engine state, extensions/hosted-services/scheduler counts |
| `events` | `EventCollector` | the A2 typo check's own join, on the wire |
| `container` | `ContainerCollector` | registrations, lifetimes, instantiated or not |
| `tasks` | `TaskCollector` | every retained background task |
| `thread_pools` | `ThreadPoolCollector` | occupancy of every pool `ITaskManager` manages |
| `bounded` | `BoundedStructuresCollector` | ring buffer, retained tasks, subscription count, GC counts |
| `config` | `ConfigCollector` | masked by default (`ADR-001` §2.8) |
| `signals` | `SignalsCollector` | dead letters and watched state machines — §5 |

`ExclusiveAction.held_slot()` and R1 (an emit nobody heard) are seeded by the demo app
(§6) and logged by `RuntimeMonitor` at shutdown but have **no collector yet** — named here
rather than silently absent from this table.

## 5. Signals — the dead-letter queue and state machines

Both are read-only opt-ins on the extension itself, called once at the point the application
constructs the thing being watched:

```python
console.watch_dlq(resilient_bus)                    # a ResilientEventBus
console.watch_state_machine("EnrolmentFlow", flow)   # a BaseStateMachine
console.watch_ui_thread_health(get_ui_thread_health) # a zero-arg callable
```

**Explicit, never discovered.** `EPIC-006D` found that a subclass registry for state machines
would have missed real handlers because the marker was duck-typed — naming a machine cannot be
wrong the way guessing at one can.

**`watch_dlq(bus)`** — `bus.get_dlq()` is read fresh at every collection, so an event a
`ResilientEventBus` parked after exhausting its retries appears with its handler, exception,
and a capped `repr()` of its payload. The dashboard's Reprocess control is visible and
disabled, stating why: reprocessing re-emits into the live application from this socket, and
every write path is `ADR-003`'s decision to make, not this feature's.

**`watch_state_machine(name, machine)`** — wraps the machine's own `transition_to()`/
`dispatch()` to catch `InvalidStateTransitionError` (it raises rather than returning `False` —
`REF-005`; the machine's own global callback never fires on a rejection, only a success). A
rejected transition renders inline with accepted ones, in the danger colour token, and
`rejected_count` is its own field rather than something the client derives by filtering. Call
this **before** driving the machine — a watcher installed after the fact misses whatever
already happened.

**`watch_ui_thread_health(source)`** — `source` is a zero-argument callable returning a
`UiThreadHealth` (freeze count, worst freeze duration, off-thread-mutation count), typically
closing over a `pyside_mvc.safety.UIWatchdog` and
`pyside_mvc.safety.get_off_thread_mutation_count()`. **Absent, not zeroed, when never called**
— a `0` means "watched, no violations"; showing it for an app that was never watched would be
the same lie `EPIC-005`'s `D1` already names for a different section.

## 6. Seeing it seeded, not just wired correctly

`sagittarius-trace snapshot` against a correctly-wired app shows every panel green and proves
nothing about whether the console actually *detects* anything wrong. `examples/student_management`'s
`DemoFaultsExtension` (opt-in via `--demo-faults`, never in the CI doctor gate's own factory)
plants one instance of every condition the engine's diagnostics claim to catch — full table and
the reasoning behind each seed:
[`examples/student_management/docs/runtime_state_console_demo.md`](../../examples/student_management/docs/runtime_state_console_demo.md).

## 7. Security

- **Secrets are masked by default** (`ConfigEntry.masked`) and cannot be unmasked by a client
  request — `reveal_config` is a producer-side constructor argument, not a wire field.
- **Binding off-loopback without a token raises at construction** — the same `TraceServerConfigError`
  `tracing.md` §3 describes for the trace path, since both share `TraceServer`.
- **Read-only.** `reprocess()`/cancelling a task/firing a job are all write paths into a live
  process from a socket; none is reachable from this console. Enabling any of them needs
  its own ADR.

## 8. Where the pieces are

| Path | |
| :--- | :--- |
| `extensions/audit/contracts.py` | `StateSnapshot` and every section's wire shape — one schema, imported by both sides |
| `extensions/state_console/extension.py` | `StateConsoleExtension` — `watch_dlq()`/`watch_state_machine()`/`watch_ui_thread_health()` |
| `extensions/state_console/collectors/` | One file per section |
| `extensions/state_console/state_machine_watcher.py` | `_StateMachineWatcher` |
| `extensions/audit/cli.py` | `sagittarius-trace snapshot` |
| `extensions/pyside_mvc/safety/ui_watchdog.py` | `UIWatchdog` — freeze detection and counters |
| `extensions/pyside_mvc/safety/thread_affinity.py` | `get_off_thread_mutation_count()` |
| `tools/state_console/` | The QML dashboard — `sagittarius-console` entry point |
| `scripts/run-console.ps1` | `-Attach` / `-Demo` / `-Snapshot` |

## 9. What used to be here

`tracing.md` §7 records that an earlier snapshot dashboard (`TASK-002`) was deleted by
`EPIC-005A` — an AuditExtension/AuditService pair whose PySide6 client and rich-based TUI
client had both been non-functional since before the feature was marked complete. This is that
question, answered again, properly: real end-to-end tests against a live `TraceServer` (not
tests that mock the transport), one schema both sides import, and every screen exercised
against a running application before being called done. Nothing above reuses any of the
deleted code.
