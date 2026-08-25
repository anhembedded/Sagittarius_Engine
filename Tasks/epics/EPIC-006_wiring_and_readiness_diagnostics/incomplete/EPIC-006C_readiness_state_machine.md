# EPIC-006C — Readiness state machine and `app.ready`

**Epic:** [EPIC-006 — Wiring & Readiness Diagnostics](../README.md)
**Status:** 🔵 Backlog — **next up**
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
