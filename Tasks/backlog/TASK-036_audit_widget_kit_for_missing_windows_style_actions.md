# TASK-036: Audit every widget-kit card for missing Windows-Explorer-style utility actions

## Description

This session, `AppDataTable` (`sagittarius_engine/extensions/pyside_mvc/Sagittarius/UI/AppDataTable/`)
turned out to be missing common table actions a Windows-Explorer-style list view is expected to
have: click-to-sort columns and click-to-select rows. Both were added to the base component (not
the one screen that surfaced the gap), since every consumer benefits with zero per-screen changes
— see the commit adding `sortKey`/`sortAscending`/`currentIndex`/`rowClicked`/`rowDoubleClicked`
to `AppDataTable.qml`.

The user asked for the same kind of review across the **rest** of the widget kit: check every
card for missing common/utility actions of this kind, and add whichever are common enough to the
base component (not per-screen), the same way `AppDataTable` was just handled.

## Survey done so far (starting point, not a final verdict)

Read every component in `Sagittarius/UI/` on 2026-08-23 to scope this task accurately rather than
leave it as a blind "review everything":

- **`AppDataTable`** — done this session (sort, select, hover). Further candidates not done:
  keyboard navigation (arrow keys + Enter to select), multi-select, column resize, right-click
  context menu. Likely lower priority than what shipped — decide case by case.
- **`LogPanel`** — already has Copy (whole-log to clipboard), Clear, per-line text
  selection/copy (`TextEdit`, not `Text`), and auto-scroll-while-at-bottom. Candidate gaps: a
  level filter (show only errors/warnings), a search/filter box, pause-auto-scroll-while-reading
  (partially covered by the "only scroll if already at bottom" behavior, but no explicit pause
  control), export-to-file.
- **`AppModal`** — already has `Popup.CloseOnEscape | Popup.CloseOnPressOutside` and an explicit
  close (✕) button. Reasonably complete; no obvious common gap found on this pass.
- **`TimeRangeCard`** — has the custom-range toggle and two `DateTimePicker`s, but no "Clear" /
  "Reset" action to blank the range without manually clearing both fields, and no quick-range
  shortcuts (e.g. "Today", "Last 7 days") that a Windows-style date-range control commonly offers.
- **`DateTimePicker`**'s calendar popup — has prev/next month navigation and an "Apply" button,
  but no "Today"/"Now" quick-jump and no "Clear" action.
- **`BaseCard`** — `compact` is driven by the consumer, by design (ui-architecture.md §1.2 tier
  3) — not clearly a per-card action to add.
- **`StatefulButton`**, **`StyledCheck`**, **`FieldBackground`** — primitive controls, not
  containers; "utility actions" as a category doesn't obviously apply to any of the three on this
  pass, but worth a second look rather than assuming.

## Requirements

1. Re-verify the survey above against the current QML source (it may have drifted since
   2026-08-23) before acting on it.
2. For each candidate gap: decide whether it's common enough to belong in the base component
   (matching the reasoning that justified `AppDataTable`'s sort/select — every consumer should
   get it for free) versus something narrow enough to leave to individual screens.
3. Implement whichever are decided common, in the base component, with the same reuse-existing-
   tokens discipline `AppDataTable`'s fix followed (`Theme.stateActiveTint`, `Theme.stateHoverBg`,
   etc. — check `tokens/state_tokens.py`'s existing vocabulary before inventing new tokens).
4. Add regression tests for whatever ships, following `tests/extensions/pyside_mvc/test_widget_kit_gallery.py`'s
   existing pattern (property-level assertions via `.property()`/`.setProperty()` against a probe
   fixture, not simulated mouse input — no precedent for that in this test suite).
5. Verify against both the Gallery (`Sagittarius/UI/Gallery/Gallery.qml`) and
   `examples/student_management`'s real usage, the same way `AppDataTable`'s fix was verified with
   an actual screenshot, not just passing tests.

## Priority

P2 — not a defect, but a real, user-requested UX completeness gap across a shared component
library multiple consumers depend on.

## Category

UI / Widget Kit (`pyside_mvc`)

## Related

- [TASK-035](TASK-035_appdatatable_columns_have_no_horizontal_gap.md) — a different, cosmetic
  `AppDataTable` gap found in the same session, filed separately since it's a rendering defect,
  not a missing action.
- This session's `AppDataTable` sort/select commit is the precedent and pattern to follow for
  whichever other components get action additions from this audit.
