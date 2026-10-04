# EPIC-008B — A mode host takes actions on its toolbars, exposes its docks to a View menu and keeps a named perspective

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** 🔵 Backlog
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W1)
**Depends on:** EPIC-008A

---

## 🎯 Summary & Objectives
`RegionHost` adds toolbar content with `addWidget` and pins toolbars (`region_host.py:136-139,210,223`), keeps docks in a private `_docks` (:107) so no View menu can list them, and saves one unnamed blob per host with `PERSPECTIVE_VERSION = 1` (:158-180), which the consumer never calls.

### Acceptance criteria
- [ ] `place_action(place, action)` adds a `QAction` to a toolbar region; `place_widget` on a toolbar region is refused unless the widget is the toolbar's own widget for an action (a combo box or search field wrapped in a `QWidgetAction`).
- [ ] Toolbars are movable and can be hidden; their objectNames are stable for `saveState`.
- [ ] `dock_toggle_actions()` returns each dock's `toggleViewAction()` in contribution order; `default_perspective()` captures the layout as built.
- [ ] `PerspectiveStore` (an `IStateContributor` of `ui_state`) saves and restores each host's perspective under `perspective::<surface_id>` with the host's layout version; a mismatch restores the default and logs once; `reset_perspective()` restores the default.
- [ ] Tests: actions on toolbars, refusal of a bare widget, toggle actions list every dock, save → new host → restore round-trip, version mismatch falls back.

## 📐 Implementation Plan / Overview
Qt's own `QMainWindow` contract (actions on toolbars, `toggleViewAction`, `saveState(version)`) persisted through the engine's existing `ui_state` (P5: apply before you invent).

| File | Change |
| :--- | :--- |
| `pyside_mvc/runtime/region_host.py` | Actions, toggles, default perspective |
| `sagittarius_engine/extensions/pyside_mvc/workbench/perspective_store.py` | New |

## 🧪 Verification & Test Coverage
Unit tests mirroring the package (`tests/extensions/pyside_mvc/workbench/`), `qtbot`, no sleeps; each guard mutation-verified. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.
