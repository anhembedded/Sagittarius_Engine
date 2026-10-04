"""The safe answer is the default, and the answers are verbs (`EPIC-008C`;
Microsoft `mess-confirm`)."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ActionConfirmation,
    build_confirmation_box,
)

_STOP = ActionConfirmation(
    title="Emergency stop",
    consequence="Every open order is cancelled and live trading turns off.",
    accept_text="Stop everything",
)


def test_the_reject_answer_is_the_default_and_the_escape(qtbot) -> None:
    box, accept = build_confirmation_box(None, _STOP)
    qtbot.addWidget(box)

    default = box.defaultButton()
    assert default is not None and default is not accept
    assert default.text() == "Cancel"
    assert box.escapeButton() is default


def test_the_dialog_names_the_consequence_and_the_verb(qtbot) -> None:
    box, accept = build_confirmation_box(None, _STOP)
    qtbot.addWidget(box)

    assert box.windowTitle() == "Emergency stop"
    assert "Every open order is cancelled" in box.text()
    assert accept.text() == "Stop everything"
    assert box.buttonRole(accept) is QMessageBox.ButtonRole.AcceptRole
