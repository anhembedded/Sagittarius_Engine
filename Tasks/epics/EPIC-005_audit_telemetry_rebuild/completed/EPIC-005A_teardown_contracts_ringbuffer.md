# EPIC-005A — Teardown, contracts, ring buffer, transport

**Epic:** [EPIC-005 — Audit Telemetry Teardown & Trace Recorder](../README.md)
**Status:** ✅ **Done 2026-08-26.** Requirements 2–4 shipped 2026-08-25 (see §Measurement and
the outcome below); 5–6 shipped with `EPIC-005D`'s transport; requirement 1's teardown
completed 2026-08-26 — see §Outcome.
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

---

# Outcome

## The teardown, run 2026-08-26

22 files deleted: `tools/audit_dashboard/` (13), `tools/audit_dashboard_cli.py`, four engine
modules (`audit_extension.py`, `audit_service.py`, `ports.py`,
`infra/websocket_broadcaster.py`), `audit/events.py`, and the three test files (13 tests).

`audit/events.py` was **not** in §3's list and was deleted anyway: its two events
(`SystemStateChangedEvent`, `TaskCompletedEvent`) were emitted and consumed only by
`audit_service.py` and the tests going with it, so keeping them would have left two events in
the registry that nothing could ever emit. `EVENT_CATALOG.md` regenerated accordingly (16
events, down from 18).

**Requirement 1's tag already existed** (`pre-epic-005-audit`, created before the measurement
work on 2026-08-25) — but only locally. Pushing it failed with a `403`: this session's GitHub
credentials are scoped to `refs/heads/*`, not `refs/tags/*`. The requirement's *intent* is that
the deleted work stays recoverable, so it is preserved as a pushed branch,
`archive/pre-epic-005-audit`, at the commit immediately before the deletion. Recorded rather
than quietly skipped: a recovery ref that exists only in an ephemeral container is not a
recovery ref.

## Requirements 5 and 6 were met before this, without the teardown

`TraceServer` (`EPIC-005D`) was built as new code *alongside* the old broadcaster rather than
replacing it, so the auth and bind-readiness behaviour this subtask refused to lose came back —
`tests/extensions/audit/test_trace_server.py`, modelled directly on the deleted
`test_websocket_broadcaster_auth.py` — **before** anything was deleted, not after. That
ordering is the whole point of §"The cost, stated plainly": the 13 tests were not deleted and
replaced later on a promise; their replacements were green first.

## One test was rewritten, not deleted

`tests/runtime/test_task_progress_integration.py` read a task's progress back through
`AuditService.get_all_tasks_details()`. The behaviour under test is the **task manager's**, so
it was pointed at `context.tasks.tasks` directly instead. It is a better test for it: the old
collector reached the task manager through four chained `getattr`/`hasattr` guesses, any of
which falling through returned an empty list — which this test would have reported as "task
should be in output", blaming the task manager for the collector's bug.

## A real defect, found because the count did not change

After deleting 18 shipped modules, `scripts/verify_wheel_importable.py` rebuilt, reported
**"all 216 shipped modules imported"** — the same number as before — and **passed**.

setuptools copies sources into `build/lib/` and never removes what has disappeared from the
working tree. The wheel therefore still contained every deleted module, imported them
successfully, and counted them toward that green number. Verified directly by listing the
built archive: all 18 present.

`build/` is gitignored, so CI's fresh clone was never affected — but a maintainer cutting a
release from their own checkout would have shipped code this epic had just deleted, with the
guard saying PASS. `build_wheel()` now removes `build/` before every build; the count dropped
to 211 and the archive listing is clean.

This is the same failure `TASK-039` and this guard exist to prevent, one level up: not "a
command that never ran shipped", but "the check that proves commands run verified a stale
tree". A guard whose PASS is believed is worse than no guard.

## Verification

**1391 passed, 8 skipped** (down from 1403: 13 deleted tests, one rewritten, and the
event-catalog/docs guards now passing on the new content). `ruff check`, `ruff format --check`
and `mypy` (355 files) clean; the architecture guard passes; `tests/test_agents_docs_resolve.py`
green after every doc that named a deleted thing was corrected.

The docs the teardown falsified, all fixed in the same change: `architectures/architecture.md`
(its entire Clean Architecture worked example was `tools/audit_dashboard/` — replaced with
`examples/student_management`, which is real and tested), `repository.md`, `project.md`,
`modules.md`, `glossary.md`, `troubleshooting.md`, `configuration.md`, `tracing.md` §7,
`ONBOARDING.md`, `rules/deployment.md`, and `readme.md` — whose "this line comes back when
there is something behind it" placeholder now has something behind it.

The `[audit]` extra (`rich`) was removed with its only consumer, and the two
`websockets.legacy` `filterwarnings` entries in `pyproject.toml` went with the broadcaster that
used that API — a filter for a warning that can no longer fire would silently hide a real one
if the legacy API ever returned.
