# BUG-022 — A status slot showed itself as a top-level window before it was in the status bar

**Reported date:** 2026-10-06
**Severity:** Low. For a moment per status widget, at start-up, the shell opened a tiny top-level window. On Qt's offscreen platform each one logs `This plugin does not support propagateSizeHints()`, which fails the reference consumer's sanity tier (12 errors); on a desktop it can flash.
**Status:** ✅ Fixed (2026-10-06)
**Found by:** the reference consumer's sanity tier (`diagnostic_guard`), on the `engine.ref` bump to `495d654` (this repository's PR #233, `BUG-021`).

---

## What is wrong

`BUG-021`'s `StatusSlot` (`workbench/status_slot.py`) called `_refresh()` at the end of its constructor, and `WorkbenchShell.add_status_widget()` built the slot with no parent before handing it to `QStatusBar.addPermanentWidget()`. A parentless widget that `setVisible(True)` is a top-level window, so every status widget opened one for an instant.

## Why no net here caught it

This repository's suite does not fail on Qt warnings; the consumer's sanity tier does. The shell's tests asserted what the status bar shows, not that nothing else opened.

## Fix

- The shell builds each slot with the status bar as its parent.
- `StatusSlot._refresh()` does nothing while the slot is a window; the bar shows it when it is added.

## Regression tests

`tests/extensions/pyside_mvc/workbench/test_workbench_shell.py::TestStatusBarOutputAndOptions`:
- `test_a_status_widget_never_opens_a_window_of_its_own`: watches `Show` events on top-level widgets while a status widget is added. **Before**, red (the slot was shown as a window); **after**, green. With both changes reverted it fails.
- `test_a_status_slot_without_a_parent_stays_hidden`: red with the window guard removed.

## Verification

- The consumer's sanity tier with this engine installed: 36 passed, no `propagateSizeHints` message (was 36 passed, 12 errors). Its conformance suite: 5 passed.
- Engine: 1748 passed, 7 skipped; ruff and CI's mypy command clean.

## Related

- `BUG-021`, which introduced the slot.
