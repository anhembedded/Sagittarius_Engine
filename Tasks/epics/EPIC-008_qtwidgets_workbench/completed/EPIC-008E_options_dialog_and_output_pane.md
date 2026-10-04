# EPIC-008E — One Options dialog with contributed pages, and one Output dock with contributed channels

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** ✅ Completed
**Completed Date:** 2026-10-04
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W4)
**Depends on:** EPIC-008B, EPIC-008C

---

## 🎯 Summary & Objectives
Neither exists; the consumer renders settings as a page with a Save button per section and logs as four separate cards.

### Acceptance criteria
- [x] `IOptionsPage` (Protocol): `title`, `widget()`, `apply()`, `revert()`, `is_dirty()`, `validation_message()`.
- [x] `OptionsDialog` titled "Options": section list left, stacked pages right, `QDialogButtonBox` with OK, Cancel and Apply in the platform's order; Apply enabled only when a page is dirty; OK disabled while a page reports a validation message, which is shown in place; Cancel, Esc and the title-bar close revert every page. Opened by Tools → Options (no ellipsis, MS uxguide `cmd-menus`), shortcut `QKeySequence.Preferences` (empty on Windows by platform definition).
- [x] `OutputPane(QDockWidget)`: a channel combo box, a read-only view over the channel's `LogListModel`, Copy and Clear as actions; `OutputChannel` is contributed with an id and title.
- [x] Sample app contributes one settings page and one channel.

## 📐 Implementation Plan / Overview
Windows desktop guidance (MS uxguide `win-dialog-box`: commit buttons, Apply semantics) as Visual Studio and Qt Creator apply it; Visual Studio's Output window.

| File | Change |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/workbench/i_options_page.py, options_dialog.py, output_pane.py, output_channel.py` | New |

> The plan table's `output_channel.py` was folded into `output_pane.py`.

## 🧪 Verification & Test Coverage
Unit: dirty/apply/revert/validation; channel switching; copy. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.

## Implementation notes
- `i_options_page.py` (`IOptionsPage`, with `set_change_listener` so the dialog re-evaluates without polling), `options_dialog.py` (`OptionsDialog`): `QListWidget` sections, `QStackedWidget` pages, `QDialogButtonBox` OK/Cancel/Apply; Apply only while dirty and valid; OK disabled and the first page's reason shown while invalid; `reject()` reverts every page, so Cancel, Esc and the title-bar close all do.
- `output_pane.py` (`OutputPane`, `OutputChannel`): a combo of channels in the pane's toolbar (`QWidgetAction`), a read-only `QListView` over the channel's `LogListModel` through a proxy writing "[HH:MM:SS] message", Copy (selected lines, or all; `StandardKey.Copy` while the lines have focus) and Clear as the pane's own actions in its toolbar and context menu, like Visual Studio's Output toolbar.
- Sample app: `GeneralOptionsPage` (one check box backed by `IConfig`) and an "app" channel.
- Tests: `test_options_dialog.py` (Apply, validation, OK applies only dirty pages, Cancel/Esc/close revert), `test_output_pane.py` (channels, copy all or selected, clear the shown channel only), `test_workbench_shell.py` (Tools → Options opens the dialog; the pane docks and Window lists it), the sample's `test_sample_shell.py`.
