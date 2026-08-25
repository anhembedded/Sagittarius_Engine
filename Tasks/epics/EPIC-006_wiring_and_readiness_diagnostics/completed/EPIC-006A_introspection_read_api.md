# EPIC-006A: The read half — `IEventBus.subscriptions()` and `IContainer.registrations()`

- **Status**: ✅ Completed
- **Completion Date**: 2026-08-25
- **Epic**: `EPIC-006` — Wiring & Readiness Diagnostics
- **Category**: Interfaces / Introspection

---

## Why

Every check in `EPIC-006` §3 is a **comparison** between what is declared and what is actually
wired. A comparison needs enumeration, and neither side could be enumerated:

| Question | What existed | Why it could not answer |
| :--- | :--- | :--- |
| "which event names has anything subscribed to?" | `IEventBus.get_handlers(name)` | Answers about one name the caller already holds. A handler bound to `"student.updatd"` is unreachable by any question about `"student.updated"` — and *not knowing the bad name* is the entire premise. |
| "what is registered in the container?" | `IContainer.resolve(T)` | Answers "give me a T" for a named `T`. There was no enumeration at all. |

Without these, the flagship check — the silent typo — is not merely hard to write; it is
structurally impossible.

## The alternative that was rejected

Reading `bus._handlers` and `container._bindings` directly. `EPIC-005` §2 already records that
exact access in `AuditService` as a defect, and the codebase shows why it is not merely
stylistic:

- **`ThreadPoolEventBus` has no `_handlers` at all.** It is a decorator; `on()`/`off()` forward
  to `self._inner_bus` and only `emit()` differs. A diagnostic reading `bus._handlers` finds
  nothing and reports a fully-wired application as having zero subscriptions.
- **`ResilientEventBus` registers wrappers, not handlers.** `on()` installs a
  `resilient_wrapper` closure on the inner bus and records the pairing in `_wrapper_map`.
  Reading through to the inner bus yields a list of identically-named `resilient_wrapper`
  objects — true, and useless: a report naming the decorator instead of the subscriber has
  answered a different question.
- The engine already pays for this. `thread_pool_event_bus.py:61` carries a
  `hasattr(...) / getattr(..., "_handlers", {})` fallback dance for precisely this reason.

Only the implementation knows how to answer for itself. That is what an interface method is for.

## Design

### Concrete with an empty default, not abstract

`code-rule.md` §L forbids the usual escape (`raise NotImplementedError` on an inherited method),
and declaring the methods abstract would break every `IEventBus`/`IContainer` implemented outside
this repository at instantiation.

Both are therefore **concrete, returning empty** — which exactly mirrors the precedent already in
`i_event_bus.py`, where `get_handlers()` is concrete with `return ()`.

The cost is that "no subscriptions" and "cannot introspect" look identical from outside. That is
bought back for anything shipped here by two architecture guards
(`test_event_buses_implement_subscriptions`, `test_containers_implement_registrations`) which walk
the package and fail if a concrete implementation inherits the default. So an empty answer from an
engine class means genuinely empty; the ambiguity only ever applies to a foreign implementation,
which is the case the default exists to protect.

The guards were verified to have teeth rather than passing vacuously: they discover 4 `IEventBus`
implementations and 1 `IContainer`, and a deliberately non-overriding bus is detected.

### `Registration`

A frozen dataclass in `interfaces/i_container.py` — `abstract`, `concrete`, `lifetime`
(`"singleton" | "transient" | "scoped"`), `instantiated`. Exported from
`sagittarius_engine.interfaces` alongside the `Lifetime` alias.

Two decisions are load-bearing:

- **It never holds the instance.** A diagnostic that resolved things in order to describe them
  would construct half the application as a side effect of a question. `concrete` is `None` for a
  factory or lambda, whose result type is unknowable before it runs.
- **`instantiated` is separate from `lifetime`.** `singleton(abstract, SomeClass)` installs a lazy
  factory that *pops itself* on first resolve, with the built object landing in `_instances`. The
  registration is a singleton in both states; reading only `_factories` would make it vanish after
  first use.

`StdLibContainer.registrations()` builds entries in ascending order of the precedence `resolve()`
applies — bindings, factories, instances, scope registry — so a later write overwrites an earlier
one and the reported lifetime is the one that would actually be used.

## Changed

| File | Change |
| :--- | :--- |
| `interfaces/i_event_bus.py` | `subscriptions()`, concrete, default `{}` |
| `interfaces/i_container.py` | `Registration`, `Lifetime`, `registrations()`, concrete, default `{}` |
| `interfaces/__init__.py` | exports `Registration`, `Lifetime` |
| `infrastructure/container/std_container.py` | `registrations()` over all four stores, under the lock |
| `infrastructure/event_bus/memory_event_bus.py`<br>`asyncio_event_bus.py`<br>`ipc_queue_event_bus.py` | `subscriptions()` under each class's own lock; names emptied by `off()` are dropped |
| `infrastructure/event_bus/thread_pool_event_bus.py` | delegates to the inner bus |
| `infrastructure/event_bus/resilient_event_bus.py` | inverts `_wrapper_map` to report the handler the caller registered; an unmapped handler passes through rather than being hidden |

## Verification

- **`tests/infrastructure/event_bus/test_subscriptions_introspection.py`** — 8 tests, including
  the typo case, the emptied-by-`off()` case, snapshot semantics, `ThreadPoolEventBus` delegation
  (asserting it still has no `_handlers`, so the test keeps proving delegation), and
  `ResilientEventBus` reporting `_handler` where the inner bus holds `resilient_wrapper`.
- **`tests/infrastructure/container/test_registrations_introspection.py`** — 12 tests, including
  the lazy singleton before and after first resolve, a factory reported without being called,
  `resolve()`-precedence reporting, immutability, and a foreign container getting the empty default.
- **`tests/test_architecture.py`** — the two guards plus an explicit pin for `AsyncioEventBus`.

Full suite **1126 passed, 8 skipped** (was 1103) on Python 3.12. `ruff check`,
`ruff format --check`, `mypy` (321 files) all clean. Wheel guard PASS.

## Finding: `AsyncioEventBus` is not an `IEventBus`

It satisfies `IAsyncEventBus`, which is a **Protocol** — a separate hierarchy that
`issubclass`-based guards structurally cannot reach. It is still a bus applications run on, so it
implements `subscriptions()` and is pinned by its own explicit test rather than left to a guard
that cannot see it.

`EPIC-006B` must handle both bus families explicitly; assuming a single `IEventBus` hierarchy
would silently skip diagnostics for any application using the async bus.

## Version impact — no bump, per `release.md` §1

**No version bump and no tag**, per `release.md` §1 ("finishing a task is not a reason to cut a
version") and §0 (releases need an explicit instruction).

For whoever cuts the next release: this change is **purely additive published-API surface** on
`interfaces/`. Under `release.md` §2 it is not *automatically* a `b` bump, since `IEventBus` and
`IContainer` are outside the `__all__` set that `test_public_api_exports` pins (`App`,
`EngineContext`, `IExtension`, `ExtensionDescriptor`). It is still worth calling out as `b`-class:
the readme's own quick-start teaches consumers to import both interfaces directly, so they are
public in practice whatever the root `__all__` says. Nothing here is breaking — no existing
implementation must change, which is the whole reason the methods are concrete.

## Next

`EPIC-006B` — the `WiringReport` and checks A, C, D, built on these two methods.
