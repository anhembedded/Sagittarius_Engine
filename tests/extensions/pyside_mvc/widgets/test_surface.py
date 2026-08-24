"""Tests for `widgets.surface` — `Surface`/`Panel`/`Card`."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QFrame, QLabel

from sagittarius_engine.extensions.pyside_mvc.widgets import Card, Panel, Surface


def test_surface_itself_is_abstract(qtbot):
    with pytest.raises(TypeError, match="Surface is abstract"):
        Surface()


def test_panel_constructs_as_a_qframe(qtbot):
    panel = Panel()
    qtbot.addWidget(panel)

    assert isinstance(panel, QFrame)
    assert panel.styleSheet() != ""


def test_panel_body_layout_accepts_content(qtbot):
    panel = Panel()
    qtbot.addWidget(panel)

    label = QLabel("hello")
    panel.body_layout.addWidget(label)

    assert panel.body_layout.count() == 1


def test_card_exposes_title_and_it_is_mutable(qtbot):
    card = Card("Sync Controls")
    qtbot.addWidget(card)

    assert card.title == "Sync Controls"

    card.title = "Renamed"
    assert card.title == "Renamed"


def test_card_header_actions_is_a_separate_layout_from_body(qtbot):
    card = Card("Log")
    qtbot.addWidget(card)

    from PySide6.QtWidgets import QPushButton

    button = QPushButton("Clear")
    card.header_actions.addWidget(button)

    # header content must not land in body_layout, which is where a
    # subclass/consumer's own content goes.
    assert card.body_layout.count() == 1  # just the header widget itself
    assert card.header_actions.count() == 1


def test_card_is_concrete_not_abstract(qtbot):
    # Unlike Surface, Card is directly usable — no type(self) is Card guard.
    card = Card("Standalone")
    qtbot.addWidget(card)
    assert card.title == "Standalone"


def test_setenabled_cascades_to_body_layout_children(qtbot):
    from PySide6.QtWidgets import QPushButton

    card = Card("X")
    qtbot.addWidget(card)
    button = QPushButton("Action")
    card.body_layout.addWidget(button)

    card.setEnabled(False)

    assert button.isEnabled() is False


def test_on_enabled_changed_hook_fires_on_setenabled(qtbot):
    calls: list[bool] = []

    class TrackingPanel(Panel):
        def _on_enabled_changed(self, enabled: bool) -> None:
            calls.append(enabled)

    panel = TrackingPanel()
    qtbot.addWidget(panel)

    panel.setEnabled(False)
    panel.setEnabled(True)

    assert calls == [False, True]
