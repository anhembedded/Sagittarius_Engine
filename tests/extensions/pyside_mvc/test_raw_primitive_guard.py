"""Tests for the anti-raw-primitive QML static guard (EPIC-001C) — the
enforcement mechanism behind ui-architecture.md §1 ("never author a raw
visual primitive except through the escape hatch")."""

from __future__ import annotations

from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc.kit import find_raw_primitives
from sagittarius_engine.extensions.pyside_mvc.kit.raw_primitive_guard import (
    format_findings,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_finds_a_bare_button_declared_as_a_block_root(tmp_path: Path):
    _write(tmp_path / "Screen.qml", 'Button {\n    text: "Run"\n}\n')

    findings = find_raw_primitives(tmp_path)

    assert len(findings) == 1
    assert findings[0].control == "Button"
    assert findings[0].line_number == 1


def test_finds_a_bare_checkbox(tmp_path: Path):
    _write(tmp_path / "Screen.qml", 'CheckBox {\n    text: "Enabled"\n}\n')

    findings = find_raw_primitives(tmp_path)

    assert len(findings) == 1
    assert findings[0].control == "CheckBox"


def test_does_not_flag_statefulbutton_or_styledcheck(tmp_path: Path):
    """The kit's own replacements must never false-positive as violations
    of themselves — `Button` is a substring of `StatefulButton`, so the
    matcher must anchor on the full token, not do a substring search."""
    _write(
        tmp_path / "Screen.qml",
        'StatefulButton {\n    text: "Run"\n}\nStyledCheck {\n    text: "Enabled"\n}\n',
    )

    assert find_raw_primitives(tmp_path) == []


def test_does_not_flag_a_property_named_button_or_similar(tmp_path: Path):
    _write(
        tmp_path / "Screen.qml",
        "property var lastButtonPressed: null\nsignal buttonClicked(string id)\n",
    )

    assert find_raw_primitives(tmp_path) == []


def test_ignores_comment_only_lines(tmp_path: Path):
    _write(
        tmp_path / "Screen.qml",
        '// example: Button { text: "nope" } is not allowed\n'
        'StatefulButton { text: "Run" }\n',
    )

    assert find_raw_primitives(tmp_path) == []


def test_exempt_dirs_are_skipped_entirely(tmp_path: Path):
    """The kit's own directory (where these controls are legitimately
    constructed from) is meant to be exempted by the caller — this proves
    the mechanism, matching qml_literal_guard's identical contract."""
    kit_dir = _write(
        tmp_path / "Sagittarius" / "UI" / "StatefulButton.qml", "Button {\n}\n"
    ).parent
    _write(tmp_path / "screens" / "Screen.qml", "Button {\n}\n")

    findings = find_raw_primitives(tmp_path, exempt_dirs=[kit_dir])

    assert len(findings) == 1
    assert "screens" in str(findings[0].file)


def test_finds_multiple_across_files_sorted_by_path(tmp_path: Path):
    _write(tmp_path / "b_screen.qml", "CheckBox {\n}\n")
    _write(tmp_path / "a_screen.qml", "Button {\n}\n")

    findings = find_raw_primitives(tmp_path)

    assert [f.file.name for f in findings] == ["a_screen.qml", "b_screen.qml"]


def test_format_findings_includes_file_line_and_control(tmp_path: Path):
    qml = _write(tmp_path / "Screen.qml", "Button {\n}\n")

    findings = find_raw_primitives(tmp_path)
    rendered = format_findings(findings)

    assert str(qml) in rendered
    assert "Button" in rendered
    assert "1 raw Qt Quick Controls primitive" in rendered
