# EPIC-005A — Teardown, contracts, ring buffer, transport

**Epic:** [EPIC-005 — Audit Telemetry Teardown & Trace Recorder](../README.md)
**Status:** ⏸️ On hold with its epic — deferred behind `EPIC-006`
**Category:** Observability / Teardown
**Priority:** P2

---

## 🎯 Objective

Delete the existing audit feature entirely — both clients and the server — and rebuild the
recorder foundation: one shared contracts module, protocol v1, a bounded ring buffer, and the
WebSocket transport.

## Scope of deletion

`tools/audit_dashboard/`, `tools/audit_dashboard_cli.py`,
`sagittarius_engine/extensions/audit/`, and the three test files covering it.

**`[project.scripts] sagittarius-audit` is already gone** — removed by `TASK-039`, which found
the command had never run for any consumer. That part of this subtask is done ahead of it.

## The cost, stated plainly

**13 currently-passing tests are deleted**, and `WebsocketBroadcaster` — the one piece that
genuinely works, including `TASK-017`'s token auth and the ephemeral-port/`_ready_event` handling
that makes it testable — gets rewritten.

This subtask is not complete until those behaviours are back: **the auth test and the
bind-readiness test return as tests against the new transport.** Deleting them and moving on
would trade a working, tested component for an untested one and call it progress.

## Requirements

1. `git tag pre-epic-005-audit` **before** anything is removed.
2. `contracts.py` — frozen dataclasses, `to_dict()`/`from_dict()`, `PROTOCOL_VERSION`. Stdlib
   only. **One** module, imported by both sides; the two hand-maintained schemas that drifted
   apart are exactly what D3/D4 were.
3. Ring-buffer recorder — `deque(maxlen=N)`, O(1) append, no I/O or lock on the hot path.
   Retained mode by default so a consumer attaching late still sees what already happened.
4. Overhead budget met: < 2µs per record enabled, **exactly zero** when disabled.
5. Rebuilt transport with auth and readiness behaviour restored.
6. A raw `websockets` client receives a schema-valid `hello` + `trace` batch.

## Risk to watch

If the overhead budget cannot be met in CPython, that finding must surface **here**, not in
Milestone D. A tracer that perturbs what it measures is worse than none, and discovering it late
means discovering it after the instrumentation in `EPIC-005B` is already written against it.
