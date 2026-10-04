# EPIC-008C — Every command is an ActionDescriptor: one QAction for its menu entry, toolbar button and shortcut

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** ✅ Completed
**Completed Date:** 2026-10-04
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W2)
**Depends on:** EPIC-008A

---

## 🎯 Summary & Objectives
The engine has no `QAction`, `QShortcut` or `QKeySequence` anywhere; the consumer builds 8 actions by hand and fakes the rest as styled push buttons.

### Acceptance criteria
- [x] `ActionDescriptor` (frozen): `action_id`, `text`, `menu_path` (e.g. `('Trade',)`), `toolbar` (place or `None`), `shortcut` (`QKeySequence.StandardKey` or string), `icon_name`, `checkable`, `confirm` (a consequence sentence or `None`), `surface_id` (`None` = global).
- [x] `ActionRegistry.contribute()` refuses a duplicate `action_id`, a shortcut already bound in the same scope, and a rebind of a standard shortcut to another meaning.
- [x] `ActionRegistry.bind(action_id, handler, enabled=Signal|None, checked=Signal|None)` connects the presenter; an unbound action at boot is reported, not silent.
- [x] An action with `confirm` raises a `QMessageBox` naming the consequence before its handler runs; Cancel runs nothing.
- [x] Menu text carries an access key (`&`), unique within its menu; a literal ampersand is written `&&`; the registry refuses a duplicate access key in one menu.
- [x] A command that needs more input before it acts ends its text with "…" (U+2026, never "..."); the descriptor's `needs_input` flag and the ellipsis must agree.
- [x] Shortcuts are a `QKeySequence.StandardKey` or from the allowed set for new bindings (Ctrl+G/J/K/L/M/Q/R/T, Ctrl+digit, F7/F8/F9/F12); Ctrl+Alt combinations are refused (MS uxguide `inter-keyboard`).
- [x] A confirmation names the consequence, uses specific verbs (never OK/Cancel) and makes the safe choice the default (MS uxguide `mess-confirm`).
- [x] Every toolbar action is also reachable from a menu; an icon-only toolbar action's tooltip includes its shortcut (MS uxguide `cmd-toolbars`).

## 📐 Implementation Plan / Overview
Qt's Command pattern: one `QAction` per command (Qt docs, Actions), registered like `ContributionRegistry` (opaque ids, validation at contribute time).

| File | Change |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/workbench/action_descriptor.py, action_registry.py, action_confirmation.py` | New, one abstraction per file |

## 🧪 Verification & Test Coverage
Unit: each refusal, binding, confirmation path. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.

## Implementation notes
- `workbench/action_text.py` (access keys, plain text, the ellipsis rule), `shortcut_policy.py` (StandardKey or the free set, compared in Qt's portable spelling), `action_descriptor.py` (`ActionDescriptor`, `ActionConfirmation`, `ActionDeclarationError`; validated at construction), `action_confirmation.py` (`IActionConfirmer`, `MessageBoxConfirmer`, `build_confirmation_box()` with the reject answer as default and escape), `action_registry.py` (`ActionRegistry`).
- Refusals: duplicate id; one key twice in one scope (global meets every mode; two modes may share); a free key the platform reserves (on Linux Ctrl+G is FindNext and Ctrl+T AddTab, found by asking `QKeySequence.keyBindings`); two items of one menu on one access key; one menu spelled with two access keys; OK/Yes answers.
- Departure: the handler gets the checked state read from the action, because PySide gives a `functools.partial` slot the zero-argument `triggered()` overload. A rejected confirmation of a checkable command reverts its check.
- Tests: `workbench/test_action_text.py`, `test_shortcut_policy.py`, `test_action_descriptor.py`, `test_action_confirmation.py`, `test_action_registry.py`. Mutation-verified: removing the confirmation gate fails 2 tests; removing the access-key check fails 1.
