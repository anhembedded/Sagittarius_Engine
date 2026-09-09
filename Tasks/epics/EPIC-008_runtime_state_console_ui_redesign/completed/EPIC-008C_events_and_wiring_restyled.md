# EPIC-008C: Events & wiring restyled

- **Status**: ✅ Done
- **Category**: Tooling (`tools/state_console`)
- **Started Date**: 2026-09-09
- **Completed Date**: 2026-09-09

---

## 🎯 Summary & Objectives

Restyle the Events & wiring screen onto `reference/handoff.md` §7.3: sortable columns,
undeclared-event rows visually unmissable, a `WIRING BUG` banner naming exactly which
subscriptions are dead.

Per `EPIC-008`'s own milestone table, this is done when sort persists across a snapshot
refresh and undeclared rows are visually unmissable.

## 📐 Implementation Plan / Overview

- **Sub-tabs: All / Undeclared only, not the four `reference/handoff.md` §7 names.**
  `EventCollector`'s own docstring says `emits`/`failures` are always `0` — nothing in this
  engine counts them per event yet (a documented `RuntimeMonitor` gap, not something this
  subtask introduces or needs to close: neither this screen's stated acceptance criteria touch
  those two fields). Building "With failures"/"Never emitted" tabs against data that can never
  vary would be decoration, not information — named here rather than silently shipped as
  always-degenerate tabs.
- **Sorting is free.** `AppDataTable` already has click-to-sort with `sortKey`/`sortAscending`
  living on the one persistent table instance; a `SnapshotReceived` only reassigns its `model`
  property, which doesn't touch those two, so a sort survives both a refresh and a tab switch
  with no code written for it here.
- **Undeclared rows tinted via `rowAccent`** (already-shipped from `EPIC-007F`, not new) rather
  than per-cell colour — same reasoning as `EPIC-008B` §4's worker-pools table and Modules
  table: `AppDataTable` cells have no per-cell delegate, and adding one for a single consumer
  would repeat a mistake this epic has now avoided three times.
- **`WIRING BUG` banner**, verbatim copy from `reference/handoff.md` §7.3, naming every
  undeclared name in the current snapshot.
- **A real "did you mean `<near>`?" suggestion**, not a static hint: `EventsPresenter` runs
  `difflib.get_close_matches()` (stdlib, no new dependency) against the snapshot's own declared
  names — verified against a real typo the demo app seeds (`demo.roster_syncd` correctly
  suggests `demo.roster_synced`).
- **The diagnostic detail line reuses `AppDataTable`'s existing row-expansion mechanism**
  (`expandedDelegate`/`expandPredicate`, shipped in `EPIC-008A` for Tasks & threads' own future
  use) rather than a permanently-visible second line under every undeclared row — an
  interaction difference from the handoff's static two-line row, chosen because the mechanism
  already exists and a permanently variable row height inside a fixed-row-height table is a
  larger, riskier change for the same information.
- **`BUG-013` reproduced and fixed again**: the original screen's own comment already named
  this (a right-aligned column immediately followed by a left-aligned one fuses their header
  text and values into one string) for the `registered` column; adding a `declaration` column
  after the numeric block reintroduced it (caught by screenshot review, not a test — this class
  of bug has no text assertion that would catch a rendering fusion). Fixed by placing
  `declaration` before the right-aligned block, matching the original's own ordering fix.

No wire or collector changes needed this time — `EventState` already carries every field this
restyle uses (`module`, `handlers`, `registered`, `emits`, `failures`).

## 🧪 Verification & Test Coverage

- `tests/tools/state_console/test_events_presenter.py` (4 new tests): declared rows get no
  near-match suggestion, undeclared rows carry their real handler names, a genuine near-match
  is found among declared names, and an undeclared name with nothing similar gets no
  suggestion (not a wrong one).
- `tests/tools/state_console/test_events_screen.py` (+2 tests, 4 total): the `WIRING BUG`
  banner's visibility tracks whether anything is actually undeclared, and the two sub-tabs
  show real counts.
- Full local CI green.
- Screenshots offscreen against the real demo app with seeded faults: All tab (25 events, no
  column fusion), Undeclared tab (2 real undeclared names, tinted, filtered), and an expanded
  undeclared row showing the real subscribing handler and the real near-match suggestion for
  the demo's actual seeded typo.
