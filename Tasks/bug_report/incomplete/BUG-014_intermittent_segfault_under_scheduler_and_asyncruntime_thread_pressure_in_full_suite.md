# BUG-014 — Intermittent `Segmentation fault` in the full test suite, with dozens of leaked `Scheduler`/`AsyncRuntime` threads at crash time

**Reported date:** 2026-09-19
**Severity:** Medium (intermittent — roughly 1 in 3 full-suite runs this session — but a hard crash, not a test failure, so it can silently read as "gate never finished" rather than "gate is red")
**Status:** 🔴 Open
**Found by:** `TASK-043` E1, while verifying the contribution-mechanism harvest's full local gate

---

## What is wrong

`pwsh scripts/ci-local.ps1`'s "Pytest — Full Suite" step, and a plain `pytest tests/ examples/
student_management/tests/ ...` invocation of the same command, crash the interpreter with `Fatal
Python error: Segmentation fault` roughly 1 run in 3 (2 crashes out of 5 full-suite runs today).
Both crashes happened at the same point in progress — **~94%**, immediately after
`tests/test_examples.py::test_stress_boot_shutdown_cycles` and
`test_stress_task_and_scheduler_under_load` — and both crash dumps show the same shape: **~100
leaked threads** still alive at the moment of the fault, overwhelmingly

```
Thread 0x...:
  File ".../threading.py", line 359 in wait
  File ".../sagittarius_engine/runtime/scheduler/scheduler.py", line 220 in _run
  ...
Thread 0x...:
  File ".../selectors.py", line 468 in select
  File ".../asyncio/base_events.py", line 1949 in _run_once
  File ".../asyncio/base_events.py", line 641 in run_forever
  File ".../sagittarius_engine/runtime/async_runtime/async_runtime.py", line 36 in _run_loop
  ...
```

i.e. dozens of `Scheduler._run()` and `AsyncRuntime._run_loop()` background threads from earlier
tests, still running, never joined. A third run (green) also logged, at interpreter shutdown
(after "Tests passed"):

```
gc:0: ResourceWarning: gc: 45 uncollectable objects at shutdown; use gc.set_debug(gc.DEBUG_UNCOLLECTABLE) to list them
```

which is the same failure family — objects (very likely native Qt/QML ones, given the extension
module list in the crash dump: `PySide6.QtCore/QtGui/QtWidgets/.../QtQuick`) that a fixture never
tore down, surviving to process-exit GC.

## Reproduction

Today, 2026-09-19, in `/home/user/anhembedded/sagittarius_engine` on this session's branch
(`task/TASK-043-e0-scheduled-job-cancel`, commit `5e89ff1`, no working-tree changes at the time):

| Run | Invocation | Result |
| :-- | :--- | :--- |
| 1 | `pwsh scripts/ci-local.ps1` (full gate) | **Segfault** at ~94%, `logs/ci-local-20260919-093137.log` |
| 2 | `pytest tests/ -v` (plain, no coverage) | 1376 passed, 7 skipped — green |
| 3 | `pwsh scripts/ci-local.ps1` (full gate, rerun) | PASS, `logs/ci-local-20260919-093341.log`, but with the `gc: 45 uncollectable objects` `ResourceWarning` above |
| 4 | `pytest tests/ examples/student_management/tests/ ... --cov=... -q`, with `sagittarius_engine/extensions/pyside_mvc/runtime/{contribution_descriptor,contribution_error,contribution_registry,i_contribution_registry,size_hint,surface_declaration}.py`, both `pyside_mvc/__init__.py`/`runtime/__init__.py` edits, and `tests/extensions/pyside_mvc/test_contribution_registry.py` **`git stash`-ed out** (i.e. on a tree closer to plain `5e89ff1`) | **Segfault**, exit 139 |

Run 4 is the decisive one: it reproduces with the new `TASK-043` E1 harvest files entirely absent
from the working tree, so **this is not caused by that change** — see `TASK-043`'s own note for
that finding. Whatever the true trigger is, it predates and is independent of `EPIC-001D`
objective 2's harvest landing.

## Why it matters

A segfault is not a `FAILED` pytest line — `scripts/ci-local.ps1`'s own automated log scan (which
greps for `- (WARNING|ERROR|CRITICAL) -` bracketed records) does not catch either the fault or the
shutdown-time `ResourceWarning`, since neither is routed through the app's own logger. A session
trusting `RESULT: PASS` plus the script's own scan, without independently grepping the raw log for
`Segmentation fault`/`ResourceWarning` (as `ci-rule.md`'s own doctrine already requires, for a
different reason), would report a gate that only happened to come up green this time.

## Hypothesis, not yet confirmed

`test_examples.py::test_stress_boot_shutdown_cycles` / `test_stress_task_and_scheduler_under_load`
(both immediately preceding the crash point in every progress trace collected today) construct and
tear down many `Scheduler`/`AsyncRuntime`-bearing app instances under load; if their shutdown does
not actually join every scheduler/async-runtime thread, load from those two tests would explain
the ~100 leaked threads still alive by the time later Qt-heavy tests (`test_full_coverage.py`'s
event-bus/thread-pool tests, then the QML gallery/state-console tests near the very end) run
against a process already carrying that much uncollected background-thread and native-object
weight. **Not verified against the actual shutdown code** — filed from the crash-dump evidence
above, for whoever picks this up to confirm or refute against `Scheduler.shutdown()` /
`AsyncRuntime.stop()`'s real join logic.

## Requirements

1. Confirm whether `Scheduler`/`AsyncRuntime` teardown (used by whatever fixture backs
   `test_stress_boot_shutdown_cycles`) actually joins its background thread(s), or only signals
   them to stop.
2. If threads are leaking: fix the shutdown path to join with a timeout, and add a regression test
   that boots+shuts down N times and asserts `threading.active_count()` (or an equivalent thread
   census) returns to baseline.
3. If the true cause is instead the native Qt/QML side (the `gc: 45 uncollectable objects`), trace
   what specifically survives GC at shutdown (`gc.set_debug(gc.DEBUG_UNCOLLECTABLE)`, per the
   warning's own suggestion) rather than guessing.
4. Once fixed, run the full gate several times in a row (the crash's own ~1-in-3 rate means a
   single green run is not proof) before closing.

## Related

- `TASK-043` E1 — where this was found; not blocking, not caused by that change (evidence above)
- `EPIC-004C_elite_migration.md` (this repo) — an earlier full-gate report explicitly used "no
  `ResourceWarning`" as part of its own green-gate bar, so this is a real regression against that
  bar, not a newly-tolerated class of noise
