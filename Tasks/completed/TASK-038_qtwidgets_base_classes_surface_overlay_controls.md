# TASK-038: `pyside_mvc.widgets` — QtWidgets base classes (Surface/Card/Overlay/Styled*)

## Description

`Sagittarius_Elite_Warrior` decided to drop QML project-wide (`EPIC-006`, see that repo's
`Tasks/epics/EPIC-006_drop_qml/README.md` and
`DECISION_2026-08-24_widget_architecture.md`), following a chain of findings that started with
`BUG-039` (the native chart renderer never actually rendered a production frame, undermining
the performance premise `EPIC-005`'s ADR used to keep the chart on QtQuick). This task builds
the engine-side QtWidgets replacement for `Sagittarius/UI/`'s QML kit — `EPIC-005`'s own
migration (`SettingsScreen`/`DatabaseScreen`) had already hand-rolled `setStyleSheet()` calls
per widget with no shared base, which the user flagged as "card vs non-card lộn xộn" (card and
non-card widgets jumbled together) and asked for a real OOP hierarchy.

Explicitly evaluated and declined: `qfluentwidgets` (this repo's own `TASK-037` prototype,
already validated and shipped in `examples/student_management`). The user chose to build a
custom hierarchy instead, so both approaches now coexist in this repo for different consumers —
this is not a reversal of `TASK-037`'s conclusion, just a different choice for a different app.

## What was built (2026-08-24)

New package `sagittarius_engine/extensions/pyside_mvc/widgets/`:

- **`style.py`** — `StyleRole`/`WidgetState` enums, `apply_role(widget, role, state=...)`. The
  ONLY file permitted to build a QSS string from token values — every widget in this package
  calls it once, in its own `__init__`, rather than inheriting styling behaviour. Reads live
  token values via `get_theme_bridge().value(name)` (verified this works from plain Python, no
  QML engine needed — `QQmlPropertyMap` is a real `QObject` with a callable `.value()` method).
- **`surface.py`** — `Surface(QFrame)` (abstract gate), `Panel(Surface)` (bare grouping box,
  concrete), `Card(Surface)` (title + `header_actions` + `body_layout`, concrete).
- **`overlay.py`** — `Overlay(QDialog)` (abstract gate: title/subtitle header, `body_layout`,
  subclass-supplied `_build_buttons()` footer).
- **`controls.py`** — `StyledButton(QPushButton)`, `StyledCheckBox(QCheckBox)`,
  `StyledField(QLineEdit)`, `DateTimeField(QDateTimeEdit)` — each a single-inheritance subclass
  of its own distinct Qt base, no shared control base.
- **`guards.py`** — `find_inline_stylesheets()` (no hex literal outside `style.py`, counterpart
  to `tokens.qml_literal_guard`), `find_bare_qt_base_widgets()` (no `class X(QFrame)`/
  `class X(QDialog)` outside `surface.py`/`overlay.py`, counterpart to `kit.raw_primitive_guard`).
  No coverage-guard counterpart yet — no QtWidgets showcase exists to check coverage against;
  add one when `EPIC-006C`+ gives this package a real consumer to build one from.

`pyside_mvc/__init__.py` re-exports everything from `widgets/`, same pattern as `kit`/`mvc`/
`runtime`/`safety`/`tokens`.

## Key finding: `@abstractmethod`/`ABCMeta` does not reliably block instantiation for a Qt widget subclass

Verified empirically before relying on it: `class Surface(QFrame, metaclass=_QtABCMeta)` with an
unimplemented `@abstractmethod` **constructs without raising** under this PySide6/Shiboken
version — the metaclass combination doesn't crash, but `ABCMeta`'s instantiation-blocking
behaviour silently doesn't fire. The reliable alternative, used throughout this package: a
`type(self) is BaseClass` guard raising `TypeError` in `__init__`, verified to work correctly.
Documented in `Surface`'s and `Overlay`'s own docstrings so a future reader doesn't rediscover
this the hard way.

## Second finding: `configure_app_qml()` does not itself populate `get_theme_bridge()`

`get_theme_bridge()`'s singleton is only populated as a side effect of `register_theme()`,
called from `create_quick_widget()` — i.e. only when a `QmlHostView`-based screen actually
constructs. A pure-QtWidgets screen never triggers this path. **Not fixed here** — out of scope
for this task (which only needed the singleton populated inside its own tests, via a local
palette). Elite's own `app_bootstrapper.py` will need a small addition once it starts
constructing real `widgets/`-based screens with no QML anywhere in the call path
(`EPIC-006C`+) — call `get_theme_bridge(Palette.as_ui_dict())` directly at boot, independent of
`configure_app_qml()`. Documented in `apply_role()`'s own docstring so this isn't lost.

## Test isolation gotcha: the shared theme-bridge singleton across the FULL test session

`get_theme_bridge()` is process-wide and first-caller-wins. Two tests initially compared
enabled-vs-disabled button QSS output and failed only when the **whole** engine test suite ran
together (not in isolation) — some other suite's placeholder palette (`test_overlay_host.py`'s
all-`#000000`) won the race first, making every token (`muted`, `accent`, ...) collide to the
same value and silently erasing the distinction being tested. Fixed with a `fake_theme_bridge`
fixture (`monkeypatch`-replaces `widgets.style.get_theme_bridge` with a stand-in returning a
distinct string per token name) for the two tests that specifically need cross-token
distinctness — every other test in the package either asserts structural properties (non-empty
QSS) or reads back whichever live value actually won and asserts it appears in the output,
which holds regardless of which palette won.

## Test coverage

`tests/extensions/pyside_mvc/widgets/` — 41 tests: `test_style.py` (7), `test_surface.py` (8),
`test_overlay.py` (8), `test_controls.py` (7), `test_guards.py` (11, mirroring
`test_raw_primitive_guard.py`'s `tmp_path` pattern). Guards self-checked against the real
`widgets/` package source (0 findings both ways, matching `EPIC-001C`'s own precedent of testing
a new guard against the kit it ships alongside).

## Also fixed in passing

`.venv`'s `requirements.txt`/`requirements-dev.txt` had declared `PySide6-Fluent-Widgets`/
`pytest-qt` (`TASK-037`) but neither had actually been `pip install`ed into this repo's own
`.venv` — `ci-local.ps1 -Full` failed test collection on the two `qfluentwidgets`-based example
test files before this was noticed. Installed both; unrelated to this task's own code, but
blocking verification of it.

## Verification

`pwsh -NoProfile -File scripts/ci-local.ps1 -Full` — `RESULT: PASS`, `890 passed, 5 skipped` (up
from baseline's `849 passed` by the 41 new tests), log scan clean (no WARNING/ERROR/CRITICAL).
`ruff check`/`ruff format`/`mypy --config-file pyproject.toml` all clean on every new file.

## Category

Architecture / Presentation Layer

## Related

- `Sagittarius_Elite_Warrior`'s `EPIC-006` (`Tasks/epics/EPIC-006_drop_qml/`) — the consumer this
  was built for; `EPIC-006C`/`D`/`E` will build real Elite screens on top of this package.
- `BUG-039` — the finding that made dropping QML production-viable (native chart never actually
  ran in production; the QtWidgets/pyqtgraph renderer was already the more complete one).
- `TASK-037` — the qfluentwidgets alternative, evaluated and declined by the user for this
  effort, still valid and shipped for `examples/student_management`.
