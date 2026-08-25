# EPIC-006D — Check B: dispatch resolvability pre-flight

**Epic:** [EPIC-006 — Wiring & Readiness Diagnostics](../README.md)
**Status:** 🔵 Backlog
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
