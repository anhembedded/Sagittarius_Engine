# EPIC-005B — Instrumentation and the `ctx.trace` API

**Epic:** [EPIC-005 — Audit Telemetry Teardown & Trace Recorder](../README.md)
**Status:** ⏸️ On hold with its epic
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
