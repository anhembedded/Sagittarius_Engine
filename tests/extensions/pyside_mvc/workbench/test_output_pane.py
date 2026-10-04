"""One Output dock, a channel per source (`EPIC-008E`)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import QListView, QMainWindow, QWidget

from sagittarius_engine.extensions.pyside_mvc import (
    LogListModel,
    OutputChannel,
    OutputPane,
)


@pytest.fixture
def pane(qtbot) -> OutputPane:
    output = OutputPane()
    qtbot.addWidget(output)
    return output


def _lines(pane: OutputPane) -> QListView:
    view = pane.findChild(QListView, "workbench::output::lines")
    assert view is not None
    return view


def _channel(channel_id: str, *messages: str) -> OutputChannel:
    model = LogListModel()
    for message in messages:
        model.append(message)
    return OutputChannel(channel_id, channel_id.title(), model)


def test_it_is_a_dock_titled_output(pane: OutputPane) -> None:
    assert pane.windowTitle() == "Output"
    assert pane.objectName() == "workbench::output"


def test_the_first_channel_shows_and_another_can_be_chosen(pane: OutputPane) -> None:
    pane.add_channel(_channel("sync", "fetched 500 candles"))
    pane.add_channel(_channel("bots", "grid started", "order placed"))
    assert _lines(pane).model().rowCount() == 1

    pane.show_channel("bots")

    assert _lines(pane).model().rowCount() == 2
    assert "order placed" in str(_lines(pane).model().index(1, 0).data())


def test_copy_takes_every_line_or_only_the_selected_ones(pane: OutputPane) -> None:
    pane.add_channel(_channel("bots", "grid started", "order placed"))

    everything = pane.copy_lines()
    assert everything.count("\n") == 1
    assert QGuiApplication.clipboard().text() == everything

    view = _lines(pane)
    view.selectionModel().select(
        view.model().index(1, 0), QItemSelectionModel.SelectionFlag.Select
    )
    assert pane.copy_lines().endswith("order placed")
    assert "grid started" not in pane.copy_lines()


def test_clear_empties_the_shown_channel_only(pane: OutputPane) -> None:
    sync, bots = _channel("sync", "a"), _channel("bots", "b")
    pane.add_channel(sync)
    pane.add_channel(bots)

    pane.clear_action.trigger()

    assert sync.model.rowCount() == 0 and bots.model.rowCount() == 1


def test_a_channel_added_twice_is_refused(pane: OutputPane) -> None:
    pane.add_channel(_channel("sync"))
    with pytest.raises(ValueError, match="already added"):
        pane.add_channel(_channel("sync"))


def test_the_pane_copy_and_an_edit_copy_coexist_on_the_copy_key(qtbot) -> None:
    """Review of PR #225: a second Ctrl+C shortcut made both ambiguous."""
    window = QMainWindow()
    qtbot.addWidget(window)
    edit_copies: list[bool] = []
    edit_copy = QAction("&Copy", window)
    edit_copy.setShortcut(QKeySequence.StandardKey.Copy)
    edit_copy.triggered.connect(lambda: edit_copies.append(True))
    window.addAction(edit_copy)
    # Takes focus but, unlike a line edit, does not claim Ctrl+C itself.
    elsewhere = QWidget()
    elsewhere.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    window.setCentralWidget(elsewhere)
    pane = OutputPane(window)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, pane)
    pane.add_channel(_channel("sync", "fetched 500 candles"))
    window.show()
    with qtbot.waitActive(window):
        window.activateWindow()
    QGuiApplication.clipboard().setText("")

    _lines(pane).setFocus()
    qtbot.keyClick(_lines(pane), Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)

    assert "fetched 500 candles" in QGuiApplication.clipboard().text()
    assert edit_copies == []

    elsewhere.setFocus()
    qtbot.keyClick(elsewhere, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)

    assert edit_copies == [True]
