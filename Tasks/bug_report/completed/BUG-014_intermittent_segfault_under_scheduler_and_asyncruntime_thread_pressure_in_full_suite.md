# BUG-014 — Intermittent `Segmentation fault` in the full test suite, with dozens of leaked `Scheduler`/`AsyncRuntime` threads at crash time

**Reported date:** 2026-09-19
**Severity:** Medium (intermittent — roughly 1 in 3 full-suite runs this session — but a hard crash, not a test failure, so it can silently read as "gate never finished" rather than "gate is red")
**Status:** ✅ Fixed (2026-09-19) — confirmed on GitHub Actions itself: `Test (Python 3.12 on ubuntu-latest)` (and all 7 other checks) green on commit `976ce7c`, run `35440802725` (https://github.com/anhembedded/Sagittarius_Engine/actions/runs/35440802725/job/105891211463). See "Fixed, 2026-09-19" section for the full root-cause and per-file breakdown. The two earlier "Fixed" closures in this same report were both premature on local evidence alone — this one is not: it is the first closure backed by the authoritative signal (`ci-rule.md` §1's two-tier clause).
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

## Requirement 6, confirmed 2026-09-19 — the real root cause

GitHub Actions crashed a **third** time, identical signature, on commit `f6ff744` (run
`35439470637`, job `105887787307`) — the commit carrying *both* the `step_timeout` propagation fix
**and** the `Scheduler.start()` orphan-guard fix an independent reviewer found. **60 live threads**
in the dump this time: 29 in `scheduler.py`'s `_run()` (now at line 257), 29 in `async_runtime.py`'s
`_run_loop()`, 1 thread-pool worker — same scale as both prior crashes. Two consecutive real GitHub
Actions runs, two different rounds of genuine fixes in between, functionally the same crash: this is
no longer explainable as a slow join under load. Requirement 6's suspicion was right, and this time
it was checked rather than left open:

```
grep -rl "\.boot(" tests/ --include=*.py | wc -l   # 24 files
# per-file .boot() vs .stop() call counts (tests/kernel/test_extension_manager.py, e.g.):
#   boots=9  stops=0
```

**`Bootstrap.boot()` (`sagittarius_engine/kernel/bootstrap.py:40,52`) unconditionally calls
`self.context.async_runtime.start()` and `self.context.scheduler.start()` on every successful
boot** — so every test that constructs an `App`/`EngineContext` and calls `.boot()` starts one real
`Scheduler` thread and one real `AsyncRuntime` thread. Across the 24 test files that call `.boot()`,
counting `.boot(` vs `.stop(` per file finds entire files with real, non-trivial boot counts and
**zero** stop calls of any kind — `tests/extensions/test_health_check_requested.py` (4 boots, 0
stops), `tests/extensions/test_dependency_validator.py` (2, 0), `tests/runtime/
test_task_progress_integration.py` (1, 0), `tests/middleware/test_middleware.py` (1, 0),
`tests/test_full_coverage.py` (8, 0), `tests/kernel/test_extension_manager.py` (9, 0),
`tests/kernel/test_core.py` (2, 0), `tests/test_agents_docs_resolve.py` (1, 0),
`tests/test_edge_cases.py` (10, 0), `tests/test_integration_io.py` (2, 0) — **40 un-stopped `boot()`
calls in these ten files alone**, each leaking a `Scheduler` + `AsyncRuntime` thread pair (checked
for a missed teardown mechanism first: these files' own `app` fixtures use plain `return`, not
`yield`, so there is no finalizer calling `stop()` either). Totalled across all 24 files: 103
`.boot()` calls against 78 `.stop()` calls of any kind (a loose proxy, but consistent with the
crash dumps' own 29-vs-29 scale). This is the accumulation mechanism Requirement 6 asked about: not
one slow join, but dozens of test files that simply never clean up the `App` they booted.

**Why the `step_timeout`/`start()` fixes didn't help:** both are real, correct fixes for what they
address (an *attempted* `stop()` that fails to join in time), but neither one applies when `stop()`
is never called at all. `App.stop()`'s honesty and retry-safety are moot for a caller that never
calls it.

**Scope decision needed before a fix lands.** A real fix here is either (a) hand-adding a
guaranteed `app.stop()` teardown (a `yield` fixture, `addfinalizer`, or `try`/`finally`) to every
one of the ~24 offending test files — direct but large and repetitive, touching files this PR never
otherwise touches — or (b) a shared, autouse mechanism (e.g. a `conftest.py`-level fixture that
tracks every `App` a test boots and stops it in teardown regardless of which local fixture
constructed it) — more architecturally correct per `fix-bug-rule.md` §1 ("move shared logic up to
the one layer that serves every consumer") but requires auditing all 24 files' actual construction
patterns first (several define their own local `app` fixture with different dependencies, not all
go through one shared fixture). Either way this is a repo-wide test-suite change, well outside
`TASK-043` E0-E2's own scope (a scheduler-cancel/contribution-registry/region-host harvest) and
outside what `PR #222`'s diff touches — consistent with the bug's own original finding that it
reproduces with that PR's diff entirely absent. Not started; needs a scope/priority decision before
work begins.

## Fixed, 2026-09-19 — the ~24-file audit, corrected and closed

The aggregate `.boot(`/`.stop(` grep counts above overstated the file list: two of the ten cited as
0-stop leaks were false positives caught only once actually read —
`tests/extensions/test_health_check_requested.py` and `tests/extensions/test_dependency_validator.py`
both call `extension.boot(context)`/`HealthExtension().boot(context)` — an `IExtension`'s own
per-extension hook against a hand-rolled fake context, never a real `App`/`Bootstrap.boot()` — so
neither leaks anything. The lesson taken from that mistake: **every remaining file was read before
being edited**, and beyond that, correctness was checked empirically rather than by grep at all —
a temporary `conftest.py`-level `autouse` fixture censused `threading.enumerate()` for
`SagittariusScheduler`/`AsyncRuntimeLoop` threads before and after every test across the full suite
(`tests/ examples/student_management/tests/`) and logged any test that left one behind. Two full
passes with this census found the real, complete list (superseding the grep-based one above):

**Straightforward missing `.stop()`** (one test each, added a trailing/`try`-`finally` call):
`tests/kernel/test_tracing_instrumentation.py` (16 tests, converted its `_app()` helper and the
one inline `App(...)` call to the new `app_factory` fixture below), `tests/test_edge_cases.py`
(converted its local `app` fixture to `yield` + `stop()`), `tests/kernel/test_extension_manager.py`
(9 tests), `tests/test_full_coverage.py` (12 call sites), `tests/runtime/
test_task_progress_integration.py`, `tests/kernel/test_core.py` (2 tests), `tests/test_integration_io.py`
(2 tests), `tests/extensions/persistence/test_database_extension_runtime.py` (3 of 6 tests shared a
`_boot_app_with_database_extension()` helper but only some callers stopped the result).

**A second, distinct real leak path — an exception past `Bootstrap.boot()`'s own try/except still
leaves threads started:** `tests/extensions/diagnostics/test_diagnostics_extension.py`'s
`test_fail_fast_aborts_the_boot_on_a_wiring_error` raises from the readiness inspection, which runs
at `self.context.lifecycle.set_ready()` — **after** `Bootstrap.boot()`'s try/except block ends (it
wraps only extension/hosted-service/scheduler startup, not `set_ready()`), so `scheduler.start()`
had already succeeded and nothing in `Bootstrap.boot()` cleans it up on this path. Wrapped in
`try`/`finally: app.stop()`.

**A third, distinct real leak path — `App.stop()` catching a mocked subsystem's exception leaves
the real thread unjoined:** `tests/runtime/test_exception_cases.py`'s
`test_app_stop__scheduler_raises__other_subsystems_still_stop` and
`test_app_stop__multiple_failures__logs_all_errors` (and, separately, `tests/kernel/
test_extension_manager.py`'s predecessor-style pattern) mock `context.scheduler.stop`/
`context.async_runtime.stop` to raise, in order to test `App.stop()`'s own per-step error handling
(`ci-rule.md`-adjacent: a hung/failing step must not block the rest of shutdown). The mock replaces
the method entirely, so `App.stop()`'s call to it never does the real join — the mocked
`RuntimeError` is caught and logged exactly as production would, but the actual OS thread stays
alive. `test_bootstrap_boot__rollback_cleanup_fails__logs_error_without_crash` has the identical
shape (`AsyncRuntime.start()` runs for real at `bootstrap.py:40`, before the mocked
`hosted_services.start()` fails). Fixed by bypassing the mock in a `finally` block and calling the
real unbound class method directly on the instance (`Scheduler.stop(app.context.scheduler)` /
`AsyncRuntime.stop(app.context.async_runtime)`), which correctly does the real join without
touching what the test is actually asserting on.

**A fourth path — the app is booted entirely inside code the test never gets a handle to:**
`tests/extensions/diagnostics/test_doctor_cli.py` already had an `_apps` list +
`_stop_apps` autouse-fixture pattern for its own `clean_app()`/`app_with_a_typo()`/
`app_with_only_a_warning()` helpers, but three tests instead exercise `cli.main()` end-to-end
against `examples.student_management.doctor_target:build` — `cli.main()` calls that factory and
gets back an already-booted `App` with no way for the test to reach in and stop it (a real CLI
invocation legitimately never needs to; the process exits). Fixed by patching `App.boot` itself,
for the duration of each test in this file, to self-register whichever instance called it into the
same `_apps` list — catching the leak regardless of which code path constructed the `App`, without
`cli.py` or `doctor_target.py` needing a test-only escape hatch.

**A fifth — most of the file's tests discarded the return value entirely:**
`examples/student_management/tests/presentation/enroll_form/test_enroll_form_iview.py`'s `_boot()`
helper returns the built `App`, but 4 of its 6 tests never captured it (`_boot(tmp_path)` as a bare
statement) — only the 2 tests that did capture it also called `.stop()`. Fixed by capturing and
stopping in all 4.

**Shared mechanism added** (`tests/conftest.py`): an `app_factory` fixture, the same
tracked-factory-with-teardown shape as the file's existing `thread_pool_bus_factory`/
`ipc_broker_factory`, used by `test_tracing_instrumentation.py`, `test_extension_manager.py`, and
`test_full_coverage.py` in place of bare `App(...)` construction where a shared helper made that the
more natural fix than a one-off `try`/`finally`.

**Verification.** The thread census (kept only as a diagnostic, not committed) found **zero**
leaked `Scheduler`/`AsyncRuntime` threads across two full passes of the entire suite after these
fixes — the first empirical (not inferential) confirmation this session has had, superseding every
grep-based count above. `pwsh scripts/ci-local.ps1 -Full` run 3 consecutive times post-fix, all
`RESULT: PASS`, zero `Segmentation fault`/`FAILED`/`ERROR`/`Traceback` in any of the three raw logs
(`logs/ci-local-20260919-113602.log`, `-113655.log`, `-113745.log`) — only the pre-existing,
separately-tracked `gc: 45 uncollectable objects` `ResourceWarning`, unchanged. Notably, one
diagnostic run *before* these last fixes (still on top of the `step_timeout`/`start()`-guard fixes
alone) **did** reproduce the segfault locally for the first time all session — 24 threads, 12
Scheduler/AsyncRuntime pairs, the identical signature — direct proof this repo's local dev
container can hit this race once the leak is large enough, and that the earlier "local never
reproduces it" framing was really "the leak wasn't yet large enough to reproduce it locally," not a
structural difference between environments.

Given the ~1400-test full suite (~13 files, ~40 individual sites) and the demonstrated ~1-in-3ish
historical rate on GitHub Actions specifically, this fix is reported here with real, empirical,
census-based evidence rather than "no crash in N runs" — and GitHub Actions' own `Test` job on the
pushed commit, the authority this report closes against per `ci-rule.md` §1's two-tier clause, is
now confirmed green: commit `976ce7c`, run `35440802725`, all 8 checks (`Test`, `Lint & Type Check`,
`Security Audit`, `Package Import Guard`, `Performance Benchmark`, `Build & Distribute Check`,
`Architecture Guard`, `Reference Applications`) `success`. Closed for real.

## Requirements (reopened)

5. ~~Run the full gate several more times, both locally and by watching GitHub Actions on this PR~~
   — **done, see "Fixed" section above; 3/3 clean full-gate runs plus a zero-leak thread census.**
6. ~~Investigate whether something beyond a single slow join is leaking whole `Scheduler`/
   `AsyncRuntime` *instances*~~ — **confirmed 2026-09-19, see "Requirement 6, confirmed" above.**
7. ~~If the segfault recurs even with the `step_timeout` fix, treat "GitHub Actions' runner reliably
   reproduces this" as a fact to design verification around~~ — **superseded: the leak also
   reproduced locally once it grew large enough (see "Fixed" section); the earlier framing that
   local never reproduces it was itself not quite right.**
8. ~~Fix the ~24 test files (and/or add the shared teardown mechanism) that `.boot()` an `App`
   without ever calling `.stop()`~~ — **done, see "Fixed" section above.**
9. ~~Watch GitHub Actions' `Test` job on the next push and confirm green before treating this report
   as closed for real~~ — **done: commit `976ce7c`, run `35440802725`, all 8 checks green.**

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
