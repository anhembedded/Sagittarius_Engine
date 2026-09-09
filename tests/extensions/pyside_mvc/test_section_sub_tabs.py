"""Tests for `SectionSubTabs` (`EPIC-008B`) — the sub-tab row
`reference/handoff.md` §6 specifies, promoted once three screens
(Overview, Events & wiring, Container) had each independently built the
identical row.

Uses the shared standalone-`QQmlEngine`/distinguishable-`Theme` helper
(`_standalone_qml_theme.py`) — see that module's own docstring for why the
shared `get_theme_bridge()` singleton every other kit test uses cannot
tell `accent`/`accent900`/`muted` apart from one another.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Q_ARG, QMetaObject, QObject
from PySide6.QtGui import QColor

from tests.extensions.pyside_mvc._standalone_qml_theme import (
    collect_all_items,
    load_qml_fixture,
    standalone_theme_engine,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_sub_tabs(engine):
    return load_qml_fixture(engine, _FIXTURES_DIR / "section_sub_tabs_probe.qml")


def _tabs_by_id(all_items) -> dict[str, QObject]:
    tabs = {}
    for item in all_items:
        name = item.objectName()
        if name.startswith("subTab_"):
            tabs[name.removeprefix("subTab_")] = item
    return tabs


def test_renders_one_tab_per_entry_with_label_and_count(qtbot):
    engine, theme, merged = standalone_theme_engine()
    sub_tabs = _load_sub_tabs(engine)
    qtbot.wait(1)
    tabs = _tabs_by_id(collect_all_items(sub_tabs))

    for tab_id, label, count in [
        ("all", "All", "25"),
        ("undeclared", "Undeclared", "2"),
    ]:
        tab = tabs[tab_id]
        label_text = tab.findChild(QObject, "subTabLabel")
        count_text = tab.findChild(QObject, "subTabCount")
        assert label_text.property("text") == label
        assert count_text.property("text") == count


def test_the_active_tab_uses_the_active_colour_the_inactive_one_does_not(qtbot):
    engine, theme, merged = standalone_theme_engine()
    sub_tabs = _load_sub_tabs(engine)
    qtbot.wait(1)
    tabs = _tabs_by_id(collect_all_items(sub_tabs))

    active_label = tabs["all"].findChild(QObject, "subTabLabel")
    inactive_label = tabs["undeclared"].findChild(QObject, "subTabLabel")
    assert QColor(active_label.property("color")) == QColor(merged["accent900"])
    assert QColor(inactive_label.property("color")) == QColor(merged["muted"])


def test_changing_the_active_tab_id_moves_the_highlight(qtbot):
    engine, theme, merged = standalone_theme_engine()
    sub_tabs = _load_sub_tabs(engine)
    qtbot.wait(1)
    tabs = _tabs_by_id(collect_all_items(sub_tabs))

    sub_tabs.setProperty("activeTabId", "undeclared")

    now_active_label = tabs["undeclared"].findChild(QObject, "subTabLabel")
    now_inactive_label = tabs["all"].findChild(QObject, "subTabLabel")
    assert QColor(now_active_label.property("color")) == QColor(merged["accent900"])
    assert QColor(now_inactive_label.property("color")) == QColor(merged["muted"])


def test_selecting_a_tab_emits_tab_selected_with_its_id(qtbot):
    """Via the component's own `_selectTab(id)` function — invokable with a
    `QVariant` argument the way `MouseArea.clicked(mouse)` cannot be (see
    `AppRail`'s own tests for the same reasoning). The `MouseArea.onClicked`
    binding that calls it is reviewed by inspection."""
    engine, theme, merged = standalone_theme_engine()
    sub_tabs = _load_sub_tabs(engine)
    qtbot.wait(1)

    received = []
    sub_tabs.tabSelected.connect(received.append)

    assert QMetaObject.invokeMethod(
        sub_tabs, "_selectTab", Q_ARG("QVariant", "undeclared")
    )

    assert received == ["undeclared"]
