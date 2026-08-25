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
4. Overhead budget met: < 2µs per record enabled, and as close to zero as CPython allows
   when disabled — **by guarding at the call site**, not by a no-op object. See the
   measurement below; the original wording of this requirement was unachievable and its
   preferred mechanism was the slower of the two.
5. Rebuilt transport with auth and readiness behaviour restored.
6. A raw `websockets` client receives a schema-valid `hello` + `trace` batch.

## Risk to watch

If the overhead budget cannot be met in CPython, that finding must surface **here**, not in
Milestone D. A tracer that perturbs what it measures is worse than none, and discovering it late
means discovering it after the instrumentation in `EPIC-005B` is already written against it.


---

## Measurement, taken first (2026-08-25)

This subtask's "Risk to watch" says an unmeetable overhead budget must surface **here**, before
`EPIC-005B` writes instrumentation against it. So it was measured before anything was deleted —
a prototype recorder, `timeit`, 500k–1M iterations, best of five, on CPython 3.12.

### The enabled budget passes, with 12× headroom

| | ns/record | budget |
| :--- | ---: | ---: |
| `perf_counter_ns()` | 53.8 | |
| `deque.append` of a constant 8-tuple | 32.7 | |
| empty call | 19.0 | |
| **full trace point** (guard + clock + tuple + append) | **157** | **2000** |

For scale, a `MemoryEventBus` emit is ~490 ns. An enabled trace point costs about a third of
one emit. **The ring-buffer design in §4.2 is sound and the epic can proceed on it.**

### The disabled budget was stated wrong, and so was its mechanism

"Exactly zero" is not achievable: a no-op object still costs an attribute lookup and a method
call. Against a floor of 21.5 ns — the empty call site itself, which is what "no
instrumentation at all" costs:

| Disabled call site | ns | above floor |
| :--- | ---: | ---: |
| no instrumentation at all | 21.5 | — |
| no-op object *(as this subtask specified)* | 48.8 | **+27.3** |
| guard on `None` | 24.5 | **+3.0** |

The spec preferred the no-op object explicitly — *"one attribute lookup, not a branch per
event"* — and that preference is **backwards**. A branch is a load and a compare; a call on a
null object is a full frame. The guard is nine times closer to free.

`EPIC-006F` measured the same thing independently for its bus observer hook (65 ns
unconditional call vs 27 ns reading the tuple first) and reached the same conclusion. Two
independent measurements in this codebase now say: **in CPython, guard at the call site.**

### What this changes downstream

`EPIC-005B` must write every instrumentation site as a guarded call, and `EPIC-005A`'s recorder
must therefore be `None` when disabled rather than a `NullRecorder` instance. Had this been
found in Milestone D, every instrumentation site would have needed rewriting — which is exactly
what the "Risk to watch" section was written to prevent.
