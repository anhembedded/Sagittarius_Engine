"""Tests for `widgets.overlay.Overlay`."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton

from sagittarius_engine.extensions.pyside_mvc.widgets import Overlay


class _ConfirmOverlay(Overlay):
    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.confirm_button = QPushButton("Confirm")
        row.addWidget(self.cancel_button)
        row.addWidget(self.confirm_button)
        return row


def test_overlay_itself_is_abstract(qtbot):
    with pytest.raises(TypeError, match="Overlay is abstract"):
        Overlay("title")


def test_subclass_constructs_as_a_qdialog(qtbot):
    overlay = _ConfirmOverlay("Confirm delete")
    qtbot.addWidget(overlay)

    assert isinstance(overlay, QDialog)
    assert overlay.isModal() is True
    assert overlay.styleSheet() != ""


def test_title_and_subtitle_properties(qtbot):
    overlay = _ConfirmOverlay("Title", "Subtitle text")
    qtbot.addWidget(overlay)

    assert overlay.title == "Title"
    assert overlay.subtitle == "Subtitle text"


def test_subtitle_defaults_to_hidden_when_empty(qtbot):
    overlay = _ConfirmOverlay("Title only")
    qtbot.addWidget(overlay)

    assert overlay._subtitle_label.isVisibleTo(overlay) is False


def test_subtitle_becomes_visible_when_set(qtbot):
    overlay = _ConfirmOverlay("Title")
    qtbot.addWidget(overlay)

    overlay.subtitle = "Now visible"

    # isVisible() would stay False here regardless — it also requires the
    # top-level dialog itself to have been shown, which this fast unit
    # test deliberately never does. isVisibleTo(overlay) reflects the
    # requested visibility relative to its own parent instead (verified
    # empirically: a freshly setVisible(True) child of an unshown QDialog
    # reports isVisible()=False but isVisibleTo(parent)=True).
    assert overlay._subtitle_label.isVisibleTo(overlay) is True


def test_build_buttons_result_is_wired_into_the_dialog(qtbot):
    overlay = _ConfirmOverlay("Confirm")
    qtbot.addWidget(overlay)

    assert overlay.cancel_button.text() == "Cancel"
    assert overlay.confirm_button.text() == "Confirm"


def test_body_layout_accepts_content(qtbot):
    from PySide6.QtWidgets import QLabel

    overlay = _ConfirmOverlay("Confirm")
    qtbot.addWidget(overlay)

    overlay.body_layout.addWidget(QLabel("Are you sure?"))

    assert overlay.body_layout.count() == 1


def test_default_build_buttons_is_an_empty_row(qtbot):
    class _NoButtonsOverlay(Overlay):
        pass

    overlay = _NoButtonsOverlay("No buttons")
    qtbot.addWidget(overlay)
    # Constructs without error, matching the "not @abstractmethod" call in
    # Overlay._build_buttons()'s own docstring.
