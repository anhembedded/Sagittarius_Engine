# Events — how they are defined, dispatched, and reported

Load this before touching anything under `domain/`, `infrastructure/event_bus/`, or a
presenter's subscriptions. It describes mechanisms that already exist and that you are expected
to **use rather than re-invent** — most of them were built specifically because four different
places had each hand-rolled the same thing slightly differently.

Written 2026-08-25 during the consuming app's `EPIC-008`. The reasoning behind each decision
lives in that epic's ADR, in the **app** repo under
Tasks/epics/EPIC-008_chuan_hoa_luong_event/ — a path in the other repo, not this one
(`ONBOARDING.md` §8). This file is the "what exists and how to use it" half.

---

## 1. Defining an event

Subclass `BaseEvent` (`domain/base_event.py`). One event per file.

This repo has **no** domain/events directory (deliberately unquoted: a backtick here would read as a claim that the path exists) — its own events live beside the component
that emits them (`kernel/events.py`, `runtime/tasks/events.py`,
`extensions/health/health_module.py`). A consuming application puts its events in its own
domain layer instead; do not assume that layout exists here (`ONBOARDING.md` §8).

```python
@dataclass
class SyncProgress(BaseEvent):
    symbol: str
    total: int
```

Subclassing gets you four things automatically:

| | |
| :--- | :--- |
| `event_id` | a UUID, per instance |
| `occurred_on` | UTC timestamp, per instance |
| `event_name` | defaults to the class's `__qualname__`; set it explicitly (`event_name = "health.updated"`) to pin a stable wire name across renames |
| registration | the class appears in `EventRegistry`, and therefore in `EVENT_CATALOG.md` |

**Two implementation details in `BaseEvent` are load-bearing — do not "simplify" either:**

1. Its metadata fields are `kw_only`. Without that, any subclass declaring a field with no
   default fails at class-creation time with `non-default argument follows default argument`.
2. `event_id`/`occurred_on` are **properties over private fields**, not public dataclass fields
   named after the `IDomainEvent` members. A public `event_id: str = field(default_factory=...)`
   looks equivalent and is not: `@dataclass` deletes the class attribute for a `default_factory`
   field and then calls `abc.update_abstractmethods()`, which re-marks the inherited abstract
   property as unimplemented — every instantiation then raises
   `TypeError: Can't instantiate abstract class`.

Both were found closing `BUG-005`, where inheriting `BaseEvent` silently gave a `@dataclass`
subclass nothing at all: the generated `__init__` never called `super().__init__()`, so all
three inherited members raised `AttributeError` on first access.

## 2. Events that are addressed by a bare string

The engine's own lifecycle events (`"app.booted"`, `"extension.started"`,
`"runtime.tasks.failed"`, …) predate `BaseEvent` and are emitted by name. They carry a payload
dataclass with an `event_name: ClassVar[str]`, and register themselves once at the bottom of
their defining module:

```python
EventRegistry.register_named(TaskFailed.event_name, TaskFailed, module=__name__)
```

**Emit by reading the name off the class** (`self._emit(TaskFailed.event_name, TaskFailed(...))`),
never by repeating the string literal at the call site — two copies of one constant with nothing
keeping them in step is how they drift.

## 3. The catalog is generated, never hand-written

`EVENT_CATALOG.md` at the repo root is produced by `scripts/generate_event_catalog.py` from
`EventRegistry`, and `tests/domain/test_event_catalog_matches_registry.py` fails CI if the
committed file no longer matches. **Add an event → run the script → commit the diff.** There is
no "remember to update the doc" step, deliberately: a hand-maintained list and a central
`Enum` of event names were both considered and rejected, because each creates a second source
of truth that drifts (see the ADR §4.6, and `rules/doc-code-sync.md` for the repo's history
with exactly that failure).

`EventRegistry` is also the intended data source for a planned engine-side event-audit tool
(which events exist, their callbacks, their durations). Keep `register()`'s signature able to
carry more later.

## 4. Dispatching: what a bus guarantees

Five implementations of `IEventBus` exist; `MemoryEventBus` is what applications actually use.
All of them share one reporting path, and you get these guarantees from it:

- **A handler that raises never disappears.** It is caught, reported at `ERROR` **with a full
  traceback**, and the remaining handlers still run. Isolation is deliberate — one broken
  subscriber must not stop unrelated ones being notified — and is only defensible because the
  failure is visible.
- **A bus built without a logger is still not silent.** `resolve_bus_logger` falls back to
  `FallbackLogger`, which forwards to the standard `logging` module and configures nothing, so
  `logging.lastResort` still puts `ERROR` on stderr. `NullLogger` is *wrong* here: it would
  discard the exceptions this whole mechanism exists to surface.
- **Dispatch is traced at `TRACE`, not `INFO`, and without the payload.** Some events fire per
  websocket tick; an `INFO` line each is the flood that froze the consuming app's UI thread
  (`BUG-042`). The payload is excluded because `ILogger` takes an already-formatted string —
  there is no lazy-formatting escape hatch, so including it would cost a `repr()` on every emit
  even when the level is off — and because payloads in logs leak domain data.

The modules, one abstraction each:

| Module | Responsibility |
| :--- | :--- |
| `infrastructure/event_bus/bus_logger.py` | which logger a bus reports through (`resolve_bus_logger`) |
| `infrastructure/event_bus/dispatch_trace.py` | the `TRACE` line on a normal dispatch |
| `infrastructure/event_bus/handler_reporting.py` | the `ERROR` report when a handler raises |
| `infrastructure/event_bus/diagnostic_labels.py` | naming an event/handler *for a log line* — not for routing |
| `infrastructure/logging/logger_resolution.py` | choosing a logger when none was injected |
| `infrastructure/logging/fallback_logger.py` | an `ILogger` that forwards to stdlib `logging` and configures nothing |

**If you are adding a sixth bus, or anything else that invokes handlers, call
`report_handler_failure` — do not write your own catch-and-log line.** That duplication, in
four places, is what this module set replaced.

## 5. Subscribing from a presenter (`pyside_mvc`)

An `IEventBus` calls handlers on whichever thread called `emit()`. For a websocket feed or a
thread-pool worker that is not the Qt main thread, and touching a widget from there crashes the
process.

**Use `BasePresenter.subscribe()`. Do not call `self.event_bus.on(...)` directly.**

```python
def _connect_engine_events(self) -> None:
    self.subscribe(BacktestCompleted, self._on_backtest_completed)   # already on the main thread
```

`subscribe()` routes through `QtEventBridge`, which gives you two things a direct subscription
does not:

1. The handler always runs on the Qt main thread. Qt's default `AutoConnection` is used on
   purpose: a cross-thread emit is queued, a same-thread emit stays a direct call, so a call
   site that reasonably expects `emit()` to have completed on return is not broken for a hop it
   did not need.
2. It is unsubscribed automatically on teardown. Opting out of this is *silent* — nothing
   fails, the handler simply keeps running after its screen is gone.

**`QtEventBridge` reports handler failures itself**, and must: a Qt signal/slot boundary does
not propagate exceptions back to the emitter (PySide6 catches and prints them), so the bus's own
exception handling cannot see a failure on the far side of the hop — and for a queued delivery the
emitting frame is long gone. Without that, routing a handler through the bridge would silently
undo §4's guarantee.

## 6. Presenter teardown: override `shutdown()`, never `dispose()`

`BasePresenter.dispose()` is framework-owned and idempotent. It drops every subscription this
presenter made, **then** calls `shutdown()`, which is the author hook. `PresenterManager`
prefers `dispose()` and falls back to `shutdown()` for a presenter that does not derive from
`BasePresenter`.

Overriding `dispose()` would skip the unsubscribe without any error — the same override-vs-call
trap `rules/architecture.md` documents for the extension lifecycle. Put your cleanup in
`shutdown()`.

`_connect_ui_signals()` and `_connect_engine_events()` are **no-ops by default**, not
`NotImplementedError` — a screen with nothing to wire is valid, and raising from an inherited
method breaks Liskov substitutability (`code-rule.md`).

## 7. Known open defects in this area

Read `Tasks/bug_report/README.md` for the authoritative list; these two are the ones that will
bite someone working here:

- **`BUG-007`** — `ResilientEventBus.on()` keys its `_wrapper_map` by `__name__` while the rest
  of the package keys by `event_name`/`__qualname__`. Two event classes sharing a bare
  `__name__` collide and the second `on()` silently registers nothing. If you are consolidating
  key resolution, that bug is where to do it — `diagnostic_labels.describe_event` is
  deliberately *not* that consolidation (it produces a label for humans, not a routing key).
- **`BUG-006`** — unrelated to events, but it will confuse you when you run the suite: two
  "no QML runtime warnings" tests assert on Qt's entire message stream, so a once-per-process
  platform warning (`QFontDatabase: Cannot find font directory`) lands on whichever of them
  collection order puts first. Adding an unrelated test file changes which one fails. It is
  **not** flaky-random; it is order-dependent and reproducible in both directions.

---

## 8. Checking the wiring, not just the catalog

The catalog above says what *can* be emitted. It says nothing about what is actually subscribed,
and a handler bound to a name no event uses fails silently forever — `bus.on("student.updatd",
handler)` never runs and nothing reports it.

`sagittarius-doctor` joins the two and reports the difference. See
[`diagnostics.md`](diagnostics.md).
