# ADR-003 — The engine provides a QtWidgets workbench of stock controls, built here first

- **Date**: 2026-10-04
- **Status**: Accepted
- **Epic**: [EPIC-008](../epics/EPIC-008_qtwidgets_workbench/README.md)
- **Consumer**: `Sagittarius_Elite_Warrior` Elite EPIC-033

## Context
The only consumer retired QML and the token layer (its ADR D20-D22) and rendered its screens with a hand-styled widget kit; a review of the running app found no menu bar, one workbench mode out of eight, thirteen button styles and twelve hand-configured tables. The engine already owns half a workbench (`RegionHost`, a `QMainWindow`) but no menus, actions, settings dialog, output pane or display conventions. `TASK-043` recorded harvest-first: build in the consumer, move here after a second consumer and a stable phase. `ui-architecture.md` still says tokens own every visual value.

## Decisions
| # | Decision | Decided by |
| :-- | :--- | :--- |
| D1 | The workbench mechanism (EPIC-008B-F) is built in this repository now; harvest-first is superseded for it. | The user: "cái nào cần sửa bên engine thì sửa bên engine" (what needs changing in the engine is changed in the engine); "làm trực tiếp bên engine luôn, ko cần phải dựng ở app trước" (do it directly in the engine, no need to build it in the app first) |
| D2 | The QtWidgets contract is stock controls with their defaults in the platform style; no per-widget style sheet, palette, font or size; tokens and the QML kit bind QML consumers only. | The user: "các UI thì phải đồng nhất … 1 kiểu thui … làm 1 UI sơ đẳng, nhưng đúng triết lý Window app trước, chưa cần tính đến design" (the UI must be uniform, one kind only; a plain UI true to the Windows-app philosophy first, design later) |
| D3 | Display conventions are engine mechanism: column and value kinds decide alignment, sorting and formatting; the consumer supplies precision policy. | The user: "các widget hiện thị cũng phải thống nhất, ví dụ mấy cái mảng thì phải thông nhất các properti" (display widgets must be uniform too, e.g. tables share the same properties) |
| D5 | The QtWidgets rule is the desktop guidance of Microsoft Windows User Experience Interaction Guidelines (`learn.microsoft.com/en-us/windows/win32/uxguide`), Microsoft Fluent / Windows app design, KDE HIG (`develop.kde.org/hig`), Apple HIG, GNOME HIG and Qt's styling guidance (`doc.qt.io/qt-6/qtwidgets-styling-approaches.html`), cited per clause; where they disagree the Windows desktop choice wins (Tools → Options with OK/Cancel/Apply, platform button order via `QDialogButtonBox`). | The user: "tốt nhất là nên tham khảo triết lý UI WINDOW của các tổ chức lớn" (best to draw on the Windows UI philosophy of the major organisations) |
| D4 | One abstraction per file under `pyside_mvc/workbench/`; public symbols exported; released as `3.0.0`: an `a` bump, because `release.md` §2 bumps `a` for a feature change (this row first said `b`, corrected at release, 2026-10-04). | Agent, ONBOARDING §10.5 and `release.md` |

## Consequences
The engine commits to an API before a second consumer exists, accepted for speed by the user. The workbench is Qt's own shapes (`QMainWindow`, `QAction`, `QDockWidget`, `QDialogButtonBox`, model/view), which bounds the risk of a wrong abstraction. `examples/student_management` is the second user from day one.

## Alternatives
Harvest-first (rejected by the user for speed); a QSS theme for consistency (rejected: retired by the consumer's ADR D20-D22 and fixes looks, not structure).
