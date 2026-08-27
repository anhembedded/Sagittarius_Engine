# EPIC-007B — The public read APIs the collector needs

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** ✅ **Done 2026-08-27** — see §Outcome
**Category:** Core Architecture / Introspection
**Priority:** P2
**Depends on:** EPIC-007A (the schema names what has to be readable)

---

## 1. The rule this milestone exists to obey

`EPIC-006`'s acceptance criterion 2: *"No diagnostic code touches `_handlers`, `_bindings`,
`_config` or any other private."* `EPIC-006A` honoured it by **adding** `registrations()` and
`subscriptions()` rather than reaching in, and that is the precedent followed here.

Three of the eight sections in `EPIC-007A`'s schema cannot be filled today without either
touching a private or publishing a live mutable structure. Each gap below is worth closing
on its own merits — a consuming application's own tests want all three — which is why this
is a milestone and not a footnote inside the collector.

## 2. The gaps, and what closes them

### 2.1 `ITaskManager.snapshot()`

`get_active_tasks()` returns only `RUNNING` and `PENDING`. Everything the console needs to
say about *finished* work — completed, failed, cancelled, and the terminal error — is
unreachable through it.

`TaskManager.tasks` is a public attribute, but it is a **live dict mutated under `_lock`
from pool threads**. Handing it out is not introspection, it is a data race with a public
name.

```python
def snapshot(self) -> tuple[TaskSnapshot, ...]:
    """Every retained task, frozen, taken under the existing lock."""
```

Frozen records, taken in one pass under `_lock`, ordered newest-first. The lock is already
held for `get_active_tasks()`; this adds no new contention shape.

**Corrected while implementing:** the type is `TaskSnapshot`, not `TaskState` as an earlier
draft of this section named it — `runtime.tasks.TaskState` is the engine's own enum, and two
things sharing a name one import apart is what `EventRegistry`'s collision warning exists to
catch. `TaskSnapshot` carries the real `TaskState` enum as its `state` field.

### 2.2 Pool occupancy — split across two interfaces, not one

**Corrected while implementing.** This section originally proposed a single
`IThreadManager.stats()` for *all* pool occupancy — background, critical, everything. That
conflated two subsystems that turned out to be unrelated: the mockup's "background 2/20 ·
critical 0/10" panel is `TaskManager`'s own two internal `ThreadPoolExecutor`s
(`background_executor`, `critical_executor`), which `IThreadManager` — a separate,
general-purpose service most of this codebase does not even register (`grep` for
`resolve(IThreadManager)` finds one call site, in the extension's own `shutdown()`) — has no
visibility into at all.

So this is two additions, not one:

```python
# IThreadManager (interfaces/i_thread_manager.py) — one pool, this instance's own
def stats(self) -> PoolStats | None: ...

# ITaskManager (interfaces/i_task_manager.py) — the two pools TaskManager itself owns
def pool_stats(self) -> tuple[PoolStats, ...]: ...
```

Both share one `PoolStats` dataclass (`name`, `max_workers`, `in_flight`, `queue_depth`,
`submitted`, `completed`), defined once in `i_thread_manager.py` and imported by
`i_task_manager.py` — not redefined, for the same reason `Lane` is defined once and re-exported
rather than declared twice (`EPIC-005B`).

**Queue depth is the one that matters** and is the reason this is not cosmetic: a queue that
grows is backpressure, it is the earliest visible sign that the app is falling behind, and
today it is unobservable by any means. It is *derived*, not read from either executor's
private `_work_queue`: a submitted callable is either running on one of `max_workers` threads
or waiting — there is no third state — so `queue_depth = max(0, in_flight - max_workers)` is
exact. Counters (`submitted`/`completed`) are maintained by the manager via
`future.add_done_callback()`, which fires on every terminal state a future can reach —
completed, raised, or cancelled — unlike counting inside a wrapped function body, which a
future cancelled before it starts running never enters.

**A real deadlock, found and fixed while wiring the counters in.** `future.add_done_callback()`
invokes its callback *synchronously, on the calling thread*, when the future is already done
by the time the callback attaches — most sharply, when `Future.cancel()` succeeds, which fires
the callback from inside `cancel()` itself. Both `ThreadManager.shutdown()` and
`TaskManager.cancel_all()` call `.cancel()` on not-yet-started futures while holding a
non-reentrant `threading.Lock` the new done-callback also needed — the thread deadlocking on
its own lock. Reproduced (`tests/infrastructure/test_thread_manager.py` hung the whole test
process, not one assertion) and fixed by narrowing both locks to stop wrapping the call that
can trigger a synchronous callback. Regression tests assert both paths complete promptly
rather than trusting it stays fixed by inspection.

### 2.3 Exclusive slots and container scopes

- `ExclusiveAction` already answers `is_running(key)`. What is missing is *which key holds
  the slot, and for how long* — a slot held far longer than its task runs is a leaked
  single-flight key, and the control it guards never re-enables.

  **Corrected while implementing:** `held_slot()`, singular, not the `held_slots()` this
  section originally proposed. One `ExclusiveAction` instance holds exactly one slot — its
  own class docstring says so — so at most one key can ever be held at a time, and a plural
  name implying several simultaneous entries was never accurate to the class it describes.

- `ScopeContext` is a context manager with no census. A count of open scopes that only ever
  rises is a `with` block that never exits. `StdLibContainer.open_scope_count()`, incremented
  in `ScopeContext.__enter__()` and decremented in `__exit__()` — not in `create_scope()`
  itself, which only *constructs* the context manager and can run without the `with` block
  that actually activates it ever executing.

### 2.4 `IConfig` cannot say which layer won — found while implementing `EPIC-007A`

`ConfigEntry` carries a `source` field (`json:config.json`, `env:APP_`) because
*"which layer won"* is the question a config panel is actually opened for. It cannot be
filled today: `ConfigManager.get_all()` returns a flat merged mapping, and the sources that
produced it live in `self._sources`, a private.

`EPIC-007A` shipped the field anyway, defaulted to `""`, with the gap named on the dataclass
rather than papered over — a source guessed from a key's shape would be worse than an honest
blank. Closing it needs a public reader:

```python
def sources(self) -> Mapping[str, str]:
    """Which registered source supplied the winning value for each key."""
```

Until then the console shows the key and its value or mask, and no source column.

## 3. What is explicitly NOT added

A `stats()` on the event bus. Emit and failure counts per event name are already funnelled
through `dispatch_trace.log_event_emitted` and `handler_reporting.report_handler_failure`,
and `IBusObserver` already observes both — `EPIC-006F` built exactly that path and measured
it at 98 ns/emit. A second counter on the bus would be the same number maintained twice.

## 4. How to run it

```bash
.venv/bin/python -m pytest tests/runtime/tasks/test_task_manager.py -v -k "snapshot or pool_stats or cancel_all"
.venv/bin/python -m pytest tests/infrastructure/test_thread_manager.py -v -k stats
.venv/bin/python -m pytest tests/runtime/tasks/test_exclusive_action.py -v -k held_slot
.venv/bin/python -m pytest tests/infrastructure/container/test_scoped_lifecycle.py -v
.venv/bin/python -m pytest tests/infrastructure/config/test_config_manager.py -v -k sources

# the whole introspection surface, including EPIC-006A's
.venv/bin/python -m pytest -k "snapshot or pool_stats or held_slot or open_scope or sources or registrations or subscriptions" -v

# and the guard that says none of it reaches into a private
.venv/bin/python -m pytest tests/test_architecture.py -v
```

## 5. Done when

1. `snapshot()` returns frozen records for **every** retained state, not only the live ones.
2. A test spawns a task, lets it fail, and asserts the failure and its exception text survive
   into the snapshot.
3. A test asserts `snapshot()` is safe under concurrent `spawn()` — the returned tuple is a
   consistent point-in-time read, not a view that can change while being read.
4. `pool_stats()`/`stats()` report a non-zero queue depth under a deliberately saturated pool.
   Without this test the field can ship reading zero forever and nobody would notice.
5. `held_slot()` reports a slot's key and how long it has been held.
6. The open-scope count returns to its starting value after a `with` block exits, and does
   not when the block is abandoned — both asserted.
7. No new private access anywhere; `tests/test_architecture.py` still passes.

---

# Outcome

**Done 2026-08-27.** Six read APIs across five files, all concrete-with-honest-default
(never `@abstractmethod`) so no existing or hypothetical third-party implementer of
`ITaskManager`/`IThreadManager`/`IConfig`/`IContainer` breaks over any of them.

## What shipped

| Interface | Method | Returns |
| :--- | :--- | :--- |
| `ITaskManager` | `snapshot()` | `tuple[TaskSnapshot, ...]` — every retained task |
| `ITaskManager` | `pool_stats()` | `tuple[PoolStats, ...]` — the `background`/`critical` executors |
| `IThreadManager` | `stats()` | `PoolStats \| None` — this instance's own pool |
| `IConfig` | `sources()` | `dict[str, str]` — which registered source won each key |
| `IContainer` | `open_scope_count()` | `int` — how many `create_scope()` blocks are entered right now |
| `ExclusiveAction` | `held_slot()` | `HeldSlot \| None` — which key, and for how long |

## Three corrections made while implementing, each recorded inline above

1. **§2.1** — `TaskSnapshot`, not `TaskState` as first drafted. `runtime.tasks.TaskState` is
   the engine's own enum; reusing the name one import apart is exactly what
   `EventRegistry`'s collision warning exists to catch.
2. **§2.2** — split into `IThreadManager.stats()` (one pool, this instance's own) and
   `ITaskManager.pool_stats()` (the two pools `TaskManager` owns internally), not the single
   `IThreadManager.stats()` originally proposed. The mockup's "background 2/20 · critical
   0/10" panel is `TaskManager`'s own executors — `IThreadManager` is a separate,
   general-purpose service this codebase barely uses (one call site resolves it, in an
   extension's own `shutdown()`) and has no visibility into them at all. Conflating the two
   would have under-reported one or the other.
3. **§2.3** — `held_slot()`, singular. One `ExclusiveAction` instance holds exactly one slot
   — its own docstring says so — so `held_slots()` implying several simultaneous entries was
   never accurate to the class.

## A real deadlock, found and fixed, not just a naming slip

Wiring `future.add_done_callback()` into `ThreadManager.submit()` and
`TaskManager.spawn()`'s sync branch (to count completions honestly, per §2.2's "not read out
of the executor's internals" rule) turned two **pre-existing, latent** lock-scoping choices
into a **live self-deadlock**:

`Future.add_done_callback()` invokes its callback *synchronously, on the calling thread*
when the future is already done — and `Future.cancel()`, when it succeeds on a
not-yet-started future, invokes that future's callbacks from inside `cancel()` itself, on
whichever thread called `cancel()`. Both `ThreadManager.shutdown()` (`with self._lock:
self._executor.shutdown(cancel_futures=True)`) and `TaskManager.cancel_all()` (`with
self._lock: ... task.cancel()`) called `.cancel()`-triggering code while holding a
non-reentrant `threading.Lock` — the same lock the new done-callback also needed. A thread
deadlocking on its own lock.

**Reproduced, not assumed:** `pytest tests/infrastructure/` hung the entire process (not one
assertion — `pytest` itself never returned) the first time these tests ran with the counters
wired in. Fixed by narrowing both locks to stop wrapping the call that can trigger a
synchronous callback — `ThreadManager.shutdown()` no longer holds the lock around
`self._executor.shutdown(...)`; `TaskManager.cancel_all()` now snapshots which tasks to
cancel under the lock, then calls `.cancel()` on each after releasing it.

**Verified the regression tests actually catch it**, not just that they pass: reverted the
`cancel_all()` fix, confirmed
`test_cancel_all_does_not_deadlock_on_a_queued_not_yet_started_task` hangs (killed after
timeout, as `design-discipline.md`'s own standard requires — a fix whose stated cause is
untested is worse than no fix), then restored it and confirmed green.

## Verified

| Gate | Result |
| :--- | :--- |
| `pytest tests/` (minus `pyside_mvc`/`ui_state`, PySide6 absent here) | **961 passed**, same 9 pre-existing environmental failures as every prior checkpoint |
| `pytest tests/test_architecture.py` | **13 passed** |
| `ruff check` / `ruff format --check` | clean |
| `mypy` | 1 error, `thread_affinity.py:124`, the documented PySide6-absent false positive |
| Deadlock regression test, reverted then restored | confirmed it hangs without the fix, passes with it |

## Run it

```bash
.venv/bin/python -m pytest tests/runtime/tasks/test_task_manager.py tests/infrastructure/test_thread_manager.py tests/runtime/tasks/test_exclusive_action.py tests/infrastructure/container/test_scoped_lifecycle.py tests/infrastructure/config/test_config_manager.py -v
```
