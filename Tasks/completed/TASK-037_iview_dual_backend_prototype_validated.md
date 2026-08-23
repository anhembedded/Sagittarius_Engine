# TASK-037: `IView` dual-backend (QML/QWidget) — prototype validated, then rolled out to the full roster screen

## Description

Following the "would QWidget be easier?" discussion during TASK-036's work, the user asked to
evaluate feasibility of making `examples/student_management`'s screens implement a common `IView`
interface so the app could load either a QML or a QWidget rendering backend, selected via a
`run.ps1 --qtwidget`-style flag. Rather than rewrite the whole (large) roster screen up front, the
agreed scope was a small prototype: just the enroll form, to validate the pattern before deciding
whether the full investment is worth it.

## What was built (2026-08-23)

- `sagittarius_engine/extensions/pyside_mvc/mvc/i_view.py` — `IView`, a `runtime_checkable`
  `Protocol` with one method, `bind(view_model)`. Exported from both `mvc/__init__.py` and the
  top-level `pyside_mvc/__init__.py`, alongside `BasePresenter`/`BaseView`.
- `examples/student_management/presentation/enroll_form/` — a self-contained MVP triad:
  - `enroll_form_view_model.py` — `EnrollFormViewModel`, a plain `QObject` (deliberately **not**
    `BaseQmlViewModel`, whose whole reason to exist is QML's `uiMode` FSM binding — a ViewModel
    that must work with either backend has no business depending on either).
  - `qml_enroll_form_view.py` / `qml/EnrollForm.qml` — the QML backend; `bind()` does what
    `RosterPresenter` already does by hand today (`set_view_model()` + `load_qml()`).
  - `widget_enroll_form_view.py` — the QWidget backend; `QFormLayout` + `QLineEdit`s +
    `QDoubleSpinBox` + `QPushButton`.
  - `enroll_form_presenter.py` — `EnrollFormPresenter`, written once against `IView`, with zero
    knowledge of which concrete View it was given.
  - `enroll_form_view_factory.py` — `register_enroll_form_view(container)`, registering `IView`
    on the app's `IContainer` via `container.singleton(IView, factory)` where the factory reads
    `IConfig`'s `ui.qtwidget` key once and picks the concrete class — per the user's explicit
    request to use the container's own factory-function support rather than an if/else at each
    call site.
  - `enroll_form_prototype.py` (app root) — a standalone entry point (`--qtwidget` flag),
    deliberately **not** wired into `gui.py`/`run.ps1` yet.
- Tests: `examples/student_management/tests/presentation/enroll_form/test_enroll_form_iview.py` —
  both concrete Views satisfy `IView`; `EnrollFormPresenter` produces identical submitted data
  through either one; the factory picks the right backend from config; a QWidget-specific
  regression test (see finding below).

## Findings

1. **The pattern works.** `EnrollFormPresenter` genuinely never imports or branches on QML vs.
   QWidget — verified with real screenshots of both backends showing the same typed-in data, and
   automated tests asserting identical submitted output through the same presenter code path.
2. **QWidget's built-in controls are a real, concrete win for form-like screens.**
   `QDoubleSpinBox` gets range/decimal validation for free where `EnrollForm.qml`'s GPA field has
   to hand-parse `parseFloat(text) || 0.0`. The same logic extends further for a *table* screen:
   `QTableView` + `QHeaderView` would have given `AppDataTable`'s sort/resize/select
   (`_sortedModel()`, `_resizeColumn()`, `DragHandler`, `onModelChanged` selection-reset fix — all
   shipped this session, see TASK-036) for free too, via `setSortingEnabled(True)` and
   `setSectionResizeMode`.
3. **Two-way binding is not free on the QWidget side, and this bit the prototype once.**
   `EnrollForm.qml`'s `text: viewModel.fullName` re-renders automatically on any ViewModel change;
   `WidgetEnrollFormView` initially only wired the forward direction (`textEdited` → ViewModel).
   Verifying with a real screenshot caught this immediately (fields set programmatically on the
   ViewModel never appeared in the `QLineEdit`s) — fixed by explicitly connecting each
   `*Changed` signal back to the corresponding `setText()`/`setValue()`. A QWidget View has to do
   this by hand, every field, every screen; QML never has to think about it.
4. **The real cost is scope, not the pattern.** The enroll form is the smallest real screen in
   this app (4 fields, 1 button) and still needed a full parallel implementation — no code or
   `.qml` file is shared between the two backends. Extending this to the *full* roster screen
   means also building QWidget equivalents of `AppDataTable`, `TimeRangeCard` (or two
   `QDateTimeEdit`s), `LogPanel` (a `QListWidget`/`QPlainTextEdit`), and `AppModal` (a `QDialog`)
   — none reusable from the QML kit, and every future roster feature needs implementing twice
   from then on.

## Full rollout (2026-08-23, same day) — done

The user saw the enroll-form prototype (both backends run side by side), preferred the QWidget
look, and asked to extend it to the whole roster screen, keeping QML available via a flag (not
replacing it). Shipped:

1. `RosterPresenter`/`RosterView` refactored to `IView.bind()` — `RosterPresenter.__init__` now
   calls `self.view.bind(self.view_model)` instead of `set_view_model()`/`load_qml()` directly;
   `RosterView.bind()` does those two calls internally, unchanged behavior for the QML path.
2. `WidgetRosterView` (`presentation/roster/widget_roster_view.py`) — `QTableView` +
   `StudentTableModel`/`NumericAwareSortProxyModel` (`student_table_model.py`, a custom
   `QAbstractTableModel` + `QSortFilterProxyModel` sorting by a raw-value role so GPA sorts
   numerically, not as formatted text) for the table, 2×`QDateTimeEdit` + a checkbox + Clear
   button for the time filter, a `QListWidget` fed from `LogListModel.entries`/`countChanged` for
   the activity log (its `Copy`/`Clear` buttons call the SAME `LogListModel.copyAllToClipboard()`/
   `.clear()` slots LogPanel.qml already used), and an inline `QDialog` for enroll (not
   `WidgetEnrollFormView` — that one's `bind()` asserts on `EnrollFormViewModel` specifically,
   RosterViewModel isn't that type, so the roster's own small dialog just calls
   `view_model.requestEnroll()` directly instead of forcing a ViewModel-type mismatch).
3. `roster_view_factory.py` (`IRosterView` + `register_roster_view`) — same
   `container.singleton(IView-subtype, factory)` pattern as the enroll form's own factory.
4. `gui.py` gained a `--qtwidget` CLI flag; `run.ps1` gained `-QtWidget`, which forwards it (and
   warns and no-ops it under `-Cli`, which has no rendering backend to pick).
5. Both backends re-verified end to end with real screenshots (enroll a student, check the table/
   stats/log update; QML's teardown-safety fix in `gui.py` from earlier this session still applies
   for that path, and is a harmless no-op for `--qtwidget` since there's no QQuickWidget/Theme to
   race there).

### Findings from the full rollout

- **Confirms finding 2 concretely**: `QTableView` + `QHeaderView` gave sort/resize/select for
  free (`setSortingEnabled(True)`, the header's default Interactive resize mode,
  `selectionBehavior`) — none of `AppDataTable.qml`'s `_sortedModel()`/`_resizeColumn()`/
  `DragHandler` machinery needed porting.
- **The two-way-binding gap (finding 3) recurs per screen, not just per field type**: the time
  filter needed the same ViewModel→widget sync (`dateFilterChanged` → `_sync_filter_from_model()`)
  the enroll form's text fields needed, this time for `QDateTimeEdit`/`QCheckBox`.
- **A new, unrelated gotcha found here**: a test that constructs a `QWidget` without requesting
  pytest-qt's `qtbot` fixture *and* runs before any other test in the session has requested
  `qtbot` can hang indefinitely instead of erroring — apparently because no `QApplication` yet
  exists when the widget is constructed under this offscreen/PySide6 6.11 setup, and Qt hangs
  waiting on an event loop that was never started rather than raising cleanly. Every new test file
  should request `qtbot` (even where a widget is only constructed, never shown) rather than assume
  an existing pytest-qt session already made a `QApplication` available.
- **`QAbstractTableModel.headerData()`'s default row header** (the row-number column) needed
  `verticalHeader().setVisible(False)` explicitly — otherwise the table showed a meaningless
  arbitrary index column `AppDataTable.qml` has no equivalent of.

## Styled with qfluentwidgets (same day) — "make it look WOW"

The user compared both backends side by side, preferred the plain-QWidget look over QML's, and
asked to use a real external library for a more polished result — following up on the
`PySide6-Fluent-Widgets`/`qfluentwidgets` spike already recorded above. Every widget in
`WidgetRosterView`/`WidgetEnrollFormView`/`_EnrollDialog` swapped for its qfluentwidgets
counterpart (`TableView`, `DateTimeEdit`, `ListWidget`, `HeaderCardWidget`, `LineEdit`,
`CheckBox`, `DoubleSpinBox`, `PushButton`/`PrimaryPushButton`, `TitleLabel`/`BodyLabel`/
`StrongBodyLabel`, `MessageBoxBase` for the enroll dialog) — every one a genuine subclass of its
stock-Qt equivalent, so none of the wiring code from the plain-Qt version needed to change, only
the imports/construction. `setTheme(Theme.DARK)` (qfluentwidgets' own global theme switch, called
once per `bind()`, idempotent) fixes a real visual bug found via screenshot: the library defaults
to its light theme regardless of the window's own dark background, producing light cards on a
dark window until this was set explicitly.

**This time a proper `.venv` was set up first** (`python -m venv .venv`, `pip install -r
requirements.txt -r requirements-dev.txt`), avoiding the earlier spike's side effect of silently
upgrading system-wide PySide6. `requirements.txt` gained `PySide6-Fluent-Widgets`;
`requirements-dev.txt` gained `pytest-qt` too — a real, independently-existing gap this surfaced
(the test suite has always depended on the `qtbot` fixture, but nothing had ever declared it,
so a fresh `pip install -r requirements-dev.txt` on a machine without it already present
system-wide could never actually run the Qt tests).

**A real import-boundary bug found and fixed**: `roster_view_factory.py`/
`enroll_form_view_factory.py` originally imported `WidgetRosterView`/`WidgetEnrollFormView` at
module top level, unconditionally — importing the factory at all (even for the QML-only default
path) then required `qfluentwidgets` to be installed, breaking any environment with PySide6 but
not qfluentwidgets (this repo's own system Python, pre-`.venv`). `code-rule.md` §5 forbids
function-local imports outright, so the fix is the same guarded pattern
`persistence/database_module.py` already uses for its own optional `sqlalchemy` dependency: a
top-level `try/except ImportError` setting an `_AVAILABLE` flag, checked (and raising a clear
`ImportError` if false) only inside `_build_view()` when `--qtwidget` is actually requested.

## Priority

P3 — no defect, a deliberately paused architecture decision pending the user's call on scope.

## Category

Architecture / Presentation Layer

## Related

- TASK-036 — the AppDataTable sort/resize/select work that finding 2 above draws its QTableView
  comparison from.
