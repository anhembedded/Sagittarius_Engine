# EPIC-005B — Instrumentation and the `ctx.trace` API

**Epic:** [EPIC-005 — Audit Telemetry Teardown & Trace Recorder](../README.md)
**Status:** ✅ **Done 2026-08-25** — see §Outcome. Requirement 1 is partial and said so.
**Category:** Observability / Runtime
**Priority:** P2
**Depends on:** EPIC-005A

---

## 🎯 Objective

Instrument the engine's own lifecycle with semantic spans, and give applications the same API.

**This is the half of `EPIC-005` that justifies the epic.** `py-spy` and `viztracer` already
attach to a running Python process and produce timelines without any framework support. What
they cannot produce is *meaning*: `py-spy` sees `_dispatch_inner()`, not "query `GetRoster`,
through three middleware, into its handler". Only the engine knows that.

## Scope

Spans and instants across task manager, dispatcher, event bus, scheduler, extensions, hosted
services, health and app boot — see `EPIC-005` §4.3 for the full table.

Two things fall out for free and are worth naming, because they are what people actually reach
for a tracer to answer:

- **Boot profiling** — per-extension `register`/`boot` spans answer "why does startup take four
  seconds?" as a bar chart.
- **Middleware cost** — a span per frame shows which one in the chain is expensive, per dispatch.
  Currently unanswerable by any means.

## The application-facing API

```python
ctx.trace.mark("order-filled", price=101.5)
with ctx.trace.span("strategy-eval", symbol="BTC"):
    ...
```

This is what properly retires D8. Instead of the framework hard-coding `student.added` and three
other demo-app events inside `AuditService`, the application instruments itself and the framework
knows about zero application events.

## Requirements

1. Every subsystem in §4.3 produces spans when tracing is enabled.
2. Task-run spans reconstruct to the same durations the task manager itself reports — if the
   trace and the task manager disagree, the trace is wrong and nothing built on it can be
   trusted.
3. The zero-overhead-when-disabled benchmark passes.
4. No framework module names an application-specific event.


---

# Outcome

## What was instrumented

| Subsystem | Lane | Records |
| :--- | :--- | :--- |
| Extensions | `extension` | `initialize` and `start` spans, per extension → **boot profiling** |
| Dispatcher | `dispatch` | total span + handler span, sharing one correlation id |
| Middleware | `middleware` | one span per frame → **middleware cost** |
| Task manager | `task` | task-run span, with the task id in `args` |
| Application | `user` | `ctx.trace.mark()` / `ctx.trace.span()` |

Live, against a demo app with a deliberately slow extension and an expensive middleware:

```text
LANE        CAT         NAME                           ms
extension   start       SlowExtension               20.17
extension   start       FastExtension                0.01
middleware              CheapMiddleware             15.33
middleware              ExpensiveMiddleware         15.33
dispatch    command     GreetCommand                15.35
dispatch    handler     GreetCommand                 5.16
user                    strategy-eval                3.17
user        (instant)   order-filled                    -
```

Both headline answers this subtask promised, in one capture: *which extension makes startup
slow*, and *which middleware in the chain is expensive*.

**Middleware durations are inclusive**, because frames nest — `CheapMiddleware` (outermost)
contains `ExpensiveMiddleware`, so its own cost is the difference, ~nothing. That is what a
flame graph needs, and it is §5's argument for borrowing Perfetto rather than building a viewer:
self-time is something the viewer computes, not something the recorder should pre-chew.

## Requirement 1 is partial, and says so

Instrumented: extensions, dispatcher, middleware, task manager, plus the application API.
**Not instrumented: event bus, scheduler, hosted services, health.** Four of eight subsystems in
§4.3 remain, and calling this subtask done without naming them would be the kind of quiet
narrowing this repository keeps finding in its own history.

The event bus is the interesting one: `EPIC-006F` already put an observer hook on the two
dispatch funnels every bus routes through, so a trace recorder can attach there rather than
being threaded into six bus implementations. That is a smaller job than it looks and is the
natural next slice.

## Requirement 2 named a number that does not exist

> *"Task-run spans reconstruct to the same durations the task manager itself reports."*

**The task manager reports no durations.** `BackgroundTask` carries `id`, `name`, `token`,
`future`, `status` and `progress` — no start time, no end time, nothing to compare against.
Verified by reading the class, not assumed.

The requirement's *intent* holds and is tested, against a stronger reference than the one it
asked for: an independent wall-clock measurement of the same call. A trace that disagreed with
a real clock is wrong, and nothing built on it could be trusted.

## Requirement 3, and a ~7% tax I nearly shipped

The first working version guarded in five scattered places inside `dispatch()`, once per
middleware inside the pipeline, and passed `recorder`/`cid` as **keyword** arguments. Measured
against `main`, on a two-middleware dispatch with tracing **off**:

| | µs/dispatch | |
| :--- | ---: | :--- |
| `main`, no instrumentation | 3.693 | baseline |
| first version, tracing off | 3.939 | **+250 ns, ~7%** |
| after hoisting the guard | 3.597 | within noise |

A 7% tax on every application for a feature they had not asked for is exactly what `EPIC-006F`
rejected for its observer hook, and it does not get an exception here. The fix is the same
lesson a third time: **hoist the branch as far out as it goes.** `dispatch()` now tests
`recorder is None` once and hands off to `_dispatch_traced()`; `MiddlewarePipeline.execute()`
tests once before the loop and the disabled branch is byte-for-byte what it did before this
subtask.

With tracing **on**, a dispatch through two middleware costs ~6.4 µs more for 4 spans (8
records) — ~800 ns per record, against §4.2's 2 µs budget.

## Requirement 4 is a test, not a promise

`test_no_framework_module_names_an_application_event` boots, dispatches and stops an application
that never calls `ctx.trace`, then asserts nothing landed in the `user` lane. That is `D8`
retired structurally: the framework used to hard-code `student.added` and three other demo-app
event names inside `AuditService`; now the application marks what matters to it and the engine
knows about zero application events.

## A layering problem solved rather than worked around

`tests/test_architecture.py` forbids `kernel/` from importing `extensions/`, and the kernel is
where most of this instrumentation lives. So `ITraceRecorder` **and `Lane`** moved to
`interfaces/i_trace_recorder.py`, and `extensions/audit/contracts.py` re-exports `Lane` rather
than redeclaring it — a second definition would be `D3`/`D4` a third time, in the very module
whose argument is that two hand-maintained schemas drift.

`recorder` and `trace` are declared on `IKernelContext`, not only on `EngineContext`. mypy
rejected every instrumentation site until they were, which was the type checker correctly
pointing out that the contract had gained a member the contract did not mention.

## Two mechanisms, deliberately

Engine sites read `context.recorder` and guard on `is not None`. Applications go through
`ctx.trace`, which is **always present** even when tracing is off — an API that made every
application write `if ctx.trace is not None:` around its own markers would push the engine's
constraint onto the place where it does not apply. A marker sits where the application chose to
put it; a dispatch span sits in a loop the engine runs a million times.

## Verification

17 tests. Notable ones: `_traced_frame()` is a module-level function because a closure built
inside the loop would make Python's late binding report the *last* middleware's name for every
frame — a trace that is confidently wrong rather than merely absent. Spans close in `finally`,
so a dispatch or an extension that raised is still measured: the slow-then-failing operation is
exactly what someone opens a tracer to find.

Two timing tests skip under `--cov` (whose trace hook makes them meaningless) and run in the
`benchmark` job, which gained a step for them — otherwise requirement 3 would be checked
nowhere.

Full suite **1338 passed, 11 skipped**, coverage 91.11%; `ruff`, `ruff format --check` and
`mypy` clean; architecture guard passes; `sagittarius-doctor` still exits 0 on the reference
application.
