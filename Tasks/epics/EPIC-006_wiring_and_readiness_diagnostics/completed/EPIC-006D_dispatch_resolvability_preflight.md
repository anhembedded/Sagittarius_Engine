# EPIC-006D — Check B: dispatch resolvability pre-flight

**Epic:** [EPIC-006 — Wiring & Readiness Diagnostics](../README.md)
**Status:** ✅ Completed 2026-08-25
**Category:** Diagnostics / CQRS
**Priority:** P2
**Depends on:** EPIC-006B

---

## 🎯 Objective

Prove every dispatchable handler can actually be constructed, before a user triggers one.

## Why the check is shaped this way

`Dispatcher.dispatch(handler_class, input_dto)` takes the handler **class** and resolves it
straight from the container:

```python
handler = self.context.container.resolve(handler_class)
```

There is no registration step, so "zero handlers" and "ambiguous handlers" are not failure modes
this engine can have — a simpler design than CQRS frameworks that maintain a map, and one that
needs no audit.

But it relocates the risk rather than removing it. **A handler whose constructor dependency is
unbound fails only when someone triggers that command** — in production, on a real request. That
is precisely the late, silent failure this epic exists to pull forward.

`EPIC-006B` already checks everything *registered* in the container. This extends the same check
to handlers, which are typically **not** registered — they are resolved by class on demand, so
nothing in `registrations()` mentions them.

## Requirements

1. Discover every `IDispatchable` subclass.
2. For each, apply `EPIC-006B`'s C1/C2 logic to its constructor: an unbound abstract dependency
   is an error, an unbound plain one is §2.3's silent warning.
3. Report the resolved dependency chain per handler — "what does this actually depend on" is a
   question people ask of a DI container and cannot currently answer.
4. **Statically. Nothing is resolved.** Same constraint as `EPIC-006B`, same reason: constructing
   a handler to check it would run application code during a diagnostic.

## Open question: how are handlers discovered?

- **`__init_subclass__` registry** — the pattern `BaseEvent`/`EventRegistry` already uses here,
  and it works. Cost: `IDispatchable` gains a registration side effect.
- **Package walking** — no engine change, but it must import the consuming application's whole
  tree to find anything, which is a large and surprising side effect for a diagnostic.

*Recommendation: `__init_subclass__`*, for consistency with a mechanism this repository already
runs successfully, and because it costs no imports.


---

## ✅ Outcome — 2026-08-25

### The recommended discovery mechanism did not work

This file recommended `__init_subclass__` on `IDispatchable`, "for consistency with a mechanism
this repository already runs successfully". **Measured, it would have found nothing.**

`IDispatchable` is a duck-typed marker — not an ABC, not a `typing.Protocol` — and its own
docstring says so: *"Any handler class that implements `execute(dto) -> TResult` is considered
dispatchable."* The engine's reference application takes it at its word. Every handler in
`examples/student_management` is a bare `class XHandler:` inheriting nothing:

```
EnrollStudentHandler, GenerateRosterReportHandler, GetStudentHandler,
ListStudentsHandler, RemoveStudentHandler, SearchStudentsHandler, UpdateStudentHandler
```

A subclass registry would have reported **zero of seven**. This is the third time in this epic
that building first and measuring second would have shipped something that looked right and did
nothing.

### What was built instead

Discovery is **structural, matching how dispatch itself works** — a callable `execute` taking
`self` and one DTO. Measured against the booted demo app: 7 handlers found, 0 false positives.
Scanning the engine as well surfaces `HealthCheckQuery` plus `ICommand`, `IQuery` and
`IDispatchable`; the three interfaces are excluded by identity, since a finding against
`ICommand` names the interface where the reader needs the implementation.

`discover_handlers(*prefixes)` walks **`sys.modules`, importing nothing**. Anything the
application uses is already imported by the time this runs, and importing more to look for
handlers would execute application code as a side effect of a diagnostic — the constraint every
check in this package is built on. The honest cost: a handler in a module the app never imported
is invisible, and is also one nothing can dispatch. A prefix is required; searching everything
would sweep in third-party classes that happen to have `execute`.

An application can also name its handlers explicitly. A non-handler in that list is dropped
rather than reported — a typo in the list is not a wiring defect in the application.

### Checks

| Check | Severity | Finds |
| :--- | :--- | :--- |
| **B1** | **error** | Handler needs an unbound **abstract** dependency — `resolve()` raises on first dispatch |
| **B2** | warning | Handler needs an unbound **plain** dependency — §2.3's silent substitution |
| B3 | info | What the handler depends on — a question the DI container could not previously answer for a handler, since handlers appear in no registry |

B1/B2 share `_unbindable_dependencies()` with C1/C2. The two callers differ in *what* they
inspect, not in what "unsatisfiable" means, so the check ids are parameters rather than the logic
being written twice and drifting.

**Renumbered from this file's original text**, which said "apply C1/C2 logic". The split is
mirrored — B1 abstract, B2 plain — so a report line says which surface it came from, and B3 takes
the dependency chain the spec listed as requirement 3.

### Verification

Against the real demo app: 7 handlers discovered, no B1/B2 findings (correctly wired), B3
reporting `EnrollStudentHandler → repo: IStudentRepository, event_bus: IEventBus`. Injecting a
handler with an unbound abstract dependency produces the B1 error and flips `report.ok` to False.

`tests/extensions/diagnostics/test_handler_preflight.py` — 15 tests, plus 3 in the extension
suite. Two are premises asserted rather than assumed:
`test_handlers_are_invisible_to_the_container_check` (the reason this subtask exists) and
`test_a_bare_class_with_execute_is_dispatchable`, which also flags that discovery could be
simplified if handlers ever must inherit `IDispatchable`.

**1243 passed, 8 skipped** (was 1224) on Python 3.12. `ruff`, `ruff format`, `mypy` (341 files)
clean. Wheel guard PASS.

### Version impact

No bump, per `release.md` §1. `a` bump when a release is cut — additive feature, nothing breaking.
