# EPIC-008E — One Options dialog with contributed pages, and one Output dock with contributed channels

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** 🔵 Backlog
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W4)
**Depends on:** EPIC-008B, EPIC-008C

---

## 🎯 Summary & Objectives
Neither exists; the consumer renders settings as a page with a Save button per section and logs as four separate cards.

### Acceptance criteria
- [ ] `IOptionsPage` (Protocol): `title`, `widget()`, `apply()`, `revert()`, `is_dirty()`, `validation_message()`.
- [ ] `OptionsDialog` titled "Options": section list left, stacked pages right, `QDialogButtonBox` with OK, Cancel and Apply in the platform's order; Apply enabled only when a page is dirty; OK disabled while a page reports a validation message, which is shown in place; Cancel, Esc and the title-bar close revert every page. Opened by Tools → Options (no ellipsis, MS uxguide `cmd-menus`), shortcut `QKeySequence.Preferences` (empty on Windows by platform definition).
- [ ] `OutputPane(QDockWidget)`: a channel combo box, a read-only view over the channel's `LogListModel`, Copy and Clear as actions; `OutputChannel` is contributed with an id and title.
- [ ] Sample app contributes one settings page and one channel.

## 📐 Implementation Plan / Overview
Windows desktop guidance (MS uxguide `win-dialog-box`: commit buttons, Apply semantics) as Visual Studio and Qt Creator apply it; Visual Studio's Output window.

| File | Change |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/workbench/i_options_page.py, options_dialog.py, output_pane.py, output_channel.py` | New |

## 🧪 Verification & Test Coverage
Unit: dirty/apply/revert/validation; channel switching; copy. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.
