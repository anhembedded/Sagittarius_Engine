# EPIC-008C — Every command is an ActionDescriptor: one QAction for its menu entry, toolbar button and shortcut

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** 🔵 Backlog
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W2)
**Depends on:** EPIC-008A

---

## 🎯 Summary & Objectives
The engine has no `QAction`, `QShortcut` or `QKeySequence` anywhere; the consumer builds 8 actions by hand and fakes the rest as styled push buttons.

### Acceptance criteria
- [ ] `ActionDescriptor` (frozen): `action_id`, `text`, `menu_path` (e.g. `('Trade',)`), `toolbar` (place or `None`), `shortcut` (`QKeySequence.StandardKey` or string), `icon_name`, `checkable`, `confirm` (a consequence sentence or `None`), `surface_id` (`None` = global).
- [ ] `ActionRegistry.contribute()` refuses a duplicate `action_id`, a shortcut already bound in the same scope, and a rebind of a standard shortcut to another meaning.
- [ ] `ActionRegistry.bind(action_id, handler, enabled=Signal|None, checked=Signal|None)` connects the presenter; an unbound action at boot is reported, not silent.
- [ ] An action with `confirm` raises a `QMessageBox` naming the consequence before its handler runs; Cancel runs nothing.
- [ ] Menu text carries an access key (`&`), unique within its menu; a literal ampersand is written `&&`; the registry refuses a duplicate access key in one menu.
- [ ] A command that needs more input before it acts ends its text with "…" (U+2026, never "..."); the descriptor's `needs_input` flag and the ellipsis must agree.
- [ ] Shortcuts are a `QKeySequence.StandardKey` or from the allowed set for new bindings (Ctrl+G/J/K/L/M/Q/R/T, Ctrl+digit, F7/F8/F9/F12); Ctrl+Alt combinations are refused (MS uxguide `inter-keyboard`).
- [ ] A confirmation names the consequence, uses specific verbs (never OK/Cancel) and makes the safe choice the default (MS uxguide `mess-confirm`).
- [ ] Every toolbar action is also reachable from a menu; an icon-only toolbar action's tooltip includes its shortcut (MS uxguide `cmd-toolbars`).

## 📐 Implementation Plan / Overview
Qt's Command pattern: one `QAction` per command (Qt docs, Actions), registered like `ContributionRegistry` (opaque ids, validation at contribute time).

| File | Change |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/workbench/action_descriptor.py, action_registry.py, action_confirmation.py` | New, one abstraction per file |

## 🧪 Verification & Test Coverage
Unit: each refusal, binding, confirmation path. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.
