"""Tests for the gallery-coverage guard — the enforcement mechanism behind
ui-architecture.md §6.2's "every kit component must be reachable from a
single runnable gallery".

Includes the live check against the real kit, which is the one that keeps
the rule true rather than merely stated. It found DateTimePicker missing on
its very first run (registered in qmldir since before the gallery existed,
never shown) — the exact decay it exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

from sagittarius_engine.extensions.pyside_mvc.kit.gallery_coverage_guard import (
    DEFAULT_EXEMPT_TYPES,
    find_types_missing_from_gallery,
    format_findings,
    registered_types,
)

_QML_KIT_DIR = (
    Path(__file__).resolve().parents[3]
    / "sagittarius_engine"
    / "extensions"
    / "pyside_mvc"
    / "Sagittarius"
    / "UI"
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---- The live check ---------------------------------------------------


def test_every_registered_kit_component_appears_in_the_real_gallery():
    findings = find_types_missing_from_gallery(
        _QML_KIT_DIR / "qmldir", _QML_KIT_DIR / "Gallery" / "Gallery.qml"
    )

    assert findings == [], format_findings(findings)


# ---- registered_types() ------------------------------------------------


def test_registered_types_skips_the_module_header(tmp_path: Path):
    qmldir = _write(
        tmp_path / "qmldir",
        "module Sagittarius.UI\nAppModal 1.0 AppModal/AppModal.qml\n",
    )

    assert registered_types(qmldir) == ["AppModal"]


def test_registered_types_preserves_declaration_order(tmp_path: Path):
    qmldir = _write(
        tmp_path / "qmldir",
        "module X\nZebra 1.0 Zebra/Zebra.qml\nAlpha 1.0 Alpha/Alpha.qml\n",
    )

    assert registered_types(qmldir) == ["Zebra", "Alpha"]


def test_registered_types_ignores_blank_and_comment_lines(tmp_path: Path):
    qmldir = _write(
        tmp_path / "qmldir",
        "module X\n\n# a comment\nAppModal 1.0 AppModal/AppModal.qml\n\n",
    )

    assert registered_types(qmldir) == ["AppModal"]


# ---- find_types_missing_from_gallery() ---------------------------------


def test_reports_a_registered_type_absent_from_the_gallery(tmp_path: Path):
    qmldir = _write(
        tmp_path / "qmldir", "module X\nAppModal 1.0 AppModal/AppModal.qml\n"
    )
    gallery = _write(tmp_path / "Gallery.qml", "import QtQuick\nItem {}\n")

    findings = find_types_missing_from_gallery(qmldir, gallery, frozenset())

    assert [f.type_name for f in findings] == ["AppModal"]


def test_accepts_a_type_that_is_declared_in_the_gallery(tmp_path: Path):
    qmldir = _write(
        tmp_path / "qmldir", "module X\nAppModal 1.0 AppModal/AppModal.qml\n"
    )
    gallery = _write(
        tmp_path / "Gallery.qml", "import QtQuick\nItem { AppModal { id: m } }\n"
    )

    assert find_types_missing_from_gallery(qmldir, gallery, frozenset()) == []


def test_a_mention_in_a_comment_does_not_count_as_coverage(tmp_path: Path):
    """The check must require a real declaration. A component described in
    prose but never instantiated is exactly the gap this guard closes."""
    qmldir = _write(
        tmp_path / "qmldir", "module X\nAppModal 1.0 AppModal/AppModal.qml\n"
    )
    gallery = _write(
        tmp_path / "Gallery.qml",
        "import QtQuick\n// TODO: show AppModal here\nItem {}\n",
    )

    assert [
        f.type_name
        for f in find_types_missing_from_gallery(qmldir, gallery, frozenset())
    ] == ["AppModal"]


def test_a_longer_type_name_does_not_satisfy_a_shorter_one(tmp_path: Path):
    """`StatefulButton {` must not be read as covering a hypothetical
    `Button` — the word boundary is load-bearing, and the kit really does
    contain names where one is a suffix of another."""
    qmldir = _write(tmp_path / "qmldir", "module X\nButton 1.0 Button/Button.qml\n")
    gallery = _write(
        tmp_path / "Gallery.qml", "import QtQuick\nItem { StatefulButton {} }\n"
    )

    assert [
        f.type_name
        for f in find_types_missing_from_gallery(qmldir, gallery, frozenset())
    ] == ["Button"]


def test_exempt_types_are_not_required_in_the_gallery(tmp_path: Path):
    qmldir = _write(
        tmp_path / "qmldir", "module X\nBaseCard 1.0 BaseCard/BaseCard.qml\n"
    )
    gallery = _write(tmp_path / "Gallery.qml", "import QtQuick\nItem {}\n")

    assert find_types_missing_from_gallery(qmldir, gallery) == []


def test_base_card_is_exempt_by_default():
    """Pinned deliberately: BaseCard has no standalone appearance — it is
    shown through every card deriving from it. If this set ever grows, it
    should be a design decision visible in a diff, not a quiet addition."""
    assert DEFAULT_EXEMPT_TYPES == frozenset({"BaseCard"})


def test_format_findings_names_the_type_and_both_files(tmp_path: Path):
    qmldir = _write(
        tmp_path / "qmldir", "module X\nAppModal 1.0 AppModal/AppModal.qml\n"
    )
    gallery = _write(tmp_path / "Gallery.qml", "import QtQuick\nItem {}\n")

    rendered = format_findings(
        find_types_missing_from_gallery(qmldir, gallery, frozenset())
    )

    assert "AppModal" in rendered
    assert str(qmldir) in rendered
    assert str(gallery) in rendered
