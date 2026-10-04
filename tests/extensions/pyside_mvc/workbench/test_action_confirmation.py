"""The safe answer is the default, and the answers are verbs (`EPIC-008C`;
Microsoft `mess-confirm`)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ActionConfirmation,
    MessageBoxConfirmer,
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


def _answer_when_shown(qtbot, answer) -> None:
    """Acts on the message box once `exec()` has shown it."""

    def act() -> None:
        box = QApplication.activeModalWidget()
        assert isinstance(box, QMessageBox), "no message box was shown"
        answer(box)

    QTimer.singleShot(0, act)


def _press(key: Qt.Key):
    def answer(box: QMessageBox) -> None:
        QTest.keyClick(box, key)

    return answer


def _click_accept(box: QMessageBox) -> None:
    accept = next(b for b in box.buttons() if b.text() == "Stop everything")
    accept.click()


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (_press(Qt.Key.Key_Escape), False),
        (_press(Qt.Key.Key_Return), False),
        (lambda box: box.close(), False),
        (_click_accept, True),
    ],
    ids=["escape", "enter-takes-the-safe-default", "title-bar-close", "accept"],
)
def test_the_real_confirmer_runs_only_on_the_accepting_answer(
    qtbot, answer, expected: bool
) -> None:
    _answer_when_shown(qtbot, answer)

    assert MessageBoxConfirmer().confirm(None, _STOP) is expected
