# EPIC-008A — The UI rule describes a QtWidgets workbench in the platform style

**Epic:** [EPIC-008 — QtWidgets Workbench](../README.md)
**Status:** 🔵 Backlog
**Category:** UI Engine / Workbench (`pyside_mvc`)
**Consumer:** `Sagittarius_Elite_Warrior` Elite EPIC-033 (track W5)
**Depends on:** None

---

## 🎯 Summary & Objectives
`.agents/rules/ui-architecture.md` describes a PySide6 + QML engine whose tokens own every colour, spacing and font and whose QML kit owns every primitive (§1-§2). The only consumer retired QML and tokens (its ADR D20-D22) and now asks for stock controls in the platform style. The engine docs still list a `pyside_mvc/widgets/` package that moved out in the consumer's EPIC-007H (`Tasks/README.md:42`, `.agents/ONBOARDING.md:296`, `Tasks/decisions/ADR-002...:80`).

### Acceptance criteria
- [ ] Every principle and clause of the rewritten rule cites its source among Microsoft Windows User Experience Interaction Guidelines (`learn.microsoft.com/en-us/windows/win32/uxguide`), Microsoft Fluent / Windows app design, KDE HIG (`develop.kde.org/hig`), Apple HIG, GNOME HIG and Qt's styling guidance (`doc.qt.io/qt-6/qtwidgets-styling-approaches.html`) (the consumer's digest: its [UI review](https://claude.ai/artifact/Np92LCSrk2t2e8NQxLEkaE)); the user asked for this: "tốt nhất là nên tham khảo triết lý UI WINDOW của các tổ chức lớn" (best to draw on the Windows UI philosophy of the major organisations).
- [ ] Where the sources disagree, the rule records the Windows desktop choice: platform button order through `QDialogButtonBox`, Tools → Options, OK/Cancel/Apply with Apply enabled only on pending changes, Windows capitalisation, the Qt style's `pixelMetric` values instead of any fixed grid.
- [ ] `ADR-003_qtwidgets_workbench.md` records D1-D4 of this epic with the user's words.
- [ ] `ui-architecture.md` describes the QtWidgets workbench as the engine's UI contract: stock controls with their defaults, the platform style, no per-widget style sheet, palette, font or size; the component-boundary law (§1.2) kept and restated for QtWidgets: a mechanism owns what is the same on every use (column alignment by kind, dock toggles, perspective keys), the consumer owns what differs (which columns, which modes).
- [ ] The tokens and QML kit sections are scoped to QML consumers; nothing in them binds a QtWidgets consumer.
- [ ] The `widgets/` documentation drift is corrected in all three places.

## 📐 Implementation Plan / Overview
Rule first, so every later subtask is judged against it (the consumer's D2: philosophy before mechanism).

| File | Change |
| :--- | :--- |
| `.agents/rules/ui-architecture.md` | Rewritten |
| `Tasks/decisions/ADR-003_qtwidgets_workbench.md` | New |
| `Tasks/README.md, .agents/ONBOARDING.md, ADR-002` | Drift fixed |

## 🧪 Verification & Test Coverage
Docs only: `tests/test_agents_docs_resolve.py` and the doc-code-sync rule. Full gate: `pwsh scripts/ci-local.ps1`, read `logs/ci-local-latest.log`.
