# BUG-018 — The Options dialog closes after a page fails to apply, and no closed dialog is ever deleted

**Reported date:** 2026-10-04
**Severity:** Medium. A page whose file cannot be written reports the failure in a dialog that has already closed, so the user believes OK saved. Each opening of Tools → Options also leaves one more dialog alive for the life of the window.
**Status:** ✅ Fixed (2026-10-04)
**Found by:** the independent review of the reference consumer's PR #348 (`Sagittarius_Elite_Warrior` `EPIC-033E`), confirmed with a probe against the real `OptionsDialog`.

---

## What is wrong

1. **OK closes even when a page could not apply.** `OptionsDialog.accept()` called `apply()` and then `super().accept()` unconditionally. A page that cannot save its edits stays dirty after `apply()`; its error went to the page's own status line inside a dialog that had just closed.
2. **Closed dialogs are never deleted.** `WorkbenchShell.show_options()` built a new `OptionsDialog`, parented to the window, on every open and never deleted it. Each one kept its pages' change listener until the page replaced it, and stayed in memory until the window closed.

## Reproduction

- **Item 1:** two pages, one whose `apply()` leaves it dirty. Edit both and click OK. The dialog closes, with result Accepted.
- **Item 2:** open Tools → Options three times. Three `OptionsDialog`s remain children of the window.

## Fix

- **`OptionsDialog.apply()`** (`workbench/options_dialog.py`) now returns `True` when every page took its edits. A page still dirty after `apply()` is the dialog's signal that it could not save: the dialog selects that page and shows "<page>: the changes could not be applied."
- **`accept()`** closes only when `apply()` returned `True`.
- **`show_options()`** (`workbench/workbench_shell.py`) sets `WA_DeleteOnClose`, so the closed dialog is deleted when the event loop next runs. The returned dialog must therefore not be used after that.

## Regression tests

- `tests/extensions/pyside_mvc/workbench/test_options_dialog.py::test_ok_keeps_the_dialog_open_while_a_page_could_not_apply`
  - **Before the fix:** red, because the dialog was not visible after OK.
  - **After the fix:** green. The good page is saved, the failing page is selected, and the message names it.
- `tests/extensions/pyside_mvc/workbench/test_workbench_shell.py::TestStatusBarOutputAndOptions::test_a_closed_options_dialog_is_deleted`
  - **Before the fix:** red, because `shiboken6.isValid(dialog)` was still `True` after the deferred deletes ran.
  - **After the fix:** green.

## Verification

- `tests/extensions/pyside_mvc/workbench`: 146 passed.
- `scripts/ci-local.ps1`: see the pull request.
