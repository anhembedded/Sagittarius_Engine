# BUG-014 — Intermittent `Segmentation fault` in the full test suite, with dozens of leaked `Scheduler`/`AsyncRuntime` threads at crash time

**Reported date:** 2026-09-19
**Severity:** Medium (intermittent — roughly 1 in 3 full-suite runs this session — but a hard crash, not a test failure, so it can silently read as "gate never finished" rather than "gate is red")
**Status:** 🔴 Reopened (2026-09-19) — see "Reopened" section; the 2026-09-19 "Fixed" closure below was premature
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

## Root cause, confirmed 2026-09-19

Requirement 1's own question, answered by reading `Scheduler.stop()` and `AsyncRuntime.stop()`
directly: both *did* attempt to join their background thread, but **neither checked whether the
join actually succeeded.**

```python
# Scheduler.stop() -- before
if self._thread is not None:
    self._thread.join(timeout=5.0)
    self._thread = None          # <- ran unconditionally, whether or not join succeeded
```

A join that timed out (plausible under the exact CI load `test_stress_task_and_scheduler_under_load`
creates — 100 spawned tasks plus 20 recurring jobs all contending for `Scheduler._lock`) left the
real OS thread running, while the code discarded the only reference to it and logged nothing. The
thread became permanently untracked and unjoinable — exactly the "leaked, never joined" shape every
crash dump showed.

`AsyncRuntime.stop()` had the same unconditional-clear defect, plus a second, more dangerous one:
after the same blind `join(timeout=5.0)`, it called `self.loop.close()` **regardless of whether the
thread's own `run_forever()` had actually returned.** Closing an `asyncio` event loop while another
thread is still iterating it is undefined behaviour in CPython — not merely a resource leak but a
live suspect for the segfault itself, not just the thread-count symptom.

## Fix

Both `stop()` methods now check `thread.is_alive()` after `join(timeout=...)`:
- Still alive → log an `ERROR` naming the timeout, leave `self._thread` (and, for `AsyncRuntime`,
  `self.loop`) **set rather than discarded**, and return without claiming success. A later `stop()`
  call — no longer blocked by `_running` already being `False` — can retry the join.
- `AsyncRuntime` additionally never reaches `loop.close()` on that path, so a loop still running on
  its own thread is never closed out from under it.

`sagittarius_engine/runtime/scheduler/scheduler.py`, `sagittarius_engine/runtime/async_runtime/
async_runtime.py`. Both `stop()` methods gained a `timeout: float = 5.0` parameter (previously
hard-coded) so the honest-failure path is directly testable without a multi-second real wait.

**Regression tests**, both driving the real thread-lifecycle mechanism directly via a
`threading.Event`-blocked thread standing in for a slow-to-notice tick (not `_run()`'s own
scheduling logic, which existing tests already cover):
`tests/runtime/scheduler/test_scheduler.py::test_stop_leaves_a_still_running_thread_tracked_instead_of_discarding_it`,
`tests/runtime/test_exception_cases.py::test_async_runtime__stop_thread_still_alive__does_not_close_the_running_loop`.
Mutation-verified: reverted each fix to the pre-fix unconditional-clear behaviour, confirmed the
matching new test fails for the right reason (no error logged / the loop is discarded and would
have been closed), restored — `git diff --stat` clean.

**Verification (requirement 4):** 3 consecutive full `pwsh scripts/ci-local.ps1` runs after the fix,
all `RESULT: PASS` with zero `Segmentation fault`/`Fatal Python error` in the raw log —
`logs/ci-local-20260919-104944.log`, `logs/ci-local-20260919-105108.log`,
`logs/ci-local-20260919-105206.log`. The pre-fix rate was 2 segfaults in 5 runs; 3-for-3 clean
afterward is not absolute proof against a residual, rarer race, but is real evidence against the
documented ~1-in-3 rate.

**Not fixed, and not claimed to be:** the `gc: N uncollectable objects at shutdown` `ResourceWarning`
(requirement 3) still appeared in the clean runs above (`45` uncollectable objects, same count as
before the fix). This looks like a distinct, non-crashing symptom — plausibly native Qt/QML objects,
not the Python-level thread handles this fix addresses — and stays open as its own question if it
starts crashing again; this fix's evidence only supports closing the segfault/thread-leak half of
this report.

**A second, unrelated flake surfaced while verifying this fix**, filed separately rather than folded
in here: `BUG-015` (`tests/extensions/ui_state/test_ui_state_coordinator.py`'s `QTimer` debounce
test, load-sensitive, unrelated to `Scheduler`/`AsyncRuntime`).

## Reopened, 2026-09-19 — the fix above was necessary but not sufficient

GitHub Actions' `Test (Python 3.12 on ubuntu-latest)` job (run `35438668390`, commit `3acbea4` —
**the commit that introduced the fix above**) crashed with the identical signature: `Segmentation
fault (core dumped)` during `pytest tests/ examples/student_management/tests/ --cov=... -q`, with
**59 live threads** in the crash dump — 28 in `scheduler.py`'s `_run()` (blocked on
`self._cond.wait()`, now at line 241) and 30 in `async_runtime.py`'s `_run_loop()` (blocked on
`run_forever()`'s `select()`), plus 1 thread-pool worker. This is the same leaked-thread family the
original report described, reproducing on GitHub's own runner right after the fix meant to close it
— proof the closure above was premature. The 3 clean local runs cited as evidence were real, but
insufficient: GitHub's runner shares a weaker, more contended CPU than the local dev container, and
this session's local reproduction never actually matched that load profile.

**Why the original fix didn't stop the leak.** The original fix made `Scheduler.stop()` /
`AsyncRuntime.stop()` *honest* about a join that times out — it logs an `ERROR` and leaves the
thread tracked instead of silently discarding the reference — and *retry-safe*, so a second
`stop()` call can pick up where the first left off. But nothing in the codebase ever makes that
second call. `App.stop()` — the only caller that matters in a real shutdown — runs each step
exactly once, on a dedicated daemon thread bounded by `step_timeout`
(`sagittarius_engine/kernel/app.py::App._run_stop_step`, by design: a hung extension must never
block the rest of shutdown). A step that times out is logged and abandoned, never retried. So the
underlying OS thread was exactly as leaked after the original fix as before it — the only change
was that the leak became a logged `ERROR` instead of a silent one. The fix improved diagnosability,
not the actual thread lifecycle, which is why the segfault signature reproduced unchanged.

**A second, real defect found while re-investigating (`sagittarius_engine/kernel/app.py`
`App.stop()`):** the scheduler/async-runtime shutdown steps were wired as
`("scheduler", self.context.scheduler.stop)` / `("async runtime", self.context.async_runtime.stop)`
— bound methods called with **no arguments** inside `_run_stop_step`'s own `_runner()`. Both
methods now take a `timeout` parameter (added by the original fix), but nothing passed one through,
so they silently fell back to their own hard-coded `timeout=5.0` default regardless of the
`step_timeout` (10.0s default, and the actual budget `App.stop()`'s own docstring promises "each
individual step") the caller configured. A background thread that is genuinely about to exit, just
slower than 5.0s to be scheduled under a heavily loaded, coverage-instrumented, ~1400-test shared
process, was abandoned with **half** the budget every other step gets. This is now fixed:
`App.stop()`'s step list passes `timeout=step_timeout` through to both calls, and a regression test
(`tests/kernel/test_app.py::test_app_stop_gives_the_scheduler_and_async_runtime_the_full_step_timeout`)
locks the wiring, mutation-verified against the exact pre-fix no-argument call.

**What this does and does not claim.** Doubling the join budget for these two steps is a genuine,
narrowly-scoped correction of a real plumbing bug (a documented parameter silently not reaching its
callee) — not a guess. It should reduce, not necessarily eliminate, the rate at which a slow-to-exit
thread gets abandoned under load. It does **not** by itself explain why dozens of *separate*
`Scheduler`/`AsyncRuntime` instances (one pair per `App()` under test) end up leaked simultaneously
across a single ~1400-test session, nor has the exact native mechanism that turns "many leaked
Python threads alive" into `Segmentation fault` been identified — only the accumulation path (one
failed join is never retried, so it is permanent for the rest of the process) is understood. Both
remain open questions; see Requirements below.

## Requirements (reopened)

5. Run the full gate several more times, both locally and by watching GitHub Actions on this PR,
   after the `step_timeout` propagation fix — do not close on local runs alone again, given this is
   exactly the mistake that reopened this report.
6. Investigate whether something beyond a single slow join is leaking whole `Scheduler`/
   `AsyncRuntime` *instances* — e.g. a fixture or composition-root path that constructs and
   `.start()`s one without a guaranteed `.stop()` on every exit path (including test failure) — since
   28+30 simultaneously alive instances is a lot to attribute to occasional slow joins alone.
7. If the segfault recurs even with the `step_timeout` fix, treat "GitHub Actions' runner reliably
   reproduces this; the local dev container does not" as a fact to design verification around, not
   a fact to work around by re-running until green.

## Related

- `TASK-043` E1/E2 — where this was found; not blocking, not caused by that change (evidence above)
- `EPIC-004C_elite_migration.md` (this repo) — an earlier full-gate report explicitly used "no
  `ResourceWarning`" as part of its own green-gate bar; the `ResourceWarning` half of that bar is
  still not met (see "Not fixed" above)
- `BUG-015` — the unrelated flake this fix's own verification runs surfaced
- `BUG-016` — a second leaked-thread instance, this time corrupting a different test's mock
  instead of crashing, found while investigating this reopening; direct evidence for the
  "why do dozens of instances leak simultaneously" question above
- PR #222, GitHub Actions run `35438668390`, job `105885679152`, commit `3acbea4` — the recurrence
  that reopened this report
