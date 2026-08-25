# EPIC-006C — Readiness state machine and `app.ready`

**Epic:** [EPIC-006 — Wiring & Readiness Diagnostics](../README.md)
**Status:** ✅ Completed 2026-08-25
**Category:** Kernel / Lifecycle
**Priority:** P1 — the highest-value item left in this epic
**Depends on:** EPIC-006B

---

## 🎯 Objective

Give the engine an explicit moment at which it is *up*, and a state anyone can query.

Today there is none. `grep -riE "ready|readiness|stable|settled"` over `kernel/` and
`extensions/health/` returns nothing. `app.boot()` returns, and whether that means "running"
is left to the caller to assume.

## Why this matters more than another check

Two things depend on it, and neither can be built without it.

**1. It answers the question this epic was actually asked.** "Hệ thống đã ổn định chưa" has no
answer while there is no definition of stable. `app.ready` is that definition: boot complete
**and** every enabled extension initialised **and** every registered hosted service started
**and** the scheduler running.

**2. It is the correct place to run `EPIC-006B`'s checks.** `WiringInspector.inspect()` currently
has to be called by hand at a moment the caller picks. Run too early and half the subscriptions
do not exist yet, so A2 reports phantom problems; run too late and the application has already
been serving requests while mis-wired. The readiness milestone is the one instant where the
answer is both complete and still ahead of any real work.

## The bug class it closes

A subscriber that registers *after* an event has already fired never hears it, and nothing says
so. The engine has already been bitten — `extensions/health/health_check_requested.py:9` carries
the note in the code:

> *"already missed it, and its subscription is dead code that never fires"*

A queryable state fixes the general case: a component that arrives late asks for the current
state instead of waiting for an event that has been and gone.

## Requirements

1. An `EngineState` progression — at minimum `created → booting → ready → stopping → stopped`.
   Transitions are one-way; re-entering a state is a bug, not a no-op.
2. `app.ready` emitted **exactly once**, after all four preconditions hold.
3. The state is **queryable**, not only broadcast. A late subscriber must be able to learn that
   readiness has passed rather than block forever on an event it missed.
4. Registering for `app.ready` after it has fired must resolve immediately, or the check in
   requirement 3 is decoration.
5. `EPIC-006B`'s inspection runs at the milestone, with the fail-fast mode of §7.1 available.
6. Failure during boot must leave the state honest — not `ready`, and distinguishable from
   "still booting".

## Open questions for whoever picks this up

- Does `app.ready` belong on the event bus, on `App`, or both? An event alone re-creates the
  missed-subscription problem it exists to solve.
- What happens when an extension is registered *after* readiness — a legitimate pattern for
  plugin hosts? Either readiness is a latch that never reopens, or it is a property that can go
  false again, and those are very different contracts.
- Does the scheduler having zero jobs count as "running"? Probably yes, but say so explicitly
  rather than leaving it to the implementation.


---

## ✅ Outcome — 2026-08-25

### What landed

`EngineState` gained **`CREATED`** and **`READY`**. Before this, a freshly constructed engine
reported `STOPPED`, so "never started" and "has been shut down" — the first thing anything
monitoring an engine needs to tell apart — were the same answer.

Transitions are now checked against an explicit table and an invalid one raises
`InvalidStateTransition`. A same-state transition stays a no-op, because shutdown reaches
`set_stopped()` from more than one path and must not be made fragile by that.

`set_ready()` emits `app.ready` **exactly once**, with emission inside the transition guard so a
defensive second call cannot produce a second event.

`when_ready(callback)` runs the callback **immediately if the engine is already ready**. This is
the whole reason readiness is a queryable state and not only a broadcast, and it closes the
defect the health extension records in its own source
(`health_check_requested.py:9`: *"already missed it, and its subscription is dead code that
never fires"*). Callbacks run before the event is emitted, so a subscriber that needs to be in
place *for* `app.ready` still is.

`DiagnosticsExtension` attaches `EPIC-006B`'s inspection to the milestone via `when_ready()`,
with opt-in `fail_fast`. The dependency points from the extension to the kernel, never back:
a kernel importing an extension to run a check would invert the engine's layering, which this
repository has removed twice already (`TASK-008`, `TASK-013`). It uses `when_ready()` rather
than subscribing to `app.ready` for a concrete reason — extensions boot in dependency order, so
this one can boot *after* readiness, and a subscription made then would wait forever.

### The requirement that was removed after measuring it

The original §Requirements asked that readiness be **withheld** when an extension was left
stranded. That was implemented, then deleted, because measurement showed it guarded a state this
engine cannot reach: during boot, `initialize_and_start()` raises for **both** ways an extension
can fail to initialise — `ExtensionDependencyError` for a dependency never registered,
`ExtensionCircularDependencyError` for a cycle. Both reproduced. Control never arrives at the
gate with anything stranded, so the check was dead code implying a boot outcome that does not
exist.

Stranding is real, but only **after** boot — `register()` defers and never raises, so a plugin
added to a running engine sits uninitialised while the state still reads `ready`. A one-shot gate
at boot could not have caught that either. Filed as **`BUG-008`**; `EPIC-006B`'s check D1 already
reports it at any point in the engine's life, which is what that case actually needs.

This is the second time in this epic that building the check first and measuring second would
have shipped something that looked right and did nothing.

### Open questions from the original spec, answered

- **Event, property, or both?** Both, and `when_ready()` besides. An event alone re-creates the
  missed-subscription problem it exists to solve — pinned by
  `test_subscribing_to_the_event_after_it_fired_still_misses_it`, which asserts the *limitation*
  rather than treating it as a defect.
- **Extension registered after readiness?** Readiness is a latch; it does not reopen. The
  post-boot stranding that motivated the question is `BUG-008`, not a state-model change.
- **Scheduler with zero jobs?** Ready. Nothing about an empty schedule is unfinished.

### Verification

- `tests/kernel/test_lifecycle.py` — rewritten: 14 tests covering the new states, guarded
  transitions, exactly-once emission, and `when_ready` before/after readiness.
- `tests/extensions/diagnostics/test_diagnostics_extension.py` — 10 tests, booting a **real
  engine** rather than a fixture, because the claim being made is about a moment in a lifecycle
  and a mock cannot demonstrate a moment. Includes `fail_fast` aborting a boot on a typo'd
  subscription, and warnings alone *not* tripping it.

Two existing tests were updated rather than worked around: `test_core.py` asserted
`is_stopped` on a fresh app (now `is_created`, which is the point of the change) and pinned
`EngineLifecycle`'s exact docstring text.

**1221 passed, 8 skipped** (was 1210) on Python 3.12. `ruff`, `ruff format`, `mypy` (339 files)
clean. Wheel guard PASS. `EVENT_CATALOG.md` regenerated — 18 events, `app.ready` among them.

### Version impact — no bump, per `release.md` §1

For the next release: **`a` bump** (a feature). One behaviour change worth calling out in the
changelog rather than burying — a freshly constructed engine now reports `CREATED`, so
`lifecycle.is_stopped` is `False` where it used to be `True`. Anything asserting on the state of
an un-booted engine sees the difference.
