# EPIC-008: `SectionSubTabs` extracted (post-C/D design review)

- **Status**: ✅ Done
- **Category**: Tooling (`sagittarius_engine/extensions/pyside_mvc`, `tools/state_console`)
- **Started Date**: 2026-09-09
- **Completed Date**: 2026-09-09

---

## 🎯 Summary & Objectives

A self-review pass after subtask D found that Overview (§4), Events & wiring (§C), and
Container (§D) had each independently built the identical sub-tab row `reference/handoff.md`
§6 specifies ("sub-tab row below with a 1px bottom rule, active tab: accent 2px underline +
accent-900 text, inactive 50% ink, each tab shows a count in mono at 60% opacity") — three
copies of the same `RowLayout` of `Text` items, `MouseArea`s, and a divider `Rectangle`, each
with its own screen-prefixed `objectName`s (`overviewTabStatus`, `eventsTabAll`,
`containerTabRegistrations`, …).

This repo's own two-consumer promotion rule (`ActionCard/NOTES.md`) — previously invoked to
**decline** promoting the connect-flow primitives in `EPIC-008A` §5 (only one consumer) — is
satisfied for real this time: three independent screens, not one. Extracted into a new kit
component, `SectionSubTabs`, and migrated all three consumers onto it.

## 📐 Implementation Plan / Overview

- **`SectionSubTabs.qml`** (new,
  `sagittarius_engine/extensions/pyside_mvc/Sagittarius/UI/SectionSubTabs/`): tiered per
  `ui-architecture.md` §1.2 the same way every other kit component here is — the active-tab
  underline/colour mechanics are tier 1 (inside the component); which tabs exist, their labels
  and counts are tier 2 (`tabs`, the same schema-driven array shape `AppRail.sections` and
  `AppDataTable.columns` already use). What a tab *means* is entirely tier 3 — the component has
  no idea what "undeclared" or "never built" means.
- **`count` is optional per tab, not defaulted to 0.** `reference/handoff.md` §7.1 itself reads
  "Status · Modules (12)" — Status carries no parenthetical at all, Modules does. This is
  deliberately different from `AppRail.badgeCount`'s "0 or absent means no badge": here a
  *present* `count: 0` still renders ("Undeclared (0)" is real information — nothing wrong yet).
  It is the key's absence, not its value, that means "this tab has no count". Implemented as a
  `visible` binding on the count `Text` (`AppRail`'s own `railRowBadge` establishes that
  `visible: false` children are excluded from `RowLayout` sizing in this codebase — reused
  directly rather than reinventing it with a `Loader`).
- **Migrated all three real consumers**, each losing its own inline `RowLayout`/divider block:
  - `OverviewScreen.qml`: `{ id: "status", label: "Status" }` (no `count` key — see above),
    `{ id: "modules", label: "Modules", count: … }`.
  - `EventsScreen.qml`: `all`/`undeclared`, both counted (unchanged from `EPIC-008C`'s own
    tabs).
  - `ContainerScreen.qml`: `registrations`/`neverBuilt`/`openScopes`, all counted (unchanged from
    `EPIC-008D`'s own tabs).
- **New objectNames, old ones retired.** `subTab_<id>` on the row item (`AppRail._selectRow`'s
  own `railRow_<id>` naming convention, generalized), with `subTabLabel`/`subTabCount` as its two
  children — replacing the old combined single-`Text` `"All (25)"`-style objectNames
  (`eventsTabAll`, `overviewTabModules`, `containerTabRegistrations`, …) everywhere they existed.
- **Gallery entry** added (`Gallery.qml`, right after "App rail") showing three tabs, one with a
  `count: 0` — verified with no new QML warnings.

## 🧪 Verification & Test Coverage

- `tests/extensions/pyside_mvc/test_section_sub_tabs.py` (new, 4 tests): one tab per entry with
  correct label/count text, active vs. inactive colour, changing `activeTabId` moves the
  highlight, and `_selectTab(id)` emits `tabSelected` — same `_standalone_qml_theme.py` +
  `QMetaObject.invokeMethod(..., Q_ARG("QVariant", …))` pattern `AppRail`'s own tests established
  for testing click-only QML interactions.
- `test_events_screen.py`, `test_overview_screen.py`, `test_container_screen.py`: updated for the
  new `subTab_<id>`/`subTabLabel`/`subTabCount` shape in place of the old combined-text
  objectNames — same one-`_collect_all()`-walk discipline each file already used.
- Full `tests/tools/state_console/` + `tests/extensions/pyside_mvc/` suite: 295 passed. mypy and
  ruff clean over the touched scope.
- A segfault reproduced identically when running this combined suite both with and without this
  change present (confirmed by stashing the diff and re-running against the pre-change commit,
  `9885ac0`) — a pre-existing, load-dependent flake in background scheduler/async-runtime
  threads, unrelated to this change. A clean re-run came back fully green (295 passed).
- Full local CI (`ci-local.ps1 -RunPackagingChecks`) green, read from the log file directly:
  1492 passed, 23 skipped, 0 failed; architecture tests, packaging checks, and the import guard
  all passed.
- Screenshots offscreen against the real demo app, re-taken after migration: Overview
  (Status/Modules, Modules showing "5" in mono), Events (All 25 / Undeclared 2, WIRING BUG banner
  and row tint intact), Container (Registrations 13 / Never built 1 / Open scopes 30, fault
  styling and note text intact) — all render identically to before the migration, confirming the
  extraction changed no visible behavior.
