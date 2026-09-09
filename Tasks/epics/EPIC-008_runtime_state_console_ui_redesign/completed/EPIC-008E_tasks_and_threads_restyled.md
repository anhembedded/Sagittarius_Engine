# EPIC-008E: Tasks & threads restyled

- **Status**: ✅ Done
- **Category**: Tooling (`tools/state_console`), Engine (`sagittarius_engine/runtime/tasks`, `sagittarius_engine/runtime/scheduler`)
- **Started Date**: 2026-09-09
- **Completed Date**: 2026-09-09

---

## 🎯 Summary & Objectives

Restyle the Tasks & threads screen onto `reference/handoff.md` §7.5: a sortable Tasks table
with an expandable failed-row detail, a Thread pools table with a real `outstanding` column,
and a Limits tab (task registry cap, scheduler figures, a real per-job table).

Per `EPIC-008`'s own milestone table, this is done when "a failed task's stack is readable
after a click, one at a time" — a literal requirement this engine could not satisfy before this
subtask: `TaskSnapshot`'s own docstring previously said outright that no traceback or thread
identity ever left the log line a task's failure produced. Meeting the Definition of Done meant
reversing that earlier, deliberate `EPIC-007B` decision, not just restyling a screen.

## 📐 Implementation Plan / Overview

- **A real stack, not a re-derived approximation.** `BackgroundTask` gained `error_stack`/
  `thread_name`, captured with `traceback.format_exc()`/`threading.current_thread().name` at
  the exact `except Exception as e:` blocks in `TaskManager` that already catch a task's
  failure — the same "expose data already sitting right there" reasoning as `EPIC-008B` §4's
  `LifecycleState.modules`, not a new capability. `TaskSnapshot`/`TaskRecord` gained matching
  `error_type`/`stack`/`thread` fields; `TaskCollector` forwards them. An async task's failure
  leaves `thread` empty on purpose — it runs on the shared event-loop thread, not a worker of
  its own, and naming that thread as the task's "owner" would be a specific, false claim,
  the same "elevated, not climbing" honesty this epic's own Container subtask already argued
  for a different fault.
- **A real per-job table, not just aggregate counts.** `LifecycleState` gained a `jobs` field
  (a new `JobRecord`: name, trigger description, seconds to next fire) built from
  `Scheduler.jobs` — the exact same live list `scheduler_jobs_without_next_run` already reads,
  so it inherits that field's own documented fragility (a broken job can vanish from `.jobs`
  between one snapshot and the next). `ITrigger` gained a concrete `describe()` (default: the
  class name, overridden by both shipped triggers) so a job's trigger has a real, human-readable
  column rather than nothing.
- **Not built: the handoff's "paused" scheduler figure.** Nothing in this engine's `Scheduler`
  can pause a job — there is no such state to count. Showing "0 paused" would claim a capability
  that does not exist, unlike the screen's real "broken" figure. Named rather than invented, the
  same discipline `EventsScreen.qml`'s own two-of-four sub-tabs already established.
- **Tasks / Thread pools / Limits sub-tabs** built on the shared `SectionSubTabs` kit component
  (this epic's own prior design-review extraction), not a fourth hand-rolled copy.
- **BUG-013 hit twice more, fixed both times before shipping, not after:** a right-aligned
  column immediately followed by a left-aligned one fuses into one string in `AppDataTable`.
  Caught this time via this subtask's own screenshot review (not a test) in both the Tasks
  table (`Elapsed`/`Owner` → `"ElapsedOwner"`, `"2sSagittariusBgTask_0"`) and the Limits Jobs
  table (`Next fire`/`State`). Fixed the same way Events/Container fixed it originally: move the
  left-aligned column before the right-aligned block.
- **A second, worse bug found the same way, in already-shipped code:** the failed-row detail's
  first version nested its error-type/message/stack `Text` items *inside* the same `Rectangle`
  whose `opacity: 0.05` sets the fault-tint background — QML's `opacity` multiplies onto every
  descendant, so the stack came out nearly invisible, failing this subtask's own literal
  Definition of Done. Comparing against `EventsScreen.qml`'s near-identical `UndeclaredDetail`
  and its WIRING BUG banner found the *same* mistake already shipped there (`EPIC-008C`,
  not caught during that subtask's own review). Fixed in all three places: the tint is now an
  `Item`'s background sibling, not the text's parent.
- **Two new, real `DemoFaultsExtension` seeds**, the same "one instance of each condition"
  reasoning as every other seed there: `_seed_failed_task` (a real background task that raises
  immediately, so `TaskManager` captures a real traceback and worker thread before any client's
  first snapshot) and `_seed_scheduled_job` (a real, healthy job on the live `Scheduler` — not
  where the existing D3 "dead job" condition is seeded, since that seed's own docstring already
  explains why a dead job on the live scheduler is dropped again within milliseconds).

## 🧪 Verification & Test Coverage

- `tests/runtime/tasks/test_task_manager.py`: two tests replaced (their own names encoded the
  now-superseded "no thread field" decision) with tests for the real captured stack/error-type/
  worker-thread on a failed sync task, and the stack-but-no-thread behavior for a failed async
  task (`_wrap_coro` exercised directly via `asyncio.run`).
- `tests/extensions/state_console/test_lifecycle_collector.py` (+3 tests): `jobs` is empty with
  no scheduler, reports a real name/trigger/positive time-to-next-fire, and reports `None` for a
  job with no next run.
- `tests/tools/state_console/test_tasks_presenter.py` (new, 6 tests): a failed task carries its
  real owner/error type/stack, a completed one carries none of it, `outstanding` is
  `submitted - completed`, jobs report name/trigger/next-fire, a broken job reports
  `"no next fire"`, and jobs is empty with no lifecycle.
- `tests/tools/state_console/test_tasks_screen.py` (+3 tests, 5 total): sub-tab counts are real
  (including "Limits" correctly carrying no count concept at all), a failed row expands to show
  the real error type/message/stack, and the Jobs table shows a broken job as `"none — dead"`
  with the `"no next fire"` state tag — this last test caught the `None`-surfaces-as-`undefined`
  QML formatter bug (`"in NaNs"`) that produced.
- `examples/student_management/tests/infrastructure/demo_faults/test_extension.py` (+2 tests):
  the failed-task seed produces a real `ValueError`/stack/thread through
  `ITaskManager.snapshot()`, and the scheduled-job seed is really on the live scheduler with a
  real next-run time.
- Full local CI green, read from the log file directly: 1508 passed, 23 skipped, 0 failed;
  architecture tests, packaging checks, and the import guard all passed. One pre-existing,
  unrelated `PytestUnhandledThreadExceptionWarning` in `test_task_progress_integration.py`
  (a `datetime.now` mock's `side_effect` list exhausted by a still-running scheduler thread) —
  a warning, not a failure, confirmed unrelated to this subtask's own files.
- A segfault reproduced identically whether or not this subtask's changes were present when
  running `tests/tools/state_console/` alone repeatedly — the same pre-existing, load-dependent
  flake in background scheduler/async-runtime threads this epic's `SectionSubTabs` work already
  confirmed against the pre-change commit. The full local CI run came back clean.
- Screenshots offscreen against the real demo app, including the two new seeds: Tasks tab (a
  real failed `export_roster_pdf` row, expanded to show `VALUEERROR`, the message, and the full
  real traceback — all legible after the opacity-nesting fix), Thread pools tab (a real
  `Outstanding` column), and Limits tab (`1 / 50` registry cap with a bar, `1 jobs · 0 broken`
  scheduler figures, and a real Jobs table row: `_noop · every 0:05:00 · active · in 297s`).
