# EPIC-006B: `WiringReport` and checks A, C, D

- **Status**: ✅ Completed
- **Completion Date**: 2026-08-25
- **Epic**: `EPIC-006` — Wiring & Readiness Diagnostics
- **Category**: Diagnostics / Runtime Correctness
- **Builds on**: `EPIC-006A` (`IEventBus.subscriptions()`, `IContainer.registrations()`)

---

## What landed

`sagittarius_engine/extensions/diagnostics/` — `WiringInspector` and `WiringReport`, exported
lazily from the `extensions` barrel (`TASK-034`'s `_LAZY_ATTRS`, which
`test_extensions_lazy_attrs_cover_all` enforces).

```python
from sagittarius_engine.extensions.diagnostics import WiringInspector

report = WiringInspector().inspect(bus=event_bus, container=container)
print(report.format())
if not report.ok:
    raise SystemExit(1)
```

| Check | Severity | Finds |
| :--- | :--- | :--- |
| **A2** | **error** | A handler subscribed to a name no event is registered under — with the intended spelling named |
| A2 | warning | Subscribed but undeclared, and unlike anything declared: cannot be typo-checked at all |
| A1 | info | Declared, nobody listening |
| A3 | info | More than one handler on a name |
| A5 | info | Subscribed by string — i.e. exposed to the A2 class of defect |
| **C1** | **error** | Constructor needs an unbound **abstract** dependency; resolving raises |
| **C2** | warning | Constructor needs an unbound **plain** dependency — §2.3's silent case |
| **C3** | **error** | Circular constructor dependency, named in full |
| **D1** | **error** | Extension registered but never initialised |
| D2 | warning | Hosted service registered but never started |
| D3 | warning | Scheduled job with no next run — it will never fire |

## Decisions worth keeping

### Nothing is resolved, constructed, emitted or started

Every check is a set difference or a static signature walk. `resolve()` would answer C1/C2 far
more simply and is not an option: it *builds the object*. A diagnostic that runs half the
application as a side effect of being asked a question cannot honestly be run at boot, which is
the only place this is worth running. Pinned by
`test_inspecting_the_container_never_constructs_anything`.

### A1 is `info`, deliberately

`EventRegistry` is process-wide and holds every event the engine can emit — most of which any
given application has no reason to handle. Emitting a dozen warnings on every boot trains the
reader to skip the report, which costs more than the check finds. It stays advisory, and an
application can silence known-unheard names through `expected_unheard`, declared by the
application and never by the framework.

Validated against `examples/student_management`: **0 errors, 0 warnings, 5 info.** A correctly
wired application produces nothing actionable, which is the property that makes a non-zero count
mean something.

### A2 distinguishes a typo from an undeclared event

A subscribed name within `difflib` ratio 0.8 of a declared one is an **error** with the intended
spelling named; anything unlike everything declared is a **warning** suggesting registration.
Without that split, every application that has not declared its events reads as a pile of
defects, and the check gets switched off. `order.cancelld` matches `order.cancelled`;
`legacy.tick` matches nothing.

### A5 — reporting exposure, not just faults

A class-based subscription cannot be misspelled: Python raises `NameError` on an undefined class
long before the bus is reached. So A2's whole value is concentrated on the **string** API, and
A5 lists exactly where an application is using it. That turns the report from "here are your
mistakes" into "here is where you can still make them", with a concrete fix — declare the event
as a `BaseEvent` subclass and the class of defect becomes impossible.

### `WiringInspector` takes subsystems, not a context

Each check receives the one thing it inspects. This repository has twice removed god-object
coupling from code shaped like this (`TASK-008`, `TASK-013`), and the narrow signature is also
what lets every check be tested against a two-line fixture rather than a booted application.

### `report.ok` ignores warnings

`ok` is false only when something is definitely broken. A warning is "probably wrong, but
legitimately intentional in some applications" — gating a boot on it would make the fail-fast
mode unusable for exactly the applications that most need the report.

## Checks specified in §3 that were not implemented, and why

- **A4 — "handlers whose bound callable is a dead reference".** Not applicable. Every bus stores
  handlers in a `tuple[Callable, ...]`, a strong reference, so a subscribed handler cannot be
  collected. The check as written can never fire. The *related* real hazard — a bound method
  keeping its owner alive for the life of the bus — is a lifetime question rather than a wiring
  one, and belongs to its own task if it is worth pursuing.
- **The wiring graph as report content.** `bus.subscriptions()` and `container.registrations()`
  already expose it directly. A report exists to carry problems; repeating the whole graph buries
  the two lines that need acting on.

## Verification

`tests/extensions/diagnostics/test_wiring_inspector.py` — **33 tests**, structured as
`EPIC-006B`'s acceptance criterion requires: a deliberately mis-wired fixture produces exactly
the expected findings, and a correctly wired one produces none.

Two pin behaviour rather than assert it:

- `test_c2_reports_the_unbound_plain_dependency_that_does_not_raise` asserts the finding **and
  then demonstrates the behaviour it describes** — `container.resolve(NeedsPlain).mailer` really
  is a `PlainMailer`, the empty stand-in.
- `test_inspecting_the_container_never_constructs_anything` counts constructions and asserts zero.

Full suite **1162 passed, 8 skipped** (was 1126) on Python 3.12. `ruff check`,
`ruff format --check`, `mypy` (326 files) all clean. Wheel guard PASS.

## Version impact — no bump, per `release.md` §1

**No version bump, no tag, no changelog entry.** Finishing a subtask is not a reason to cut a
version, and releases need an explicit instruction (§0).

For the next release: this is a **new feature** — a new extension package with new public
behaviour — so under `release.md` §2's scheme it is an **`a` bump**, not `b` or `c`. Nothing is
breaking and nothing existing changed behaviour; `extensions/__init__.py` gained two lazy
entries, and no engine code calls the inspector yet.

## Next

`EPIC-006C` — the readiness state machine and `app.ready`, which gives these checks the correct
place to run: after boot, after every extension has initialised, after every hosted service has
started. Until that milestone exists, `inspect()` has to be called by hand at a moment the caller
picks.
