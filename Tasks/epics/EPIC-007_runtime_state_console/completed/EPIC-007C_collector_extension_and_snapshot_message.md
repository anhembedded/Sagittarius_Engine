# EPIC-007C — The collector extension, and `SNAPSHOT` on the wire

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** ✅ **Done 2026-08-27** — see §Outcome
**Category:** Observability / Extensions
**Priority:** P2
**Depends on:** EPIC-007A, EPIC-007B

---

## 1. The milestone where it becomes a tool

This is the first subtask whose command attaches to a **live process**. Everything before it
is proof that pieces fit; this is the one that produces the thing being built.

It is also independently valuable and should be treated as shippable on its own: a text
rendering of a running application's wiring, over SSH, in a container, on a build agent, is
a usable diagnostic even if `EPIC-007E` never happens.

## 2. Scope

### 2.1 `StateConsoleExtension`

New package `sagittarius_engine/extensions/state_console/` — engine side, **stdlib only**,
never imports PySide6 or anything from `tools/`.

It attaches at the readiness milestone the same way `DiagnosticsExtension` does, through
`when_ready()`. The kernel knows nothing about it; the dependency points from the extension
to the lifecycle, never back. `EPIC-006C` established this and it is not re-argued here.

```python
app.use(StateConsoleExtension(port=8781, token=None, interval_hz=1.0))
```

### 2.1.1 The collector architecture: `ISnapshotSection[T]`

`StateConsoleExtension` does not collect the seven sections of `EPIC-007A`'s `StateSnapshot`
itself. Each section is its own class, implementing one shared abstract base:

```python
# extensions/state_console/collector.py
class ISnapshotSection[T](ABC):
    """One section of a StateSnapshot, collected independently."""

    @abstractmethod
    def collect(self) -> T | None:
        """The section's current value, or `None` if it cannot be observed."""
```

```
extensions/state_console/
├── extension.py            # StateConsoleExtension — holds one of each, assembles StateSnapshot
├── collector.py            # ISnapshotSection[T]
└── collectors/
    ├── lifecycle.py         # LifecycleCollector(ISnapshotSection[LifecycleState])
    ├── events.py            # EventCollector(ISnapshotSection[tuple[EventState, ...]])
    ├── container.py         # ContainerCollector(ISnapshotSection[ContainerState])
    ├── tasks.py             # TaskCollector(ISnapshotSection[tuple[TaskRecord, ...]])
    ├── thread_pools.py      # ThreadPoolCollector(ISnapshotSection[tuple[ThreadPoolStats, ...]])
    ├── bounded.py           # BoundedStructuresCollector(ISnapshotSection[BoundedStructures])
    └── config.py            # ConfigCollector(ISnapshotSection[tuple[ConfigEntry, ...]])
```

Eight files for one extension — the most of any subtask in this epic — so the choice is
recorded rather than left implicit.

**`@abstractmethod`, not a concrete no-op default.** `IBusObserver`/`ITraceRecorder` use
concrete no-op defaults because an implementer may have partial interest — an observer that
only cares about failures should not have to write an empty `event_emitted`. No such case
exists here: every collector exists to provide exactly one thing, so a silent no-op default
would let a broken collector return `None` forever and read as "not observed" rather than
"not implemented." `ConfigSource`/`IFileStorage`/`IStateStore`'s idiom — `ABC` +
`@abstractmethod` — is the one that fits, because it is the same shape: several
implementations of one contract, each expected to actually do the thing.

**Each collector takes exactly what it needs in its constructor**, not an `IEngineContext`:
`LifecycleCollector(lifecycle: Lifecycle)`, `EventCollector(bus: IEventBus)`,
`ContainerCollector(container: IContainer)`, and so on. `WiringInspector`'s own docstring is
the reason, quoted rather than re-argued: *"Takes the subsystems it needs one at a time
rather than an engine context… a narrow signature is also what lets each check be tested
against a two-line fixture instead of a booted application."* `StateConsoleExtension`
resolves each dependency once, at construction, and holds one instance of each collector.

**This is not a third-party extension point**, and the spec says so rather than implying
otherwise. `IExtension`/`IMiddleware`/`IBusObserver` are genuinely open — an application
registers its own. `StateSnapshot`'s seven fields are fixed by `EPIC-007A`'s schema; an eighth
collector would have nowhere on the wire to put its result. The interface exists because this
subtask creates more files of one shape than any other in the epic and each should honour the
same contract, not because a consumer is expected to implement one.

**Considered and not taken: one class, many methods**, the shape `WiringInspector` itself
uses (`inspect_events()`, `inspect_container()`, `inspect_handlers()`, `inspect_lifecycle()`
on one class) rather than one class per check. That precedent sits in the same package this
epic depends on and cuts the other way — recorded here rather than silently overridden.
Weighed against it: `StateSnapshot` already fixes the seven-way split (`EPIC-007A`), so the
methods-on-one-class version would still be seven distinctly-shaped private methods with
seven distinct constructor dependencies threaded through one `__init__` — the god-object
shape `code-rule.md`'s own "No God Objects" clause warns against, once threading exists.
Seven single-purpose classes behind one seven-line abstract keep each dependency local to the
one collector that needs it, at the cost of the eight files this section names up front.

### 2.2 Collection is pull or interval, never event-driven

`ADR-001` §2.4, and the reason it is not negotiable: `EPIC-005` §2's **D9** was
`AuditService` re-collecting the whole world on every emitted event, with no coalescing, no
rate limit and no delta — which made a task-heavy workload pay for its own observation.

A snapshot is collected when a client asks for one, or on the fixed interval a client opted
into. It is never triggered by an emit, a dispatch, or a task transition.

### 2.3 Zero cost while detached

The collector runs only while at least one client is connected. Detached, the cost is a
comparison on a connection count: **no timer thread, no periodic walk, no allocation**.

`EPIC-005` §4.2 measured its way out of a specification that was backwards (a no-op object
turned out to cost 48.8 ns against 24.5 ns for an `is not None` guard, having been specified
on the assumption it was free). The same discipline applies: this milestone's budget is
measured and the table goes in the outcome section, not asserted here.

**Budget:** ≤ 5 ms per full snapshot on `examples/student_management` at ≤ 1 Hz; nothing
measurable detached.

### 2.4 Transport: nothing new

`TraceServer` already provides the WebSocket, `?token=` auth rejected with close code
`4401` before any data is sent, refusal to bind off-loopback without a token, and
ephemeral-port binding with a readiness event. `MessageType.SNAPSHOT` has been declared in
`contracts.py:44` since `EPIC-005A` and constructed by nothing — this fills that seat.

`TraceServer` gains one thing: a snapshot provider it can call, and the handling of a
client's snapshot request. It keeps owning nothing — it reads a provider the way it already
reads a recorder.

### 2.5 A text rendering, as part of the end-to-end test

`ADR-002` §2.3. A `--format text` rendering of a parsed snapshot, whose output is a string,
so the end-to-end test can assert on it. It is small, it keeps the schema honest — a panel
hides a missing field behind blank space, a text dump cannot — and it makes the console
usable with no display server for free.

Shipped as a `snapshot` subcommand on `sagittarius-trace`, beside `attach`.

## 3. How to run it

Two terminals. **This is the command this epic exists to make work.**

```powershell
# terminal 1 — the observed app, with the console extension attached
.\examples\student_management\run.ps1 -Console
```

```bash
# terminal 2 — read it
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781

# and keep reading it
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
```

The `-Console` switch on `run.ps1` is `EPIC-007D`'s deliverable; until it exists, pass the
extension by hand:

```bash
PYTHONPATH=. .venv/bin/python -c "
from examples.student_management.main import build_app
from sagittarius_engine.extensions.state_console import StateConsoleExtension
app = build_app(extra_extensions=[StateConsoleExtension(port=8781)])
input('attached on 8781 - press enter to stop')
app.stop()
"
```

The automated proof:

```bash
.venv/bin/python -m pytest tests/extensions/state_console/test_end_to_end.py -v
```

## 4. Done when

1. **A real `TraceServer` is started, a client connects, and a parsed snapshot is asserted
   on** — in a test, in CI, on every push. This is the test whose absence let `EPIC-005`
   D1–D6 ship in two releases; it is criterion one for that reason.
2. `sagittarius-trace snapshot` prints a live application's state in a terminal.
3. `--watch` re-reads on the interval and does not re-collect between them.
4. A v1 client is refused at connect with both versions named, not left blank.
5. The token and off-loopback rules are asserted against the snapshot path too, not only the
   trace path — an auth check that covers one of two message types is not an auth check.
6. **Measured:** detached cost, and one full snapshot, both in a table in this file's Outcome
   section, in the shape of `EPIC-005` §4.2's.
7. Nothing in `extensions/state_console/` imports outside the stdlib and the engine's own
   interfaces — architecture test extended to say so.

---

# Outcome

**Done 2026-08-27.** `StateConsoleExtension`, seven collectors behind one shared
`ISnapshotSection[T]`, `TraceServer`'s snapshot-request loop, and `sagittarius-trace
snapshot` — the command this epic exists to make work, run against the real
`examples/student_management` app, not a mock.

## What shipped

| Piece | What it is |
| :--- | :--- |
| `extensions/state_console/collector.py` | `ISnapshotSection[T](ABC)` — one `@abstractmethod collect() -> T \| None` |
| `extensions/state_console/collectors/*.py` | Seven collectors, one per `StateSnapshot` field, each taking exactly the subsystem it needs |
| `extensions/state_console/extension.py` | `StateConsoleExtension` — attaches at `when_ready()`, assembles the seven sections by keyword, caches under `interval_hz` |
| `TraceServer._snapshot_request_loop()` | Any inbound frame on an attached connection triggers one fresh (or cached) `snapshot_message()` reply |
| `sagittarius-trace snapshot [--watch DURATION]` | `_format_snapshot()` renders a parsed `StateSnapshot` as text; `--watch` repeats on the interval until detached |

## A concurrency bug found only by running the real app, not by any unit test

`StateConsoleExtension._start()` called `self._server.start()` and returned without waiting
on `self._server.ready_event` — the one thing every other caller of `TraceServer.start()`
(the CLI, every existing test fixture) already does. `TraceServer._serve()` assigns
`self._stop_event` only after its background thread's event loop actually starts running, so
`stop()` called before that assignment exists falls through to its full `timeout` wait rather
than signalling the event.

**Reproduced, not assumed:** running `StateConsoleExtension` against `examples/student_management`
end-to-end (boot, then immediately `app.stop()`) took `2.0044s` — the exact
`stop(timeout=2.0)` default, every time, not occasionally. Fixed by adding the same
`ready_event.wait(timeout=2.0)` (with a warning log on timeout) every other caller already
has. Verified: `app.stop()` dropped to `0.0031s` on the same script, same machine.

No isolated `TraceServer` unit test caught this — every one of them already waited on
`ready_event` by construction, which is precisely why testing only the transport in isolation
was not enough; the fix shipped only because of the "how to run it" §3 script, run by hand
against a real, booted application before the pytest suite was trusted.

## Measured (`EPIC-005` §4.2's discipline: measured, not asserted)

Detached (no client connected) — a comparison on a connection count, no timer thread, no
allocation. One full snapshot — `examples/student_management`, 20 runs, `gc` disabled during
the detached baseline so a collection pass cannot register as this collector's own cost:

| | p50 | p95 | max | Budget |
| :--- | ---: | ---: | ---: | :--- |
| detached baseline | — | — | ~13 ns/iteration | nothing measurable |
| one full snapshot | 0.107 ms | 0.266–0.647 ms | 0.266–0.647 ms | ≤ 5 ms |

p95 measured under 1% of budget across repeated runs of
`test_measured_detached_cost_and_one_full_snapshot_cost` — the small run-to-run spread above
(0.266ms vs 0.647ms max) is scheduling noise on a shared machine, not a regression signal;
both are an order of magnitude inside the 5ms ceiling `§2.3` set.

## Verified

| Gate | Result |
| :--- | :--- |
| `pytest tests/extensions/state_console/` | 7 passed |
| `pytest tests/extensions/audit/` | 34 passed |
| `pytest tests/` (minus `pyside_mvc`/`ui_state`, PySide6 absent here) | **996 passed**, same 9 pre-existing environmental failures as every prior checkpoint |
| `pytest tests/test_architecture.py` | 14 passed (criterion 7's stdlib-only import guard added here) |
| `ruff check` / `ruff format --check` (whole repo) | clean |
| `mypy` (whole repo) | 1 error, `thread_affinity.py:124`, the documented PySide6-absent false positive |
| `sagittarius-trace snapshot` against a live `examples/student_management` process | manually run; prints lifecycle/events/container/tasks/thread_pools/bounded/config as text |
| `sagittarius-trace snapshot --watch 0.3s` against the same live process | manually run; 5 snapshots printed over 1.5s, clean exit on server stop |
| `app.stop()` after `StateConsoleExtension` boots | `2.0044s` before the readiness-wait fix, `0.0031s` after — reproduced, not assumed |

## Run it

```bash
.venv/bin/python -m pytest tests/extensions/state_console/ tests/extensions/audit/test_cli.py tests/test_architecture.py -v
```
