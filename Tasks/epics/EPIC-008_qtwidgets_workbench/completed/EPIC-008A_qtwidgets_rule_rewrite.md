# EPIC-008A — The UI rule describes a QtWidgets workbench in the platform style

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** ✅ Completed
**Completed Date:** 2026-10-04
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W5)
**Depends on:** None

---

## 🎯 Summary & Objectives
`.agents/rules/ui-architecture.md` describes a PySide6 + QML engine whose tokens own every colour, spacing and font and whose QML kit owns every primitive (§1-§2). The only consumer retired QML and tokens (its ADR D20-D22) and now asks for stock controls in the platform style. The engine docs still list a `pyside_mvc/widgets/` package that moved out in the consumer's EPIC-007H (`Tasks/README.md:42`, `.agents/ONBOARDING.md:296`, `Tasks/decisions/ADR-002...:80`).

### Acceptance criteria
- [x] Every principle and clause of the rewritten rule cites its source among Microsoft Windows User Experience Interaction Guidelines (`learn.microsoft.com/en-us/windows/win32/uxguide`), Microsoft Fluent / Windows app design, KDE HIG (`develop.kde.org/hig`), Apple HIG, GNOME HIG and Qt's styling guidance (`doc.qt.io/qt-6/qtwidgets-styling-approaches.html`) (the consumer's digest: its [UI review](https://claude.ai/artifact/Np92LCSrk2t2e8NQxLEkaE)); the user asked for this: "tốt nhất là nên tham khảo triết lý UI WINDOW của các tổ chức lớn" (best to draw on the Windows UI philosophy of the major organisations).
- [x] Where the sources disagree, the rule records the Windows desktop choice: platform button order through `QDialogButtonBox`, Tools → Options, OK/Cancel/Apply with Apply enabled only on pending changes, Windows capitalisation, the Qt style's `pixelMetric` values instead of any fixed grid.
- [x] `ADR-003_qtwidgets_workbench.md` records D1-D4 of this epic with the user's words.
- [x] `ui-architecture.md` describes the QtWidgets workbench as the engine's UI contract: stock controls with their defaults, the platform style, no per-widget style sheet, palette, font or size; the component-boundary law (§1.2) kept and restated for QtWidgets: a mechanism owns what is the same on every use (column alignment by kind, dock toggles, perspective keys), the consumer owns what differs (which columns, which modes).
- [x] The tokens and QML kit sections are scoped to QML consumers; nothing in them binds a QtWidgets consumer.
- [x] The `widgets/` documentation drift is corrected in all three places.

## 📐 Implementation Plan / Overview
Rule first, so every later subtask is judged against it (the consumer's D2: philosophy before mechanism).

| File | Change |
| :--- | :--- |
| `.agents/rules/ui-architecture.md` | Rewritten |
| `Tasks/decisions/ADR-003_qtwidgets_workbench.md` | New |
| `Tasks/README.md, .agents/ONBOARDING.md, ADR-002` | Drift fixed |

## 🧪 Verification & Test Coverage
Docs only: `tests/test_agents_docs_resolve.py` and the doc-code-sync rule. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.

## Implementation notes
- `.agents/rules/ui-architecture.md`: the title, description and a consumer table state two contracts. QtWidgets is the default and binds §1, §1.2 and §4-§9; QML binds §1-§8, with §1.1, §2 and §3 marked QML-only. §1 gains the QtWidgets ownership test (switch the OS theme: zero consumer files change). §1.2 gains two QtWidgets rows (column kind, command confirmation). The new §9 is the contract, every clause with its source: §9.1 sources and precedence, §9.2 stock controls, §9.3 commands, §9.4 dialogs and Options, §9.5 modes, panels and perspectives, §9.6 tables and read-outs, §9.7 feedback. Section numbers §1-§8 are unchanged, because 50+ citations use them.
- ADR-003 D1-D5 already carried the user's words (commit 058c90f).
- `widgets/` drift: `.agents/ONBOARDING.md` §-table row and `Tasks/README.md` TASK-038 row now say the package left the engine in `7a3ac18`; ADR-002:80 already said so. `pyside_mvc/README.md` gains the Workbench row and the `runtime/`/`workbench/` files it was missing.
