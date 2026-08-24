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
