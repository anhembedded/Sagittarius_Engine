# TASK-018: Record `BaseCard` Sub-Type Candidates (No Code Yet)

- **Status**: ✅ Completed
- **Category**: UI Engine / Widget Kit — `EPIC-001C` follow-up
- **Started Date**: 2026-08-23
- **Completed Date**: 2026-08-23

---

## 🎯 Summary & Objectives

During design discussion on `EPIC-001C`'s Widget Kit, four plausible `BaseCard` sub-base
categories came up (`ActionCard`, `FormCard`, `StreamCard`, `TableCard`) — each describing a
different *meaning* of "disabled" for a card (block an internal action, lock editable input,
pause a live feed, lock row interaction). None has two real, shipped `BaseCard` descendants
needing the identical override contract yet — checked against all 3 real descendants today
(`LogPanel`, `TimeRangeCard`, `AppDataTable`); only `TimeRangeCard` overrides anything at all.

Per `ui-architecture.md` §1.2's operational test and the "≥2 real instances before
abstracting" discipline already applied throughout `EPIC-001C` (e.g. why the kit stayed flat
instead of grouping into `cards/`/`controls/`/`overlays/`), creating these as real QML types
now would be exactly the premature-taxonomy mistake that discipline exists to prevent.

**This task is deliberately not "create the sub-bases."** It is the thing that *is* correct
to do now: make the candidate categories visible to whoever (human or AI) next adds a
`BaseCard` descendant, so the second real instance of a pattern gets recognized as such
instead of the reasoning being rediscovered from scratch or a fifth ad hoc category invented.

## 📐 Implementation Plan / Overview

Created 4 placeholder directories under `Sagittarius/UI/`, matching the real per-component
directory convention (`EPIC-001C`'s directory-per-component reorg) so the pattern is
immediately recognizable — but each contains only a `NOTES.md`, no `.qml` file, and none are
registered in `qmldir`:

- `Sagittarius/UI/ActionCard/NOTES.md` — 0/2 candidates. Purely hypothetical; no real card
  currently wires an internal action's enabled state to the card's own active/inactive state.
- `Sagittarius/UI/FormCard/NOTES.md` — 1/2, strongest candidate. `TimeRangeCard.qml` already
  implements the exact hypothesised contract (dim + force-read-only together) today.
- `Sagittarius/UI/StreamCard/NOTES.md` — 1/2, weaker claim. `LogPanel.qml` is the
  architecturally obvious fit but has not implemented any `setDisabled` override — the
  hypothesis rests on `BaseCard.qml`'s own docstring example ("pause a live update"), not a
  shipped need.
- `Sagittarius/UI/TableCard/NOTES.md` — 1/2, weaker claim, same caveat as `StreamCard`:
  `AppDataTable.qml` is the obvious fit, no override implemented yet.

Each `NOTES.md` states: the hypothesis, the real evidence (or explicit lack of it), and the
exact promotion rule (a second real instance needing the identical contract — not "this looks
useful" — triggers creating the real `.qml` file and `qmldir` entry).

**Deliberately kept invisible to the kit guards**: no `.qml`, no `.py`, so
`tokens/qml_literal_guard.py`, `kit/raw_primitive_guard.py`, and `kit/rectangle_card_guard.py`
all correctly report zero findings for these directories — confirmed, not assumed. A
placeholder must not be mistaken for a real, guard-covered component.

## 🧪 Verification & Test Coverage

Documentation-only task; no new automated tests. Verified instead:

- [x] `find_literal_colors()` against the whole extension: 0 findings (unchanged).
- [x] `find_raw_primitives()` against the whole extension: 6 findings (unchanged — the same 6
      pre-existing, already-documented ones inside `DateTimePicker`/`StatefulButton`/`StyledCheck`).
- [x] `Sagittarius/UI/qmldir` untouched — none of the 4 candidates registered.
- [x] Gallery re-rendered successfully (proves the QML module import path is unaffected by
      the new, non-`.qml`-containing sibling directories).
- [x] Full test suite: 514 passed, 7 skipped (unchanged from before this task — no test
      references these directories, by design).
