# EPIC-007B — The public read APIs the collector needs

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** 🟠 Not started
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

### 2.2 `IThreadManager.stats()`

`IThreadManager` is `submit()` and `shutdown()`. Pool size, in-flight count and queue depth
live in `ThreadPoolExecutor`'s privates.

**Queue depth is the one that matters** and is the reason this is not cosmetic: a queue that
grows is backpressure, it is the earliest visible sign that the app is falling behind, and
today it is unobservable by any means.

```python
def stats(self) -> ThreadPoolStats:
    """max_workers, in flight, queue depth, submitted, completed."""
```

Counters are maintained by the manager (an increment on submit, a decrement in the future's
done-callback), **not** read out of the executor's internals. That keeps the numbers honest
across Python versions whose executor internals differ, and keeps this milestone inside its
own rule.

### 2.3 Exclusive slots and container scopes

- `ExclusiveAction` already answers `is_running(key)`. What is missing is *which keys exist
  and how long each has been held* — a slot held far longer than its task runs is a leaked
  single-flight key, and the control it guards never re-enables. Add
  `held_slots() -> tuple[HeldSlot, ...]`.
- `ScopeContext` is a context manager with no census. A count of open scopes that only ever
  rises is a `with` block that never exits. Add an open-scope counter to `StdLibContainer`,
  incremented in `create_scope()` and decremented in `__exit__`.

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
.venv/bin/python -m pytest tests/runtime/test_task_manager_snapshot.py -v
.venv/bin/python -m pytest tests/infrastructure/test_thread_manager_stats.py -v

# the whole introspection surface, including EPIC-006A's
.venv/bin/python -m pytest -k "snapshot or stats or registrations or subscriptions" -v

# and the guard that says none of it reaches into a private
.venv/bin/python -m pytest tests/test_architecture.py -v
```

## 5. Done when

1. `snapshot()` returns frozen records for **every** retained state, not only the live ones.
2. A test spawns a task, lets it fail, and asserts the failure and its exception text survive
   into the snapshot.
3. A test asserts `snapshot()` is safe under concurrent `spawn()` — the returned tuple is a
   consistent point-in-time read, not a view that can change while being read.
4. `stats()` reports a non-zero queue depth under a deliberately saturated pool. Without this
   test the field can ship reading zero forever and nobody would notice.
5. `held_slots()` reports a slot's key and how long it has been held.
6. The open-scope count returns to its starting value after a `with` block exits, and does
   not when the block is abandoned — both asserted.
7. No new private access anywhere; `tests/test_architecture.py` still passes.
