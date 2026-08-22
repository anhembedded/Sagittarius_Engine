"""Tests for the anti-Rectangle-as-styled-card QML static guard
(EPIC-001C) — the enforcement mechanism for the gap `raw_primitive_guard`
deliberately left open: a screen re-implementing `BaseCard`'s own
background+border+radius recipe on a bare `Rectangle` instead of actually
deriving `BaseCard`."""

from __future__ import annotations

from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc.kit import find_rectangle_as_styled_cards
from sagittarius_engine.extensions.pyside_mvc.kit.rectangle_card_guard import (
    format_findings,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_flags_a_rectangle_with_the_full_card_recipe(tmp_path: Path):
    _write(
        tmp_path / "Screen.qml",
        "Rectangle {\n"
        "    color: Theme.bgCard\n"
        "    border.color: Theme.border\n"
        "    border.width: 1\n"
        "    radius: 8\n"
        "}\n",
    )

    findings = find_rectangle_as_styled_cards(tmp_path)

    assert len(findings) == 1
    assert findings[0].line_number == 1


def test_flags_with_border_width_alone_no_border_color(tmp_path: Path):
    """Either border.color or border.width is enough to count as "has a
    border" — a card need not set both to look like one."""
    _write(
        tmp_path / "Screen.qml",
        "Rectangle {\n    color: Theme.bgCard\n    border.width: 1\n    radius: 8\n}\n",
    )

    assert len(find_rectangle_as_styled_cards(tmp_path)) == 1


def test_does_not_flag_a_plain_divider(tmp_path: Path):
    """color + a thin height, no border/radius — a real divider, not a
    card."""
    _write(
        tmp_path / "Screen.qml",
        "Rectangle {\n    color: Theme.border\n    height: 1\n    Layout.fillWidth: true\n}\n",
    )

    assert find_rectangle_as_styled_cards(tmp_path) == []


def test_does_not_flag_a_transparent_spacer(tmp_path: Path):
    _write(
        tmp_path / "Screen.qml",
        'Rectangle {\n    color: "transparent"\n    Layout.fillWidth: true\n}\n',
    )

    assert find_rectangle_as_styled_cards(tmp_path) == []


def test_does_not_flag_radius_only_icon_badge(tmp_path: Path):
    """Rounded, coloured, but no border — two of three, not the full
    recipe."""
    _write(
        tmp_path / "Screen.qml",
        "Rectangle {\n    color: Theme.accent\n    radius: 4\n    width: 8\n    height: 8\n}\n",
    )

    assert find_rectangle_as_styled_cards(tmp_path) == []


def test_does_not_flag_basecard_itself(tmp_path: Path):
    """`BaseCard { ... }` is the correct way to get this shape — the guard
    only matches a literal `Rectangle` root, never `BaseCard`."""
    _write(
        tmp_path / "Screen.qml",
        "BaseCard {\n    color: Theme.bgCard\n    border.color: Theme.border\n"
        "    border.width: 1\n    radius: 8\n}\n",
    )

    assert find_rectangle_as_styled_cards(tmp_path) == []


def test_does_not_misattribute_a_nested_rectangles_properties_to_its_parent(
    tmp_path: Path,
):
    """The whole reason this guard needs block-scoped parsing instead of a
    per-line regex: the outer Rectangle only sets `color` itself; the card
    recipe's other two properties belong to an unrelated nested child and
    must not count toward the outer block."""
    _write(
        tmp_path / "Screen.qml",
        "Rectangle {\n"
        "    color: Theme.surface\n"
        "    Rectangle {\n"
        "        border.color: Theme.border\n"
        "        border.width: 1\n"
        "        radius: 2\n"
        "    }\n"
        "}\n",
    )

    assert find_rectangle_as_styled_cards(tmp_path) == []


def test_still_flags_a_nested_rectangle_that_independently_matches(tmp_path: Path):
    """A non-matching outer Rectangle must not shadow a nested one that
    genuinely reimplements the card recipe on its own."""
    _write(
        tmp_path / "Screen.qml",
        "Rectangle {\n"
        "    color: Theme.surface\n"
        "    Rectangle {\n"
        "        color: Theme.bgCard\n"
        "        border.color: Theme.border\n"
        "        border.width: 1\n"
        "        radius: 8\n"
        "    }\n"
        "}\n",
    )

    findings = find_rectangle_as_styled_cards(tmp_path)

    assert len(findings) == 1
    assert findings[0].line_number == 3


def test_ignores_comment_only_lines(tmp_path: Path):
    _write(
        tmp_path / "Screen.qml",
        "Rectangle {\n"
        "    // color: Theme.bgCard\n"
        "    // border.color: Theme.border\n"
        "    // radius: 8\n"
        "}\n",
    )

    assert find_rectangle_as_styled_cards(tmp_path) == []


def test_exempt_marker_on_header_line_skips_flagging(tmp_path: Path):
    _write(
        tmp_path / "Screen.qml",
        "Rectangle {  // card-exempt: documented one-off, see docstring\n"
        "    color: Theme.bgCard\n"
        "    border.color: Theme.border\n"
        "    radius: 8\n"
        "}\n",
    )

    assert find_rectangle_as_styled_cards(tmp_path) == []


def test_exempt_dirs_are_skipped_entirely(tmp_path: Path):
    """Matches `find_raw_primitives`'/`find_literal_colors`' identical
    contract: the kit's own directory (where a primitive like
    `FieldBackground.qml` legitimately carries this exact shape) is exempted
    by the caller, not hardcoded here."""
    kit_dir = _write(
        tmp_path / "Sagittarius" / "UI" / "FieldBackground.qml",
        "Rectangle {\n    color: Theme.stateIdleBg\n    border.color: Theme.border\n"
        "    radius: 6\n}\n",
    ).parent
    _write(
        tmp_path / "screens" / "Screen.qml",
        "Rectangle {\n    color: Theme.bgCard\n    border.color: Theme.border\n"
        "    radius: 8\n}\n",
    )

    findings = find_rectangle_as_styled_cards(tmp_path, exempt_dirs=[kit_dir])

    assert len(findings) == 1
    assert "screens" in str(findings[0].file)


def test_finds_multiple_across_files_sorted_by_path(tmp_path: Path):
    card_body = "Rectangle {\n    color: Theme.bgCard\n    border.color: Theme.border\n    radius: 8\n}\n"
    _write(tmp_path / "b_screen.qml", card_body)
    _write(tmp_path / "a_screen.qml", card_body)

    findings = find_rectangle_as_styled_cards(tmp_path)

    assert [f.file.name for f in findings] == ["a_screen.qml", "b_screen.qml"]


def test_format_findings_includes_file_and_line(tmp_path: Path):
    qml = _write(
        tmp_path / "Screen.qml",
        "Rectangle {\n    color: Theme.bgCard\n    border.color: Theme.border\n"
        "    radius: 8\n}\n",
    )

    findings = find_rectangle_as_styled_cards(tmp_path)
    rendered = format_findings(findings)

    assert str(qml) in rendered
    assert "1 Rectangle block" in rendered
