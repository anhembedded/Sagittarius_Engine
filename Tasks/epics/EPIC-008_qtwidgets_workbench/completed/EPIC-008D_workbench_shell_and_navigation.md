# EPIC-008D — WorkbenchShell: the top-level window with the standard menu bar, a mode bar, View built from docks, Reset layout and a status bar

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** ✅ Completed
**Completed Date:** 2026-10-04
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W3)
**Depends on:** EPIC-008B, EPIC-008C

---

## 🎯 Summary & Objectives
`PresenterManager` is a bare `QStackedWidget` router; the shell, regions and navigation that `ui-architecture.md` §4 says the runtime owns do not exist, and `TASK-043` E3 (`NavigationService` with `source` and `can_leave`) waits on a consumer prototype that D2 removes.

### Acceptance criteria
- [x] `WorkbenchShell(QMainWindow)` builds the menu bar in the Windows order File, Edit, View, the consumer's menus, Tools, Window, Help (MS uxguide `cmd-menus`), each with an access key; consumer actions land in their `menu_path`; File → Exit (Alt+F4 on Windows, `QKeySequence.Quit` elsewhere), Tools → Options and Help → About exist by default; inapplicable items are disabled, never hidden.
- [x] The window remembers its size and position; `createPopupMenu()` on the toolbar area lists toolbars and docks.
- [x] A mode bar (vertical `QToolBar`, `QActionGroup`, icons and tooltips, Ctrl+1…9) switches a stack of `RegionHost`s; the bar hides its text by default.
- [x] View lists the current mode's dock toggles and toolbars and refreshes on mode change; Window → Reset layout calls `reset_perspective()` on the current mode.
- [x] A status bar with permanent slots that modes contribute to.
- [x] `NavigationService.navigate(mode_id, source=USER_INTENT|RESTORE)` asks the current mode's `can_leave()`; a refusal keeps the mode and the checked action in sync.
- [x] Only the active mode's actions are live: two modes may share a shortcut (`ActionRegistry` allows it), so the shell removes or disables the inactive mode's actions; a test proves a shared key reaches only the active mode (review of PR #224, finding 14).
- [x] The sample app `examples/student_management` runs on the shell.
- [x] TASK-043 is updated: E3 delivered here; its harvest-first rule superseded for the workbench by ADR-003.

## 📐 Implementation Plan / Overview
Qt Creator's mode selector and per-mode `QMainWindow` (P5); the engine owns mechanism, the app owns which modes exist (TASK-043's split).

| File | Change |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/workbench/workbench_shell.py, mode_bar.py, view_menu.py, navigation_service.py, navigation_source.py` | New |
| `examples/student_management/` | Uses the shell |
| `Tasks/in_progress/TASK-043_*.md` | E3 and the decision updated |

> The plan table's `mode_bar.py`, `view_menu.py` and `navigation_source.py` were folded into `workbench_shell.py`, `shell_menus.py` and `navigation_service.py`.

## 🧪 Verification & Test Coverage
Unit: menus, mode switching, View refresh, can_leave refusal. Sample app smoke run. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.

## Implementation notes
- `workbench/workbench_shell.py` (`WorkbenchShell`, `ShellMode`): the window, the left vertical mode bar (`QActionGroup`, icons only, Ctrl+1…9 through the registry, so the keys are checked like every other), a `QStackedWidget` of `RegionHost`s, the standard commands contributed to the consumer's `ActionRegistry` (File → E&xit on `StandardKey.Quit`, Tools → &Options on `StandardKey.Preferences`, Window → &Reset layout, Help → &About, View → Stat&us bar and View → T&oolbars → &Mode bar), per-mode status-bar widgets, the Output pane docked at the bottom, geometry/state/last mode through `ui_state`, `finish_setup()` (menus, default perspectives, unbound report). A close is asked of the showing mode's `can_leave` too.
- `shell_menus.py` (`MenuBarBuilder`, `menu_order`): Windows order; each menu filled on `aboutToShow` for the showing mode; the View menu appends the mode's dock toggles and Toolbars its toolbar toggles, Window the Output toggle, all given free access keys by `access_key_assignment.assign_access_keys`; an empty top-level menu is disabled.
- `navigation_service.py` (`NavigationService`, `NavigationSource`): `navigate(mode_id, source)` asks `can_leave(source)`; `navigation_refused` keeps the mode bar's check on the kept mode.
- Only the showing mode's actions are added to the window (`ActionRegistry.scoped_actions()`), so a key two modes share reaches only the showing one. Mutation-verified: adding every action fails the shared-key test; dropping the re-check fails the refusal test.
- The sample app runs on the shell (`examples/student_management/presentation/workbench/sample_shell.py`, `gui.py`): one mode, one Options page, one Output channel; smoke-run shows the shell with File, Edit, View, Tools, Window, Help and exits 0.
- Found by the registry while writing the tests: a mode named "B&ots" collides with the shell's "T&oolbars" in View. The consumer's approved View menu has exactly that pair; it is fixed in the consumer's P4.
