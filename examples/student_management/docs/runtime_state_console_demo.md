# Runtime state console demo — `-Console` / `-DemoFaults`

Written 2026-08-27 while building `EPIC-007D`, at the point the whole thing was run for real:
`console.py --demo-faults` booted, `sagittarius-trace snapshot` connected from a second
terminal, and read back exactly what was seeded.

## The two switches

```powershell
# the sample app, console attached, correctly wired — every panel green
.\examples\student_management\run.ps1 -Console

# the same app with one of everything wrong — every panel populated
.\examples\student_management\run.ps1 -Console -DemoFaults

# non-default port, and a token, as a consumer would run it
.\examples\student_management\run.ps1 -Console -ConsolePort 9001 -ConsoleToken dev-only
```

Read it from a second terminal:

```bash
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
```

`-Console` boots `console.py` — headless, no GUI, no CLI subcommand — with
`StateConsoleExtension` attached the same way `gui.py` attaches `PySideMvcExtension`
(`build_app(extra_extensions=[...])`). It blocks until Ctrl+C, then stops the app cleanly.

## `-DemoFaults`: why the sample app needs to be able to lie on purpose

`sagittarius-trace snapshot` against the default `-Console` run shows eight green panels and
proves nothing about whether the console actually *detects* anything wrong — the same trap
`EPIC-005`'s `D1` fell into (a dashboard that looked fine because it was never shown a
failure). `DemoFaultsExtension` (`examples/student_management/infrastructure/demo_faults/`)
plants one instance of each condition the engine's diagnostics claim to catch:

| Seeded | Check | Where it shows up |
| :--- | :--- | :--- |
| a handler subscribed to `demo.roster_syncd`, one letter short of the declared `demo.roster_synced` | A2 (error, with a `did you mean` hint) | `sagittarius-doctor`, and `sagittarius-trace snapshot`'s `events` section (`registered=False`) |
| an emit of `demo.roster_exported` with nobody listening | R1 | `RuntimeMonitor.findings()` — logged at shutdown, not yet on the wire (`EPIC-007F`) |
| a handler on `demo.student_deleted` that always raises `KeyError`, behind a `ResilientEventBus` wrapping the app's real bus | R2, and a real dead letter | `RuntimeMonitor.findings()` + `DemoFaultsExtension.resilient_bus.get_dlq()` — same caveat |
| a transient `_ReportService` needing an unbound `_ReportSystemClock` | C2 | `sagittarius-doctor`, and `sagittarius-trace snapshot`'s `container` section (the registration itself) |
| a scheduled `nightly_report` seeded with no next run time | D3 | `DemoFaultsExtension.dead_scheduled_job` directly — **not** the live `Scheduler`, see below |
| an `ExclusiveAction` slot taken and never released | — | `DemoFaultsExtension.exclusive_action.held_slot()` directly — not yet on the wire (`EPIC-007B` added the API, no `EPIC-007C` collector reads it yet) |
| an `EnrolmentFlow` state machine driven through one illegal move | — | `DemoFaultsExtension.rejected_transition` — an `InvalidStateTransitionError`, not a `False` return (`REF-005`) |

Every row is independently asserted on in
`examples/student_management/tests/infrastructure/demo_faults/` — the extension's own public
attributes make each seed checkable without a live console client attached.

### Why D3's seed never touches the running app's own `Scheduler`

Found while building this: setting `next_run = None` on a job actually appended to the live,
running `Scheduler` used to **crash its background thread** — `Scheduler._run()` compared
`None <= datetime`, unhandled, and the thread died silently (fixed in
`runtime/scheduler/scheduler.py`). With that fixed, appending a dead job to the live scheduler
is merely *useless* rather than fatal: `add_job()` wakes the background thread immediately,
and its very next pass drops a `next_run=None` job from `.jobs` again — so there is no stable
window in which anything could observe it there. `DemoFaultsExtension.dead_scheduled_job` is a
real, standalone `ScheduledJob` instead, stable for the life of the extension, and what a test
or `WiringInspector` should be pointed at directly.

## Why some of this only reaches a log line, not the console's wire format

`StateSnapshot` (`EPIC-007A`) has seven collected sections today —
lifecycle/events/container/tasks/thread_pools/bounded/config. R1, R2, the dead-letter queue,
`ExclusiveAction.held_slot()`, and the FSM's rejected transitions have **no field yet**; that
panel is `EPIC-007F`'s, not this milestone's. `DemoFaultsExtension` seeds all of them anyway,
and logs the ones `RuntimeMonitor` sees at shutdown (`DiagnosticsExtension(watch_runtime=True)`'s
own pattern), because the seed is real infrastructure work independent of when the matching
panel ships — and because a demo that only seeds what already has somewhere to be shown would
silently shrink every time a future milestone's scope was drafted.

## Keeping `sagittarius-doctor --strict` green

`doctor_target.build()` (`EPIC-006E`) calls `build_app()` with **no** `extra_extensions`.
`DemoFaultsExtension` reaches an app only through that parameter, so the CI gate

```bash
.venv/bin/sagittarius-doctor examples.student_management.doctor_target:build \
  --handler-package examples.student_management --strict
```

never sees it — asserted directly in
`tests/extensions/diagnostics/test_doctor_cli.py::test_demo_faults_extension_existing_does_not_leak_into_the_doctor_gate`,
which imports and constructs the class and re-runs the same `--strict` check.
