# EPIC-007F — Signals: the dead-letter queue and state machines

**Epic:** [EPIC-007 — Runtime State Console](../README.md)
**Status:** ✅ Completed 2026-08-27 (criteria 1-5 fully; criterion 6 partial — see Outcome)
**Category:** Observability / Diagnostics
**Priority:** P2
**Depends on:** EPIC-007C, EPIC-007D, EPIC-007E

---

## 1. Why these two, and why last

Every other milestone renders state that *something* could already reach — a report, a CLI,
a test. These two render state that **the engine holds and nothing whatsoever surfaces**, and
they are the highest value-per-line in the epic for that reason.

They come last because each needs a live app with the condition seeded (`EPIC-007D`) and a
screen to put it on (`EPIC-007E`). Neither adds instrumentation: both read APIs that exist.

## 2. The dead-letter queue

`ResilientEventBus` retries a failing handler `max_retries` times and then parks the event:

```python
def get_dlq(self) -> list[tuple[str, Any, Callable, Exception]]:
def reprocess(self) -> None:
```

**`grep` across the repository finds both called from tests and nowhere else.** So an event
that exhausted every retry is sitting in memory right now in any app using this bus: nothing
logs it at that point, nothing reads it, and it is gone when the process exits. There is
already a public method to replay it and no way to know you should.

### 2.1 What the panel shows

Per parked event: name, the handler that gave up, the exception type and message, the
payload, retries spent, and when. Grouped by event name, newest first.

### 2.2 Reprocess is rendered, disabled, and not wired

The control appears — a queue you can see and not act on is half a feature, and hiding the
control hides the fact that a remedy exists. It is **disabled**, with the reason stated on
screen: write actions are off.

`reprocess()` re-emits into a live application from a socket. That is a write path with a
real blast radius, and `EPIC-007` §6 puts every write action behind **ADR-003**. Wiring it
here because the method happens to be one call away is exactly the shortcut
`design-discipline.md` exists to refuse.

## 3. State machines

`BaseStateMachine.add_global_callback(cb)` is a **public, existing** extension point taking
`(old_state, new_state)`. One callback per machine yields the current state, the transition
history, and the count per state — with no change to the FSM implementation at all.

### 3.1 The finding that justifies the panel

**Corrected `REF-005`:** this section originally claimed `transition_to()` "returns `False`
on an illegal transition and raises nothing." That was never true of `BaseStateMachine` —
`transition_to()`/`dispatch()` both `logger.error(...)` and raise
`InvalidStateTransitionError` (`state_machine.py`, `declarative_state_machine.py`). The panel
this section justifies is still worth building, on a narrower and accurate ground: a raised
exception is visible only to a caller that catches it and does something with it, and nothing
in the engine does that today. A rejected transition inside a handler the event bus already
isolates (`handler_reporting.py`) is caught, logged once, and otherwise lost — the same shape
as `EPIC-006`'s A2 typo, not because the FSM stays silent, but because everything downstream
of it currently is.

The transition log therefore renders rejected attempts **in `danger`, inline with the
accepted ones**, and the count of rejections is a first-class number on the panel. If this
milestone ships only one thing, it is this row.

### 3.2 Registration

A machine is not discoverable — there is no registry of `BaseStateMachine` instances. So the
application opts in, one line per machine, at the point it constructs one:

```python
console.watch_state_machine("EnrolmentFlow", flow)
```

Explicit rather than a `__init_subclass__` registry, and for a measured reason:
`EPIC-006D` found that a subclass registry would have discovered **0 of the demo app's 7
handlers**, because the marker was duck-typed. Guessing at discovery has already cost this
repository a rewrite; an application naming its own machines cannot be wrong.

## 4. Also on this screen

**UI-thread health**, for consumers using `pyside_mvc`: `UIWatchdog` already detects main
loop freezes (`_handle_freeze(elapsed)`) and `thread_affinity` / `safe_ui_action` already
guard cross-thread UI mutation. Both currently only log. Surfacing the counts and the worst
elapsed is the cheapest red flag in the epic for a desktop app.

## 5. How to run it

```powershell
# the seeded app plus the console; open the Signals screen
.\scripts\run-console.ps1 -Demo
```

`EPIC-007D`'s `-DemoFaults` seeds both conditions: a handler on `student.deleted` that
raises until its retries are spent, and an `EnrolmentFlow` driven through one illegal move.

Text path, no display server:

```bash
.venv/bin/sagittarius-trace snapshot ws://127.0.0.1:8781 --watch 1s
# the `signals` section carries both
```

Tests:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/tools/state_console/test_signals_screen.py -v
.venv/bin/python -m pytest tests/extensions/state_console/test_dlq_section.py -v
```

## 6. Done when

1. An event that exhausted its retries appears on screen with its handler, exception and
   payload — **the first time anything in this repository other than a test has read
   `get_dlq()`**.
2. The reprocess control is visible, disabled, and states why.
3. A rejected transition appears in the transition log, marked as rejected, and is counted.
4. A test drives a machine through an illegal transition and asserts the console reports it —
   the behaviour is `transition_to()` raising `InvalidStateTransitionError` (`REF-005`), so
   the panel's global callback fires only on a *successful* transition and the rejected one
   has to be observed by catching the exception at the call site, not by reading a return
   value; the test asserts on the console's output, not on the FSM.
5. Watching a machine costs nothing measurable when the console is detached: the callback is
   registered only while a client is attached, or it is a plain append the collector reads.
6. UI-thread freeze and off-thread-mutation counts appear when the observed app uses
   `pyside_mvc`, and the section is **absent rather than zeroed** when it does not — a zero
   there means "no violations", and showing it for a headless app would be a lie.

---

# Outcome (2026-08-27)

## What shipped

| Piece | What it is |
| :--- | :--- |
| `sagittarius_engine/infrastructure/event_bus/resilient_event_bus.py` | `get_dlq()` now returns a 5-tuple, `parked_at_ns` appended (`time.perf_counter_ns()`, same clock as every other timestamp on the wire) — additive; every existing reader indexed at most `[3]`, one 4-tuple unpack in `examples/student_management` fixed |
| `sagittarius_engine/extensions/audit/contracts.py` | `DeadLetterEntry`, `StateMachineTransition`, `StateMachineState`, `UiThreadHealth`, `SignalsState`; `StateSnapshot.signals: SignalsState \| None` — additive, no `PROTOCOL_VERSION` bump (the same category of change as every earlier collector's own field additions) |
| `sagittarius_engine/extensions/state_console/state_machine_watcher.py` | `_StateMachineWatcher` — installs on `add_global_callback()` for accepted transitions, wraps the instance's own `transition_to`/`dispatch` to catch `InvalidStateTransitionError` for rejected ones (re-raised unchanged), bounded 200-entry log |
| `sagittarius_engine/extensions/state_console/collectors/signals.py` | `SignalsCollector` — assembles what the watchers already recorded; holds live references to `StateConsoleExtension`'s own containers so a `watch_*()` call made after collector construction is still visible (a real ordering this repo's `when_ready()` callbacks produce — see the extension's own comment) |
| `sagittarius_engine/extensions/state_console/extension.py` | `watch_dlq(bus)`, `watch_state_machine(name, machine)`, `watch_ui_thread_health(source)` — three explicit opt-ins, no discovery, matching §3.2's own reasoning against a subclass registry |
| `sagittarius_engine/extensions/pyside_mvc/safety/ui_watchdog.py` | `UIWatchdog.freeze_count`/`worst_freeze_elapsed_sec`, updated in the real `_handle_freeze()` path |
| `sagittarius_engine/extensions/pyside_mvc/safety/thread_affinity.py` | Process-wide `get_off_thread_mutation_count()`, incremented in `@ui_mutator`'s cross-thread branch regardless of dev/production mode |
| `sagittarius_engine/extensions/audit/cli.py` | `_format_snapshot()` renders `dead letters`/`state machines`/`ui thread` sections — `sagittarius-trace snapshot`'s own text output, §5's "the `signals` section carries both" |
| `examples/student_management/infrastructure/demo_faults/extension.py` + `console.py` | `DemoFaultsExtension(console=...)` — when a console is attached, `watch_dlq()`/`watch_state_machine()` are called *before* the fault is seeded, so the demo's existing dead letter and rejected transition reach a real snapshot |
| `tools/state_console/presentation/signals/` | Real rendering: dead-letter table, state-machine transition log (rejected rows in `danger`), the reprocess control visible-and-disabled with its reason on screen, UI-thread health card only when watched |
| `sagittarius_engine/extensions/pyside_mvc/Sagittarius/UI/AppDataTable/AppDataTable.qml` | New `rowAccent` property — `(rowData) => color \| null`, a low-opacity overlay so a selected/hovered row still reads as selected/hovered first. `null` by default; every existing consumer (Roster, Gallery, Overview, Events, Container, Tasks) is unaffected |

## A bug found and fixed as part of this work

Fixing `_format_snapshot()`'s mypy error surfaced a real variable-name collision risk in the same function (`event` reused for two different types across two loops) — caught by mypy before it shipped, not found empirically; renamed to `via`.

## Criterion-by-criterion

| # | Status |
| :--- | :--- |
| 1 | Met — `test_a_dead_letter_and_a_rejected_transition_appear_in_a_real_snapshot` (real `TraceServer`, real client, real wire) and `test_with_a_console_attached_the_dlq_and_fsm_reach_a_real_snapshot` (the demo's own seeds); manually verified via `sagittarius-trace snapshot` and the GUI screenshot below |
| 2 | Met — the Signals screen always shows the "Reprocess" control, `enabled: false`, with `viewModel.reprocessDisabledReason` (naming `EPIC-007` §6 / ADR-003) printed beside it, screenshotted |
| 3 | Met — rejected transitions render inline with accepted ones, flagged `[REJECTED]`/`REJECTED` in both the CLI and QML renderings, in `Theme.danger` in the GUI (`rowAccent`), and `rejected_count` is its own field, not derived by filtering client-side |
| 4 | Met — `test_a_rejected_transition_is_recorded_and_still_raises` drives `EnrolmentFlow`-shaped machines through an illegal move and asserts on `_StateMachineWatcher.collect()`'s output, not on the FSM; `test_the_apps_own_exception_handling_is_unaffected` proves the watcher does not change what the caller sees |
| 5 | Met for state machines — `test_watching_costs_nothing_measurable_while_detached` measures a watched vs. unwatched machine driven 5,000 times each. Trivially true for the DLQ (`watch_dlq()` is one list append; the cost of `get_dlq()` was already paid only at collection time, watched or not) |
| 6 | **Partial.** The counters are real (`UIWatchdog.freeze_count`/`worst_freeze_elapsed_sec` from a genuine background-thread freeze detector, `get_off_thread_mutation_count()` from `@ui_mutator`'s real cross-thread branch) and unit-tested with real threads/timing; `watch_ui_thread_health()`, `UiThreadHealth`, and the QML section (`visible: viewModel.hasUiThreadHealth`, absent-not-zeroed, unit-tested) are all real and wired. **Not done**: no existing example app runs a GUI with `StateConsoleExtension` attached — `examples/student_management/gui.py` has no console/`-Console` mode, and `console.py` (the one entry point that does attach a console) is headless with no `pyside_mvc`/Qt objects to watch at all. So this criterion's live demo — a real GUI app's freeze/mutation counts flowing through a real socket to a real screen — was not run; only the data plumbing between `watch_ui_thread_health()` and the rendered (or absent) section was. Wiring `gui.py` for `-Console` is a distinct, self-contained follow-up (`docs/ui_extension_lifecycle.md`'s ordering rule applies there too), not folded in here. |

## Verified

| Gate | Result |
| :--- | :--- |
| `pytest tests/extensions/audit/ tests/extensions/state_console/ tests/extensions/pyside_mvc/ tests/tools/state_console/ examples/student_management/tests/` | all green (new: 4 contract round-trip tests + 2 `DeadLetterEntry`/`UiThreadHealth` tests, 9 `state_console` end-to-end tests (2 new), 8 `SignalsCollector` tests, 7 `_StateMachineWatcher` tests, 3 `UIWatchdog` tests, 4 `thread_affinity` off-thread-mutation tests, 4 `_format_snapshot` rendering tests, 4 Signals-screen QML tests, 1 demo-wiring end-to-end test) |
| `pytest tests/ examples/student_management/tests/ tools/` (fork/Qt test excluded, verified separately at 4/4) | **1378 passed**, 22 skipped, repeated 3x for confidence after one run surfaced an unrelated, pre-existing, self-documented-flaky test (`test_ui_state_coordinator.py::test_marking_again_restarts_the_window_...`, timing-sensitive under load per its own docstring; 3/3 green in isolation, 2/3 green in the full run) |
| `ruff check`/`ruff format --check` (whole repo) | Clean on every file this work touched; 28 pre-existing errors elsewhere (a cross-repo import script) confirmed unchanged via `git stash` |
| `mypy sagittarius_engine tests examples tools` | Clean, 487 source files |
| `scripts/verify_wheel_importable.py` | PASS — 212 shipped modules (up from 210), all 3 console scripts resolve |
| `sagittarius-doctor examples.student_management.doctor_target:build --strict` | 0 errors, 0 warnings, exit 0 — unaffected, since `DemoFaultsExtension`'s seeds are opt-in and outside this factory's path (`EPIC-007D` §3) |
| `console.py --demo-faults` + `sagittarius-trace snapshot` | Real dead letter (`demo.student_deleted`: `KeyError`) and real state machine (`EnrolmentFlow`: 4 transitions, 1 rejected) both printed by the text CLI |
| Full GUI shell against the same live server, screenshotted | Signals screen shows the dead-letter table, the disabled Reprocess control with its reason, and the transition log with the rejected `ENROLLED -> SUBMITTED` row highlighted in `danger` — UI-thread health card correctly absent (never watched in this scenario) |

## Run it

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/tools/state_console/test_signals_screen.py tests/extensions/state_console/ tests/extensions/audit/test_cli.py -v
```

```bash
PYTHONPATH=. QT_QPA_PLATFORM=offscreen .venv/bin/python examples/student_management/console.py --port 8781 --demo-faults &
.venv/bin/python -c "from sagittarius_engine.extensions.audit.cli import main; main(['snapshot', 'ws://127.0.0.1:8781'])"
```
