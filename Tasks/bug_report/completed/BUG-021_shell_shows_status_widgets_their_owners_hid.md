# BUG-021 — The shell showed every status-bar widget on each mode change, over its owner's `hide()`

**Reported date:** 2026-10-06
**Severity:** Medium. A consumer's idle widgets appeared in the status bar from start-up in every mode. The reference consumer's Data mode hides its sync progress bar while no sync runs; the shell showed it, indeterminate, so the window looked busy all the time (the consumer's `BUG-151`, reported by its user with a screenshot: "the progress bar always running when I open the app").
**Status:** ✅ Fixed (2026-10-06)
**Found by:** the reference consumer's user; diagnosed from the consumer's `BUG-151`.

---

## What is wrong

`WorkbenchShell.add_status_widget(widget, mode_id)` added the widget to the status bar, and `_sync_status_widgets()` (`workbench_shell.py`, run on every mode change and every add) called `widget.setVisible(scope is None or scope == current)` on the owner's own widget. Two parties decide whether a status widget shows: the shell (is it in the current mode's scope?) and its owner (has it anything to say?). One `setVisible()` answered both, so:

- a widget its owner had hidden was shown again on the next mode change (the consumer's idle progress bar and its empty task label, in every mode);
- a mode-scoped widget its owner showed appeared in every mode until the next mode change.

## Evidence

- The consumer's screenshot and its booted-workbench capture at 1366×768: an animated indeterminate bar and an empty box beside it in Market mode, with no task running.
- The consumer's view hides its bar at construction and only shows it while a task runs (`data_management_view.py`, `_sync_progress`); its bar is indeterminate while hidden (`progressMaximum` is 0). The consumer's new conformance check reported `progress bar prgDataTask is shown with no task running` in all six modes, with this engine at `bf99528`.

## Fix

`StatusSlot` (`workbench/status_slot.py`): the shell puts each status widget in a slot and sets only the slot's scope. The owner keeps calling `show()` and `hide()` on its own widget, which the shell never touches; the slot follows it through `ShowToParent`/`HideToParent` and shows when both say yes, so no empty box is left either. The owner's wish is the widget's own `isHidden()`, which only the owner sets now. Moving the widget into its slot does not mark it hidden; Qt shows it with the slot. A widget its owner deletes leaves the slot hidden.

## Regression tests

`tests/extensions/pyside_mvc/workbench/test_workbench_shell.py::TestStatusBarOutputAndOptions`:
- `test_a_status_widget_its_owner_hid_stays_hidden_in_every_mode`: **before**, red (the hidden widget was visible after a mode change); **after**, green. It also asserts no status-bar item is shown for it; with the slot ignoring the owner, that assertion fails.
- `test_a_status_widget_its_owner_shows_appears_in_its_scope`: **before**, red (a mode-scoped widget its owner showed was visible outside its mode); **after**, green. With the slot's event filter removed, it fails.
- `test_a_status_widget_shows_at_once_in_a_shown_window`: a widget its owner never hid shows as soon as it is added.
- `test_a_status_widget_its_owner_deleted_leaves_no_empty_item`: red until the slot followed `destroyed`.

## Verification

- Engine: the shell's 28 tests pass; the whole suite, 1746 passed; CI's ruff and mypy commands are clean.
- The consumer, with this engine installed: its conformance suite passes at 1024×700, 1366×768 and 1920×1080, including the new `no_progress_at_rest` check that was red before. In the consumer's booted app the Data mode's bar is held by a `StatusSlot`, shows (indeterminate) in Market and Backtest while a sync runs, and hides, slot included, when it ends, and stays hidden across a mode change.
- Scan: no other place sets a widget's visibility from a mode scope; `RegionHost` only adds its status-bar widgets.

## Related

- The consumer's `BUG-151`.
