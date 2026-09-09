"""Tests for `AppRail` (`EPIC-008A`) — the indexed section nav with
per-row signal-count badges `reference/handoff.md` §6 specifies.

Uses the shared standalone-`QQmlEngine`/distinguishable-`Theme` helper
(`_standalone_qml_theme.py`) — see that module's own docstring for why the
shared `get_theme_bridge()` singleton every other kit test uses cannot
tell `accent`/`accent200`/`accent900`/`dangerFill` apart from one another.

Every test collects the rail's whole item tree with `collect_all_items()`
exactly ONCE and keeps that list alive for the test's duration, rather than
searching (`find_visual_child()`) more than once per test — see that
function's own docstring for the "Internal C++ object already deleted"
crash a second independent search over the same `Repeater`-containing tree
reproduced.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Q_ARG, QMetaObject, QObject, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlComponent

from tests.extensions.pyside_mvc._standalone_qml_theme import (
    collect_all_items,
    load_qml_fixture,
    standalone_theme_engine,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_rail(engine):
    return load_qml_fixture(engine, _FIXTURES_DIR / "app_rail_probe.qml")


def _rows_by_id(all_items) -> dict[str, QObject]:
    rows = {}
    for item in all_items:
        name = item.objectName()
        if name.startswith("railRow_"):
            rows[name.removeprefix("railRow_")] = item
    return rows


def test_renders_one_row_per_section_with_index_and_label(qtbot):
    engine, theme, merged = standalone_theme_engine()
    rail = _load_rail(engine)
    qtbot.wait(1)
    all_items = collect_all_items(rail)
    rows = _rows_by_id(all_items)

    for expected_index, (section_id, label) in enumerate(
        [("overview", "Overview"), ("events", "Events"), ("signals", "Signals")],
        start=1,
    ):
        row = rows[section_id]
        # Everything inside an already-retained row is a normal static
        # declaration -- plain `findChild()` works fine here (only
        # crossing the Repeater boundary above needed `collect_all_items`).
        index_text = row.findChild(QObject, "railRowIndex")
        label_text = row.findChild(QObject, "railRowLabel")
        assert index_text.property("text") == f"{expected_index:02d}"
        assert label_text.property("text") == label


def test_active_row_is_tinted_and_uses_the_active_text_colour(qtbot):
    engine, theme, merged = standalone_theme_engine()
    rail = _load_rail(engine)
    qtbot.wait(1)
    rows = _rows_by_id(collect_all_items(rail))

    active_row = rows["events"]
    inactive_row = rows["overview"]

    assert QColor(active_row.property("color")) == QColor(merged["accent200"])
    assert QColor(inactive_row.property("color")) == QColor("transparent")

    active_label = active_row.findChild(QObject, "railRowLabel")
    inactive_label = inactive_row.findChild(QObject, "railRowLabel")
    assert QColor(active_label.property("color")) == QColor(merged["accent900"])
    assert QColor(inactive_label.property("color")) == QColor(merged["textPrimary"])


def test_changing_active_section_id_moves_the_highlight(qtbot):
    engine, theme, merged = standalone_theme_engine()
    rail = _load_rail(engine)
    qtbot.wait(1)
    rows = _rows_by_id(collect_all_items(rail))

    rail.setProperty("activeSectionId", "signals")

    assert QColor(rows["signals"].property("color")) == QColor(merged["accent200"])
    assert QColor(rows["events"].property("color")) == QColor("transparent")


def test_badge_is_visible_only_for_a_positive_badge_count(qtbot):
    engine, theme, merged = standalone_theme_engine()
    rail = _load_rail(engine)
    qtbot.wait(1)
    rows = _rows_by_id(collect_all_items(rail))

    overview_badge = rows["overview"].findChild(QObject, "railRowBadge")
    events_badge = rows["events"].findChild(QObject, "railRowBadge")

    assert overview_badge.property("visible") is False
    assert events_badge.property("visible") is True


def test_badge_shows_the_exact_count_never_a_generic_indicator(qtbot):
    """`reference/handoff.md`'s own "a running count... is a first-class
    number, not something the user has to count themselves" principle,
    applied to the rail: the badge must show 10, not a dot or a "9+"."""
    engine, theme, merged = standalone_theme_engine()
    rail = _load_rail(engine)
    qtbot.wait(1)
    rows = _rows_by_id(collect_all_items(rail))

    badge = rows["signals"].findChild(QObject, "railRowBadge")
    badge_label = badge.findChild(QObject)
    assert badge_label.property("text") == "10"


def test_selecting_a_row_emits_section_selected_with_its_id(qtbot):
    """Via the component's own `_selectRow(id)` function — invokable with a
    `QVariant` argument from Python the way `MouseArea.clicked(mouse)`
    cannot be (see `LiveConnectionBand`'s own tests for that limitation).
    The `MouseArea.onClicked` binding that calls it is reviewed by
    inspection."""
    engine, theme, merged = standalone_theme_engine()
    rail = _load_rail(engine)
    qtbot.wait(1)

    received = []
    rail.sectionSelected.connect(received.append)

    assert QMetaObject.invokeMethod(rail, "_selectRow", Q_ARG("QVariant", "signals"))

    assert received == ["signals"]


def test_footer_content_is_reparented_under_the_rail(qtbot):
    engine, theme, merged = standalone_theme_engine()
    rail = _load_rail(engine)
    qtbot.wait(1)

    footer_qml = """
    import QtQuick
    Text { objectName: "myFooter"; text: "Read-only." }
    """
    component = QQmlComponent(engine)
    component.setData(footer_qml.encode(), QUrl())
    footer = component.create()
    assert component.errors() == []
    footer.setParent(engine)

    rail.setProperty("footer", footer)

    all_items = collect_all_items(rail)
    names = [item.objectName() for item in all_items]
    assert "railFooterSlot" in names
    assert "myFooter" in names
