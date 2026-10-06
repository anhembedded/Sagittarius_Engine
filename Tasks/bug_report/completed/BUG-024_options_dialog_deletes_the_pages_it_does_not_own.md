# BUG-024 — The Options dialog deletes the page widgets it does not own, so the second Tools → Options fails

**Reported date:** 2026-10-06
**Severity:** Medium. The second Tools → Options raised `libshiboken: Internal C++ object (...) already deleted` on every page, so settings could be opened once per run.
**Status:** ✅ Fixed (2026-10-06)
**Found by:** the reference consumer (`Sagittarius_Elite_Warrior`, filed there as its `BUG-162`, worked around app-side by orphaning each page widget as the dialog finished).

---

## What is wrong

`WorkbenchShell.show_options()` builds an `OptionsDialog`, sets `WA_DeleteOnClose` (`BUG-018`), and each open builds a new one. The dialog adds every page's `widget()` to its `QStackedWidget`, which reparents the widget into the dialog. The pages belong to the modules that contributed them and are kept for the next open, but a `QDialog` deletes its children, so deleting the closed dialog deleted the pages' widgets too. The next dialog called `page.widget()` and got a wrapper over a deleted C++ object.

Second defect, same cause: `set_change_listener(self._refresh)` stayed connected to the dialog after it closed, so a page edit afterwards called a dialog that was gone or about to be.

## Decision: detach, not reuse

Two fixes were possible: detach the pages before the dialog is deleted, or never delete the dialog and reuse it. Detach, because:

- `BUG-018` already settled that a closed dialog is deleted (a kept one keeps listening to its pages and lives until the window closes), and `show_options()` and its test `test_a_closed_options_dialog_is_deleted` state it.
- A reused dialog would hold state across opens (selected section, a stale validation message) that each open must reset, a new lifecycle to keep correct; detaching keeps the dialog stateless.
- The rule that a widget has one owner is the Engine's (`ui-architecture.md`): whoever builds it keeps it, and a borrower hands it back.

## Fix

`OptionsDialog.done()` (every way out: OK, Cancel, Esc, title-bar close all end in `done()`) now releases the pages before closing:

- each page's change listener is replaced with a function that does nothing (`IOptionsPage.set_change_listener` documents that it is called again on close), and
- each page widget is removed from the stack and unparented, so deleting the dialog cannot delete it.

The next dialog adds the same widgets again and sets its own listener. No change to `IOptionsPage`'s signature.

## Regression tests

- `test_options_dialog.py::test_deleting_a_closed_dialog_leaves_its_pages_alive` (OK and Cancel): close, delete, then assert every page widget is valid and a second dialog shows them. **Before the fix:** red. **After:** green.
- `test_options_dialog.py::test_a_closed_dialog_no_longer_listens_to_its_pages`: an edit after close must not enable the closed dialog's Apply. **Before:** red. **After:** green.
- `test_workbench_shell.py::TestStatusBarOutputAndOptions::test_tools_options_opens_again_after_it_was_closed`: open and close Tools → Options twice through the shell, the page widget stays valid. **Before:** red. **After:** green.

## Consequence for consumers

A consumer that orphaned its page widgets after the dialog finished (the `BUG-162` workaround) can drop that code. The workaround is harmless alongside the fix.
