# EPIC-008F: Signals restyled

- **Status**: ✅ Done
- **Category**: Tooling (`tools/state_console`), Engine (`sagittarius_engine/extensions/state_console`, `sagittarius_engine/extensions/audit`)
- **Started Date**: 2026-09-09
- **Completed Date**: 2026-09-09

---

## 🎯 Summary & Objectives

Restyle the Signals screen onto `reference/handoff.md` §7.6: one blueprint card per dead
letter (not a table row), one plate per watched state machine (name, attempts/rejected
figures, a declared-states chip row, its own transition log), and three separate UI-thread
health plates instead of one combined line.

Per `EPIC-008`'s own milestone table, this is done when "the same real dead-letter/rejected-
transition demo `EPIC-007F` used" renders in the new visual language — this is the last of the
epic's six subtasks.

## 📐 Implementation Plan / Overview

- **A per-machine plate needs data no single wire field had.** The old screen's shared,
  cross-machine `AppDataTable` was replaceable with per-machine filtering alone, but three
  things the handoff's plate wants had no wire representation at all:
  - **"Attempts"**, distinct from `rejected_count`. `len(transitions)` would undercount once
    the transitions log truncates past its cap — the same reasoning `rejected_count`'s own
    docstring already gives for being first-class rather than derived. `_StateMachineWatcher`
    gained its own running `_attempted_count`, incremented on both an accepted and a rejected
    attempt; `StateMachineState.attempted_count` carries it.
  - **A declared-states chip row.** `BaseStateMachine[T: Enum]` is generic over exactly one
    state enum, so `type(machine.current_state)` already *is* the machine's complete,
    real declaration — nothing new needed tracking, just reading. `StateMachineState.
    declared_states` exposes it.
  - **A rejection reason.** `InvalidStateTransitionError` already carries a real, specific
    message at the exact point `_StateMachineWatcher._record_rejection` catches it —
    `StateMachineTransition.reason` exposes `str(exc)` rather than re-deriving something
    generic from the from/to the row already shows in its own columns.
  All three are the same "expose data already sitting right there" pattern as every other
  wire extension this epic has made (`EPIC-008B`'s `LifecycleState.modules`, `EPIC-008E`'s
  `error_type`/`stack`/`thread`/`jobs`), not new runtime instrumentation.
- **Dead-letter cards get a positional id and a real age, computed in the presenter, not the
  wire.** `dl-0`, `dl-1`, … — an honest ordinal label for referring to a card in a list, not a
  fabricated business identifier this engine has never assigned to a parked event.
  `agoSeconds` is `(snapshot.t - parked_at_ns) / 1e9`, both already documented to share the
  same monotonic clock.
- **`SignalsViewModel.stateMachines` restructured**: each entry now nests its own
  `transitions` (newest-first, matching the handoff's own log ordering — the wire's own
  `StateMachineState.transitions` stays newest-*last*, a plain append log), replacing the
  earlier flat, cross-machine `transitions` property this view model used to expose alongside
  it.
- **Not built: a hand-rolled dashed payload border, or "hatched" rejected transition rows.**
  QtQuick has no native dashed-border style; a segment-by-segment approximation would need to
  re-tile itself on every resize, which is not worth building for one block on one screen — a
  solid border reads as "this is a distinct block" just as clearly. "Hatched" rows have no
  analogue in `AppDataTable`'s existing `rowAccent` (a solid tint, already used by four screens
  this epic restyled) — the same "no per-cell delegate" gap named several times already in this
  epic, here applied to a border/fill *style* rather than a table cell.

## 🧪 Verification & Test Coverage

- `tests/extensions/state_console/test_state_machine_watcher.py` (+5 tests): `declared_states`
  is the complete enum, not just visited states; `attempted_count` includes both accepted and
  rejected attempts and survives the transitions cap; a rejected transition carries a real,
  specific reason; an accepted one carries none.
- `tests/tools/state_console/test_signals_presenter.py` (new, 5 tests): dead letters carry a
  positional id and a real age (including across multiple entries), a machine carries its real
  `attemptedCount`/`declaredStates`, its transitions are nested newest-first with a real age and
  reason, and absent signals leaves the view model untouched.
- `tests/tools/state_console/test_signals_screen.py` (+2 tests, 7 total): declared states render
  as a real chip row, and a machine with zero rejections shows a muted (not bold) "0 rejected"
  figure — updated the existing data-shape test for the new nested-transitions shape.
- Full `tests/tools/state_console/` + `tests/extensions/pyside_mvc/` + `tests/extensions/
  state_console/` + `tests/extensions/audit/` + demo-faults suite: 481 passed, 12 skipped, 0
  failed — no segfault this run.
- Full local CI green, read from the log file directly: 1520 passed, 23 skipped, 0 failed;
  architecture tests, packaging checks, and the import guard all passed.
- Screenshots offscreen against the real demo app: a real dead-letter card (`dl-0`,
  `demo.student_deleted`, real handler/error type/message/payload, "set aside 2s ago · after 1
  retries"), and the `EnrolmentFlow` machine plate (4 attempts, 1 rejected in red, all five
  declared states as chips with `ENROLLED` filled accent, and its own transition log with the
  real rejected row tinted and its real reason visible). A second screenshot, constructed
  directly (not through the demo, which never exercises either empty path), confirmed both
  empty states render their real explanatory copy rather than a blank table.
