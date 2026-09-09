# EPIC-008D: Container restyled

- **Status**: ✅ Done
- **Category**: Tooling (`tools/state_console`)
- **Started Date**: 2026-09-09
- **Completed Date**: 2026-09-09

---

## 🎯 Summary & Objectives

Restyle the Container screen onto `reference/handoff.md` §7.4: sortable Registrations/Never-built
tables and an Open-scopes plate with real fault-threshold styling.

Per `EPIC-008`'s own milestone table, this is done when leak threshold styling is verified
against a live seeded-fault demo.

## 📐 Implementation Plan / Overview

- **The Open-scopes *table* (`scope · age · resolved in this scope`) is not built.**
  `ContainerState` carries only a count, not per-scope identity or age — building the real
  table means adding scope-creation tracking to `StdLibContainer`/`ScopeContext` itself, a
  bigger, more invasive change than exposing data a collector already has access to (this
  epic's own `EPIC-008B` §4 precedent for "extend the wire protocol"). Asked explicitly rather
  than assumed; scoped down to the plate only, which is all the stated Definition of Done needs.
- **Registrations / Never built** share one persistent `AppDataTable` (filtered by the active
  sub-tab), the same shape `EventsScreen.qml` already established so a sort survives both a
  snapshot refresh and a tab switch. Lifetime and Instance are plain-text `formatter`s
  ("instance built"/"never resolved"), not colour-tagged pills — no per-cell delegate exists in
  `AppDataTable`, the same limitation named for the third time this epic now.
- **A real, seeded leak, not a hand-set test fixture.** `examples/student_management`'s
  `DemoFaultsExtension` gained an eighth seed, `_seed_leaked_scopes()`: 30 real
  `container.create_scope()` contexts entered and never exited, comfortably past the handoff's
  own `>24` threshold — the same "one instance of each condition" reasoning already governing
  every other seed there, giving this subtask's own acceptance criterion something real to
  verify against instead of nothing.
- **A real "climbing since attach" comparison, not a guess.** `ContainerPresenter` records the
  open-scope count as it stood at the first snapshot after attach (reset on every fresh
  attach) and compares later readings against that baseline.
- **A design-review-caught bug in the note copy, fixed before it shipped:** the demo's leak is
  seeded once, during boot, before the console ever attaches — so the baseline the console
  observes is already 30, and the count never rises past it. The original two-note design
  (`reference/handoff.md`'s own "climbing"/"steady") would have shown "steady · opened and
  closed with each request" for a stuck-open leak — a specific, false claim that scopes were
  being closed. Caught by screenshot review, not a test (no assertion was wrong; the design
  itself had a real gap). Fixed with a third state: fault-but-not-climbing reads "elevated
  since attach · not decreasing" instead of either handoff-specified string.
- **A full-suite-only test failure found by the local CI gate, not by running this file
  alone:** the first version of `test_open_scopes_plate_turns_fault_above_the_threshold`
  asserted two `Theme` colours were different. In isolation that passed; under the full suite
  it failed, because `get_theme_bridge()`'s shared singleton only honours the *first* caller's
  palette in a process — an earlier test module (`test_app_rail.py`/`test_live_connection_band.py`)
  had already locked in a different one, and `Theme.danger`/`Theme.textPrimary` both resolved to
  the same placeholder black. Fixed by asserting on `openScopesFault` (the plain boolean the QML
  itself computes) instead of resolved colours — the colour binding is a one-line ternary
  already verified visually by this subtask's own screenshots.

## 🧪 Verification & Test Coverage

- `examples/student_management/tests/infrastructure/demo_faults/test_extension.py`: 1 new test
  for the leaked-scope seed, plus the existing "every seed produced something" test extended.
- `tests/tools/state_console/test_container_presenter.py` (4 new tests): the first snapshot
  after attach is never "climbing", a later rise past the baseline is, holding at or below the
  baseline is not, and a fresh attach resets the baseline (a stale one from a previous
  connection must not lie about a brand-new attach's first reading).
- `tests/tools/state_console/test_container_screen.py` (+3 tests, 5 total): sub-tab counts are
  real, the open-scopes plate turns fault above threshold (colour, count, and the
  "climbing"/"steady" note), and the third "elevated, not climbing" note case.
- Full local CI green.
- Screenshots offscreen against the real demo app: Registrations tab (13 real registrations,
  `_ReportService` correctly tagged "never resolved" — the demo's own C2 seed) and Open scopes
  tab (30, red fault styling, "elevated since attach · not decreasing").
