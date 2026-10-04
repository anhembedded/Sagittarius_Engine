# EPIC-008D — WorkbenchShell: the top-level window with the standard menu bar, a mode bar, View built from docks, Reset layout and a status bar

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** 🔵 Backlog
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W3)
**Depends on:** EPIC-008B, EPIC-008C

---

## 🎯 Summary & Objectives
`PresenterManager` is a bare `QStackedWidget` router; the shell, regions and navigation that `ui-architecture.md` §4 says the runtime owns do not exist, and `TASK-043` E3 (`NavigationService` with `source` and `can_leave`) waits on a consumer prototype that D2 removes.

### Acceptance criteria
- [ ] `WorkbenchShell(QMainWindow)` builds the menu bar in the Windows order File, Edit, View, the consumer's menus, Tools, Window, Help (MS uxguide `cmd-menus`), each with an access key; consumer actions land in their `menu_path`; File → Exit (Alt+F4 on Windows, `QKeySequence.Quit` elsewhere), Tools → Options and Help → About exist by default; inapplicable items are disabled, never hidden.
- [ ] The window remembers its size and position; `createPopupMenu()` on the toolbar area lists toolbars and docks.
- [ ] A mode bar (vertical `QToolBar`, `QActionGroup`, icons and tooltips, Ctrl+1…9) switches a stack of `RegionHost`s; the bar hides its text by default.
- [ ] View lists the current mode's dock toggles and toolbars and refreshes on mode change; Window → Reset layout calls `reset_perspective()` on the current mode.
- [ ] A status bar with permanent slots that modes contribute to.
- [ ] `NavigationService.navigate(mode_id, source=USER_INTENT|RESTORE)` asks the current mode's `can_leave()`; a refusal keeps the mode and the checked action in sync.
- [ ] The sample app `examples/student_management` runs on the shell.
- [ ] TASK-043 is updated: E3 delivered here; its harvest-first rule superseded for the workbench by ADR-003.

## 📐 Implementation Plan / Overview
Qt Creator's mode selector and per-mode `QMainWindow` (P5); the engine owns mechanism, the app owns which modes exist (TASK-043's split).

| File | Change |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/workbench/workbench_shell.py, mode_bar.py, view_menu.py, navigation_service.py, navigation_source.py` | New |
| `examples/student_management/` | Uses the shell |
| `Tasks/in_progress/TASK-043_*.md` | E3 and the decision updated |

## 🧪 Verification & Test Coverage
Unit: menus, mode switching, View refresh, can_leave refusal. Sample app smoke run. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.
