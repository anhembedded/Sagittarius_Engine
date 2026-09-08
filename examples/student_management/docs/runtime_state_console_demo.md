# Runtime state console demo — `-Console` / `-DemoFaults`

Written 2026-08-27 while building `EPIC-007D`, at the point the whole thing was run for real:
`console.py --demo-faults` booted, `sagittarius-trace snapshot` connected from a second
terminal, and read back exactly what was seeded. **Updated 2026-08-27** once `EPIC-007E`
(the QML dashboard) and `EPIC-007F` (the dead-letter/state-machine panel) both shipped —
see "Seeing it in a window" below for the mode this doc originally had no answer for.

## The two switches

```powershell
# the sample app, console attached, correctly wired — every panel green
.\examples\student_management\run.ps1 -Console

# the same app with one of everything wrong — every panel populated
.\examples\student_management\run.ps1 -Console -DemoFaults

# non-default port, and a token, as a consumer would run it
.\examples\student_management\run.ps1 -Console -ConsolePort 9001 -ConsoleToken dev-only
```

Read it from a second terminal, as text:

```bash
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
```

`-Console` boots `console.py` — headless, no GUI, no CLI subcommand — with
`StateConsoleExtension` attached the same way `gui.py` attaches `PySideMvcExtension`
(`build_app(extra_extensions=[...])`). It blocks until Ctrl+C, then stops the app cleanly.

## Seeing it in a window

The text renderer above is the CI/SSH path. To see the actual five-screen QML dashboard
(`EPIC-007E`) instead — Overview, Events & wiring, Container, Tasks & threads, Signals,
navigated through a sidebar — from the repo root:

```powershell
# one command: starts the sample app with -Console -DemoFaults, waits for the port,
# opens the dashboard against it, and stops the sample app when the window closes
.\scripts\run-console.ps1 -Demo

# or attach to an app you already started (e.g. via run.ps1 -Console above)
.\scripts\run-console.ps1 -Attach ws://127.0.0.1:8781
```

The Signals screen (`EPIC-007F`) is what makes `-DemoFaults` worth running before opening the
window: without it, that screen has an empty dead-letter table and no watched state machines.
`console.py --demo-faults` calls `StateConsoleExtension.watch_dlq()`/`watch_state_machine()`
before seeding the faults (`DemoFaultsExtension(console=...)`), so the demo's own dead letter
and rejected transition are what the window shows — not synthetic data invented for a
screenshot.

## `-DemoFaults`: why the sample app needs to be able to lie on purpose

`sagittarius-trace snapshot` against the default `-Console` run shows every panel green (a
`tasks` section only appears once something is actually running, so the exact count of
printed sections varies — the point is that nothing is red) and proves nothing about whether
the console actually *detects* anything wrong — the same trap
`EPIC-005`'s `D1` fell into (a dashboard that looked fine because it was never shown a
failure). `DemoFaultsExtension` (`examples/student_management/infrastructure/demo_faults/`)
plants one instance of each condition the engine's diagnostics claim to catch:

| Seeded | Check | Where it shows up |
| :--- | :--- | :--- |
| a handler subscribed to `demo.roster_syncd`, one letter short of the declared `demo.roster_synced` | A2 (error, with a `did you mean` hint) | `sagittarius-doctor`, and `sagittarius-trace snapshot`'s `events` section (`registered=False`) — the QML dashboard's Events & wiring screen |
| an emit of `demo.roster_exported` with nobody listening | R1 | `RuntimeMonitor.findings()` — logged at shutdown, still not on the wire (no `StateSnapshot` field for it yet) |
| a handler on `demo.student_deleted` that always raises `KeyError`, behind a `ResilientEventBus` wrapping the app's real bus | R2, and a real dead letter | `RuntimeMonitor.findings()` (R2, logged) **and**, with a console attached, `sagittarius-trace snapshot`'s `signals` section — the QML dashboard's Signals screen (`EPIC-007F`) |
| a transient `_ReportService` needing an unbound `_ReportSystemClock` | C2 | `sagittarius-doctor`, and `sagittarius-trace snapshot`'s `container` section (the registration itself) — the QML dashboard's Container screen |
| a scheduled `nightly_report` seeded with no next run time | D3 | `DemoFaultsExtension.dead_scheduled_job` directly — **not** the live `Scheduler`, see below |
| an `ExclusiveAction` slot taken and never released | — | `DemoFaultsExtension.exclusive_action.held_slot()` directly — still not on the wire (`EPIC-007B` added the API, no collector reads it yet) |
| an `EnrolmentFlow` state machine driven through one illegal move | — | `DemoFaultsExtension.rejected_transition` (an `InvalidStateTransitionError`, not a `False` return — `REF-005`) **and**, with a console attached, `sagittarius-trace snapshot`'s `signals` section — the rejected transition renders in `danger` on the Signals screen |

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

## Why two of these still only reach a log line, not the console's wire format

`StateSnapshot` (`EPIC-007A`/`F`) has eight collected sections today —
lifecycle/events/container/tasks/thread_pools/bounded/config/signals. `EPIC-007F` gave the
dead-letter queue and the FSM's rejected transitions a real field (`signals.dead_letters`/
`signals.state_machines`) and a real screen. R1 and `ExclusiveAction.held_slot()` are the two
still without one: nothing in this repository has yet added a collector for either.
`DemoFaultsExtension` seeds both anyway, and logs what `RuntimeMonitor` sees at shutdown
(`DiagnosticsExtension(watch_runtime=True)`'s own pattern), because the seed is real
infrastructure work independent of when the matching panel ships — and because a demo that
only seeds what already has somewhere to be shown would silently shrink every time a future
milestone's scope was drafted.

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
