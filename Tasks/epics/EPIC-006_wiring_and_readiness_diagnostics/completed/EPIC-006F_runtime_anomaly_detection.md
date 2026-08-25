# EPIC-006F — Runtime anomaly detection

**Epic:** [EPIC-006 — Wiring & Readiness Diagnostics](../README.md)
**Status:** ✅ **Done 2026-08-25** — R1 and R2 shipped; R3 resolved into `EPIC-005`, see §Outcome
**Category:** Diagnostics / Runtime
**Priority:** P3
**Depends on:** EPIC-006C

---

## Why this is deferred rather than backlogged

"Abnormal" is only definable relative to a settled baseline, and the engine has no concept of
settled until `EPIC-006C` defines one. Specifying the checks first would mean guessing at the
baseline they measure against, and every one of them would need rewriting once readiness exists.

Everything in `EPIC-006A`–`EPIC-006E` inspects **structure**, which holds still while you look
at it. This subtask is the first to watch **behaviour**, which does not — so it also inherits an
overhead question the others never had to answer.

## Candidate checks

- An event emitted with **zero handlers** — warn once, naming the emit site. Different from A1,
  which is static: this one fires only when something actually tries to publish into the void.
- A handler that **raised**. The bus no longer swallows these (`bde88e9`), so they can be counted
  and surfaced rather than merely logged.
- A task running **past an expected duration**; a hosted service that **died after starting**.

## The constraint that will shape it

Unlike every other subtask here, this one runs continuously. `EPIC-005` §4.2's overhead budget
becomes relevant, and the same rule applies: a diagnostic that perturbs what it measures is worse
than none.

Note the overlap with `EPIC-005` and resolve it deliberately rather than building both — a task
that ran too long is a question the trace recorder is better shaped to answer, and duplicating it
here would be the second implementation of the same idea.


---

# Outcome

## What shipped

| | |
| :--- | :--- |
| **R1** — `warning` | An event was emitted at runtime and **nothing was listening** |
| **R2** — `error` | A handler **raised** |

`sagittarius_engine/extensions/diagnostics/runtime.py` (`RuntimeMonitor`), behind
`DiagnosticsExtension(watch_runtime=True)`. The report is a `WiringReport`, the same type the
static checks produce — an operator reading a build should not have to learn a second format
because one set of checks ran at a different time.

### R1 is not A1

`A1` is static and advisory: *this event is declared and nobody subscribes*. R1 fires only when
something actually **published into the void** — a real emit that reached nobody. A1 asks "is
anyone listening?"; R1 says "you just spoke and nobody heard you".

## Nothing new in the hot path

The spec's binding constraint was overhead. Two funnels already existed and were already called
on every dispatch, built for `EPIC-008C` so that no bus could get reporting wrong on its own:

- `dispatch_trace.log_event_emitted(logger, event_name, handler_count)`
- `handler_reporting.report_handler_failure(logger, event_name, handler, exc)`

Both questions this subtask asks are therefore *already answered* at exactly one place each, and
every bus plus `QtEventBridge` routes through them. Observing them beat instrumenting six buses
— six call sites, six chances to diverge.

## Measured, then made cheaper

Overhead is the reason this subtask could have been a mistake, so it was measured rather than
argued. `MemoryEventBus.emit()`, 200k–300k iterations, best of five:

**What every application pays, including those that never opt in:**

| | µs/emit | |
| :--- | ---: | :--- |
| no hook at all (baseline) | 0.4905 | |
| hook, unconditional call | 0.5324 | **+7.0%** |
| hook, guarded on the observer tuple | 0.4877 | within noise |

A 7% tax on every application for an opt-in feature was not defensible, so the emptiness guard
is **inlined at the call site** and the module is imported rather than the function: an
unconditional call costs 65 ns of pure call overhead, reading the tuple first costs 27 ns, and
importing the *name* would bind the empty tuple once and never see a registration.

**What an application pays when it does opt in:**

| | ns/emit added |
| :--- | ---: |
| first implementation (shared `_notify()` helper) | 209 |
| after inlining the `try`/`except` per observer | **98** |

The shared helper cost an extra call frame per observer per emit. Four duplicated lines removed
a third of the cost of the entire feature.

## Two of my own defects, found by running it

Both looked right on the page and were wrong in the output:

1. **The emit site pointed at the monitor.** `_calling_site()` walks the stack from the
   innermost frame outward, skipping engine dispatch frames — but `extensions/diagnostics` was
   not in the skip list, so the innermost surviving frame was the observer itself. Every R1
   finding reported `runtime.py:162`, which is both useless and quietly wrong.

2. **The engine's own events flooded R1.** A trivial boot-and-stop produced **six** R1 warnings,
   five of them engine lifecycle events (`app.ready`, `extension.started`,
   `runtime.scheduler.*`) that no application has any reason to handle. That is precisely the
   flood `A1` is advisory to avoid: a warning stream that is mostly noise teaches the reader to
   skip the report, which costs more than the check finds.

   Filtered exactly rather than by guessing at the name: every registration records its
   declaring module, so "the engine declared this" is
   `EventEntry.module.startswith("sagittarius_engine.")`. An application that declares its own
   `app.anything` is still reported. `include_engine_events=True` reveals them **without
   re-running**, because the filter is applied at report time, not capture time — which also
   keeps a registry lookup out of the hot path.

After both fixes, the same demo reports 1 warning instead of 6, naming the line that emitted.

## Corrections to this subtask's own spec

- **"The bus no longer swallows these (`bde88e9`)" was wrong.** The bus still isolates handler
  exceptions, deliberately — `report_handler_failure()`'s docstring states the reason: a bus
  fans one event out to unrelated subscribers, and one broken subscriber must not stop the
  others. What `EPIC-008C` changed is that the failure is now always *visible*. That made R2
  **easier**, not harder: there is exactly one funnel to observe, and R2's job is to surface
  what the log line alone does not — that it happened 40 times, not once.

- **R3 (a task running past an expected duration) is cut**, on this spec's own instruction to
  resolve the overlap with `EPIC-005` rather than build both. "How long did this take" is the
  question a trace recorder is shaped around; a second implementation here would be the worse
  one.

- **"A hosted service that died after starting" is deferred, for a measured reason.** There is
  no signal for it. A service that fails to *start* raises and boot aborts loudly
  (`hosted_service_manager.py:53`); one that starts and later dies emits nothing and is caught
  nowhere. Detecting it needs new instrumentation in the runtime — a change to the runtime's
  contract, not a diagnostic, and not something to bundle into one.

## Verification

21 tests. The two defects above each have a regression test verified to **fail** when the fix is
reverted. Also covered: a broken observer cannot break the application's delivery, the extension
unregisters at shutdown (the observer registry is process-global, so a leak would silently count
another application's events), and a raising handler still does not stop the other subscribers.

Full suite **1293 passed, 8 skipped**, coverage 90.88%; `ruff`, `ruff format --check` and `mypy`
clean over CI's scope. Architecture guard passes — infrastructure holds the registry, the
extension registers *into* it, so nothing in `infrastructure/` imports `extensions/`.
