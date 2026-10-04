# EPIC-008F — Tables, lists and read-outs of one kind share their properties: column and value kinds decide them

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** 🔵 Backlog
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W6)
**Depends on:** EPIC-008A

---

## 🎯 Summary & Objectives
The consumer's 12 item views are each configured by hand (selection on 8, edit triggers on 4, 26 header resize calls) and formats values with per-screen helpers, so one price prints differently on two screens. The engine offers nothing for display widgets.

### Acceptance criteria
- [ ] `ColumnKind`: TEXT, QUANTITY, PRICE, PERCENT, MONEY, TIMESTAMP, DURATION, SIDE, STATUS; each decides alignment, width policy (content-sized or the one stretch column) and that sorting uses the raw value role.
- [ ] `ColumnSpec(key, title, kind)`; `configure_item_view(view, specs)` sets selection (rows, single or extended), no editing, sorting, header policy, no vertical header, alternating rows, and installs a delegate that renders through `IValueFormatter`.
- [ ] `IValueFormatter` (Protocol): `format(kind, value, context) -> str`; the engine ships a plain default; the consumer supplies precision policy.
- [ ] `ReadoutForm`: label–value pairs in a `QFormLayout`, values right-aligned and formatted by kind.
- [ ] An empty model shows an instruction in place (MS uxguide `ctrl-list-views`: avoid empty list views), one convention for every view.
- [ ] Headers sort ascending on the first click and descending on the second; sections are movable and their state is saved per view through `ui_state` (MS uxguide `ctrl-list-views`).
- [ ] `find_unconfigured_item_views()` guard helper the consumer's architecture tests can call (same shape as `find_deep_imports`).

## 📐 Implementation Plan / Overview
Declarative column models as in every data-grid toolkit (P5), the component-boundary law: the mechanism owns what is the same on every use.

| File | Change |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/workbench/column_kind.py, column_spec.py, configure_item_view.py, i_value_formatter.py, readout_form.py, item_view_guard.py` | New |

## 🧪 Verification & Test Coverage
Unit: each kind's alignment and sort role, formatter delegation, read-out layout, guard finds an unconfigured view. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.
