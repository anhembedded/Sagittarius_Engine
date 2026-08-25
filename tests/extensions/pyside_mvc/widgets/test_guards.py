"""Tests for `widgets.guards` — the QtWidgets counterparts to
`tokens.qml_literal_guard`/`kit.raw_primitive_guard`."""

from __future__ import annotations

from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc.widgets.guards import (
    find_bare_qt_base_widgets,
    find_inline_stylesheets,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------- #
# find_inline_stylesheets
# ---------------------------------------------------------------------- #


def test_finds_a_hex_literal_in_a_setstylesheet_call(tmp_path: Path):
    _write(
        tmp_path / "some_widget.py",
        'widget.setStyleSheet("background-color: #111318;")\n',
    )

    findings = find_inline_stylesheets(tmp_path)

    assert len(findings) == 1
    assert findings[0].matched == "#111318"
    assert findings[0].file.name == "some_widget.py"


def test_does_not_flag_style_py_itself(tmp_path: Path):
    _write(
        tmp_path / "style.py",
        'widget.setStyleSheet("background-color: #111318;")\n',
    )

    findings = find_inline_stylesheets(tmp_path)

    assert findings == []


def test_respects_the_token_exempt_marker(tmp_path: Path):
    _write(
        tmp_path / "legacy.py",
        'widget.setStyleSheet("color: #ffffff;")  # token-exempt: migration leftover\n',
    )

    findings = find_inline_stylesheets(tmp_path)

    assert findings == []


def test_ignores_comment_only_lines(tmp_path: Path):
    _write(tmp_path / "note.py", "# was #111318 before the token migration\n")

    findings = find_inline_stylesheets(tmp_path)

    assert findings == []


def test_clean_file_produces_no_findings(tmp_path: Path):
    _write(
        tmp_path / "clean_widget.py",
        "from .style import StyleRole, apply_role\n"
        "apply_role(self, StyleRole.SURFACE)\n",
    )

    findings = find_inline_stylesheets(tmp_path)

    assert findings == []


# ---------------------------------------------------------------------- #
# find_bare_qt_base_widgets
# ---------------------------------------------------------------------- #


def test_finds_a_class_directly_subclassing_qframe(tmp_path: Path):
    _write(tmp_path / "custom.py", "class MyPanel(QFrame):\n    pass\n")

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QFrame"


def test_finds_a_class_directly_subclassing_qdialog(tmp_path: Path):
    _write(tmp_path / "custom.py", "class MyDialog(QDialog):\n    pass\n")

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QDialog"


def test_does_not_flag_surface_py_or_overlay_py(tmp_path: Path):
    _write(tmp_path / "surface.py", "class Surface(QFrame):\n    pass\n")
    _write(tmp_path / "overlay.py", "class Overlay(QDialog):\n    pass\n")

    findings = find_bare_qt_base_widgets(tmp_path)

    assert findings == []


def test_does_not_flag_a_class_extending_surface_or_overlay(tmp_path: Path):
    _write(tmp_path / "card.py", "class Card(Surface):\n    pass\n")
    _write(tmp_path / "confirm.py", "class ConfirmOverlay(Overlay):\n    pass\n")

    findings = find_bare_qt_base_widgets(tmp_path)

    assert findings == []


def test_does_not_flag_controls_extending_their_own_qt_base(tmp_path: Path):
    _write(
        tmp_path / "controls.py",
        "class StyledButton(QPushButton):\n    pass\n\n\n"
        "class DateTimeField(QDateTimeEdit):\n    pass\n",
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert findings == []


def test_finds_a_class_directly_subclassing_qwidget(tmp_path: Path):
    """EPIC-007A: the gap that let 9 of the consuming app's surfaces through.
    A `class X(QWidget)` is the same "authored a raw primitive" mistake as
    `class X(QFrame)`; only the spelling differed."""
    _write(
        tmp_path / "log_panel_widget.py", "class LogPanelWidget(QWidget):\n    x=1\n"
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QWidget"


def test_base_exempt_marker_with_a_reason_waives_the_finding(tmp_path: Path):
    _write(
        tmp_path / "base_view.py",
        "class BaseView(QWidget):  # base-exempt: an MVC view root, not a surface\n"
        "    pass\n",
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert findings == []


def test_base_exempt_marker_without_a_reason_does_not_waive(tmp_path: Path):
    """Deliberately stricter than `token-exempt`/`card-exempt`, which match on
    presence alone — see `_BASE_EXEMPT_RE`'s note. A bare marker is an
    exemption nobody justified, so it does not count as one."""
    _write(
        tmp_path / "sneaky.py",
        "class Sneaky(QWidget):  # base-exempt:\n    pass\n",
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QWidget"


def test_token_exempt_does_not_silence_the_base_class_guard(tmp_path: Path):
    """The two markers are separate on purpose: one axis is a literal colour
    value, the other a base class. An exemption reviewed for one must not
    wave the other through."""
    _write(
        tmp_path / "wrong_marker.py",
        "class MyPanel(QFrame):  # token-exempt: migration leftover\n    pass\n",
    )

    findings = find_bare_qt_base_widgets(tmp_path)

    assert len(findings) == 1
    assert findings[0].qt_base == "QFrame"


def test_a_consuming_apps_palette_module_can_be_named_as_a_colour_source(
    tmp_path: Path,
):
    """EPIC-007D: an app's colours live in its own palette module, not in a
    file called `style.py`. Before this, that module was reported for
    containing the very tokens it exists to define, so "zero findings" was
    unreachable for any consumer."""
    _write(tmp_path / "palette.py", 'BG_CARD = "#111318"\n')
    _write(tmp_path / "screen.py", 'w.setStyleSheet("background: #111318;")\n')

    findings = find_inline_stylesheets(tmp_path, colour_source_names=("palette.py",))

    assert len(findings) == 1
    assert findings[0].file.name == "screen.py"


def test_naming_a_colour_source_does_not_excuse_a_lookalike(tmp_path: Path):
    _write(tmp_path / "palette_helpers.py", 'BG = "#111318"\n')

    findings = find_inline_stylesheets(tmp_path, colour_source_names=("palette.py",))

    assert len(findings) == 1


def test_style_py_is_still_skipped_without_being_named(tmp_path: Path):
    """The package's own convention keeps working for callers that pass
    nothing — this parameter is additive, not a replacement."""
    _write(tmp_path / "style.py", 'QSS = "color: #ffffff;"\n')

    assert find_inline_stylesheets(tmp_path) == []
