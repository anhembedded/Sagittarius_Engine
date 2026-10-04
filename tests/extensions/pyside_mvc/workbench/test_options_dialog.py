"""Tools → Options: Apply only with edits, OK only when valid, Cancel reverts
(`EPIC-008E`; Microsoft `win-dialog-box`)."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QLabel, QLineEdit, QListWidget, QWidget

from sagittarius_engine.extensions.pyside_mvc import IOptionsPage, OptionsDialog

_Buttons = QDialogButtonBox.StandardButton


class _TextPage:
    """An `IOptionsPage` over one line edit, with a saved value."""

    def __init__(self, title: str, saved: str) -> None:
        self._title = title
        self.saved = saved
        self.edit = QLineEdit(saved)
        self.applied = 0
        self._listener: Callable[[], None] | None = None
        self.edit.textEdited.connect(self._edited)

    @property
    def title(self) -> str:
        return self._title

    def widget(self) -> QWidget:
        return self.edit

    def apply(self) -> None:
        self.saved = self.edit.text()
        self.applied += 1

    def revert(self) -> None:
        self.edit.setText(self.saved)

    def is_dirty(self) -> bool:
        return self.edit.text() != self.saved

    def validation_message(self) -> str | None:
        return None if self.edit.text().strip() else "the value is empty"

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        self._listener = listener

    def _edited(self, text: str) -> None:
        if self._listener is not None:
            self._listener()


@pytest.fixture
def pages() -> tuple[_TextPage, _TextPage]:
    return _TextPage("General", "a"), _TextPage("Data", "b")


@pytest.fixture
def dialog(qtbot, pages) -> OptionsDialog:
    page_list: list[IOptionsPage] = list(pages)
    options = OptionsDialog(page_list)
    qtbot.addWidget(options)
    return options


def _button(dialog: OptionsDialog, which: QDialogButtonBox.StandardButton):
    box = dialog.findChild(QDialogButtonBox)
    assert box is not None
    return box.button(which)


def test_it_is_titled_options_and_lists_the_sections(dialog: OptionsDialog) -> None:
    assert dialog.windowTitle() == "Options"
    assert _button(dialog, _Buttons.Ok) is not None
    assert _button(dialog, _Buttons.Cancel) is not None


def test_apply_is_enabled_only_while_a_page_has_edits(qtbot, dialog, pages) -> None:
    general, _ = pages
    assert not _button(dialog, _Buttons.Apply).isEnabled()

    qtbot.keyClicks(general.edit, "x")
    assert _button(dialog, _Buttons.Apply).isEnabled()

    _button(dialog, _Buttons.Apply).click()
    assert general.saved == "ax"
    assert not _button(dialog, _Buttons.Apply).isEnabled()
    assert dialog.result() != dialog.DialogCode.Accepted, (
        "Apply never closes the dialog"
    )


def test_ok_is_disabled_and_the_reason_shown_while_a_page_is_invalid(
    qtbot, dialog, pages
) -> None:
    general, _ = pages
    general.edit.selectAll()
    qtbot.keyClick(general.edit, Qt.Key.Key_Backspace)

    assert not _button(dialog, _Buttons.Ok).isEnabled()
    message = dialog.findChild(QLabel, "workbench::options::message")
    assert message is not None and message.text() == "General: the value is empty"


def test_ok_applies_only_the_dirty_pages(qtbot, dialog, pages) -> None:
    general, data = pages
    qtbot.keyClicks(general.edit, "x")

    _button(dialog, _Buttons.Ok).click()

    assert general.applied == 1 and data.applied == 0
    assert dialog.result() == dialog.DialogCode.Accepted


@pytest.mark.parametrize("close_by", ["cancel", "escape", "title_bar"])
def test_every_way_out_but_ok_reverts_every_page(
    qtbot, dialog, pages, close_by
) -> None:
    general, data = pages
    dialog.show()
    qtbot.keyClicks(general.edit, "x")
    qtbot.keyClicks(data.edit, "y")

    if close_by == "cancel":
        _button(dialog, _Buttons.Cancel).click()
    elif close_by == "escape":
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    else:
        dialog.close()

    assert (general.edit.text(), data.edit.text()) == ("a", "b")
    assert general.applied == 0 and data.applied == 0


class _UnwritablePage(_TextPage):
    """A page whose write fails: `apply()` keeps the edit and stays dirty,
    as an app page does when its file cannot be written."""

    def apply(self) -> None:
        self.applied += 1


def test_ok_keeps_the_dialog_open_while_a_page_could_not_apply(qtbot) -> None:
    """`BUG-018`: OK applied every page and closed regardless, so a page that
    could not write its file reported the failure in a dialog that had just
    closed, and the user believed OK had saved."""
    good, failing = _TextPage("General", "a"), _UnwritablePage("Data", "b")
    dialog = OptionsDialog([good, failing])
    qtbot.addWidget(dialog)
    dialog.show()
    good.edit.setText("A")
    good.edit.textEdited.emit("A")
    failing.edit.setText("B")
    failing.edit.textEdited.emit("B")

    qtbot.mouseClick(_button(dialog, _Buttons.Ok), Qt.MouseButton.LeftButton)

    assert dialog.isVisible()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert (good.saved, failing.applied) == ("A", 1)
    assert dialog.findChild(QListWidget).currentRow() == 1
    message = dialog.findChild(QLabel, "workbench::options::message")
    assert message is not None
    assert message.isVisibleTo(dialog)
    assert message.text() == "Data: the changes could not be applied."
