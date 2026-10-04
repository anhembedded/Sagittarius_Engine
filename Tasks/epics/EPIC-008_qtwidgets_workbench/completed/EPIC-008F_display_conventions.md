# EPIC-008F — Tables, lists and read-outs of one kind share their properties: column and value kinds decide them

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** ✅ Completed
**Completed Date:** 2026-10-04
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W6)
**Depends on:** EPIC-008A

---

## 🎯 Summary & Objectives
The consumer's 12 item views are each configured by hand (selection on 8, edit triggers on 4, 26 header resize calls) and formats values with per-screen helpers, so one price prints differently on two screens. The engine offers nothing for display widgets.

### Acceptance criteria
- [x] `ColumnKind`: TEXT, QUANTITY, PRICE, PERCENT, MONEY, TIMESTAMP, DURATION, SIDE, STATUS; each decides alignment, width policy (content-sized or the one stretch column) and that sorting uses the raw value role.
- [x] `ColumnSpec(key, title, kind)`; `configure_item_view(view, specs)` sets selection (rows, single or extended), no editing, sorting, header policy, no vertical header, alternating rows, and installs a delegate that renders through `IValueFormatter`.
- [x] `IValueFormatter` (Protocol): `format(kind, value, context) -> str`; the engine ships a plain default; the consumer supplies precision policy.
- [x] `ReadoutForm`: label–value pairs in a `QFormLayout`, values right-aligned and formatted by kind.
- [x] An empty model shows an instruction in place (MS uxguide `ctrl-list-views`: avoid empty list views), one convention for every view.
- [x] Headers sort ascending on the first click and descending on the second; sections are movable and their state is saved per view through `ui_state` (MS uxguide `ctrl-list-views`).
- [x] `find_unconfigured_item_views()` guard helper the consumer's architecture tests can call (same shape as `find_deep_imports`).

## 📐 Implementation Plan / Overview
Declarative column models as in every data-grid toolkit (P5), the component-boundary law: the mechanism owns what is the same on every use.

| File | Change |
| :--- | :--- |
| `sagittarius_engine/extensions/pyside_mvc/workbench/column_kind.py, column_spec.py, configure_item_view.py, i_value_formatter.py, readout_form.py, item_view_guard.py` | New |

## 🧪 Verification & Test Coverage
Unit: each kind's alignment and sort role, formatter delegation, read-out layout, guard finds an unconfigured view. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.

## Implementation notes
- `workbench/column_kind.py` (`ColumnKind`: numbers right, text and dates left), `column_spec.py` (`ColumnSpec`, `Selection`, `spec_problems`: one stretch column at most, unique keys), `i_value_formatter.py` (`IValueFormatter`, `FormatContext`, `PlainValueFormatter`), `configure_item_view.py` (`SpecProxyModel`: header titles, alignment, sort on raw `DisplayRole` values; `KindDelegate` writes through the formatter; rows, single or extended selection, no editing, no vertical header, alternating rows, movable sections; no column sorted until clicked, the first click ascending), `empty_state.py` (`EmptyStateStack`: a stock `QLabel` page while the model has no rows, not an overlay), `readout_form.py` (`ReadoutForm`), `item_view_state_store.py` (`ItemViewStateStore` through `ui_state`), `item_view_guard.py` (`find_unconfigured_item_views()`, combo-box popups skipped).
- Departure: `configure_item_view(view, model, specs)` takes the model and installs the proxy, so sorting on raw values cannot depend on each model implementing `sort()`.
- Tests: `workbench/test_display_conventions.py` (26), with header clicks through real press and release. Mutation-verified: removing the sort-indicator reset fails the "nothing sorted until a click" test.
- Review round 1 (PR #224): non-stretch columns are `Interactive`, fitted to content on configure and on each model reset (not `ResizeToContents`, which Qt warns re-measures every row on every change); a negative duration keeps its sign; `ItemViewStateStore` forgets a destroyed view.
