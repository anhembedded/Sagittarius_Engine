"""One Output pane, a channel per source (`EPIC-008E`).

Visual Studio's Output window: one dock at the bottom, a combo box choosing
which source's lines it shows, and the lines read-only. A module contributes
an `OutputChannel` over a `LogListModel` it appends to; the pane never owns
the lines, so switching channels loses nothing.

Copy and Clear act on the pane itself, like the commands on Visual Studio's
Output toolbar: they are the pane's own commands, in its toolbar and its
context menu (`ui-architecture.md` §9.3's exception for a pane's local
commands). The platform's Copy key copies the lines while they have focus,
claimed through a shortcut override rather than a second `QAction` shortcut,
so it never competes with the application's Edit → Copy: Qt would call two
actions on one key ambiguous and run neither.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import (
    QEvent,
    QIdentityProxyModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QAction, QGuiApplication, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDockWidget,
    QListView,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from sagittarius_engine.extensions.pyside_mvc.runtime.log_list_model import (
    LogListModel,
)

OUTPUT_TITLE = "Output"

type AnyIndex = QModelIndex | QPersistentModelIndex


@dataclass(frozen=True, slots=True)
class OutputChannel:
    """A source of lines: a stable id, the combo's title, and its model."""

    channel_id: str
    title: str
    model: LogListModel


class _LineText(QIdentityProxyModel):
    """Shows each entry as "[HH:MM:SS] message", the text Copy copies."""

    def data(self, index: AnyIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role == Qt.ItemDataRole.DisplayRole:
            timestamp = super().data(index, LogListModel.TimestampRole)
            message = super().data(index, LogListModel.MessageRole)
            return f"[{timestamp}] {message}"
        return super().data(index, role)


class _Lines(QListView):
    """The read-only lines; claims the Copy key while it has focus."""

    def __init__(self, copy: Callable[[], object]) -> None:
        super().__init__()
        self._copy = copy

    def event(self, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.ShortcutOverride
            and isinstance(event, QKeyEvent)
            and event.matches(QKeySequence.StandardKey.Copy)
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        if event.matches(QKeySequence.StandardKey.Copy):
            self._copy()
            event.accept()
            return
        super().keyPressEvent(event)


class OutputPane(QDockWidget):
    """The dock. `add_channel()` once per source."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(OUTPUT_TITLE, parent)
        self.setObjectName("workbench::output")
        self._channels: dict[str, OutputChannel] = {}
        self._proxy = _LineText(self)
        self._choice = QComboBox()
        self._choice.setObjectName("workbench::output::channel")
        self._choice.currentIndexChanged.connect(self._show_index)
        self._lines = _Lines(self.copy_lines)
        self._lines.setObjectName("workbench::output::lines")
        self._lines.setModel(self._proxy)
        self._lines.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._lines.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._lines.setUniformItemSizes(True)
        self.copy_action = self._pane_action("&Copy", self.copy_lines)
        self.clear_action = self._pane_action("C&lear", self.clear_channel)
        self._lines.addAction(self.copy_action)
        self._lines.addAction(self.clear_action)
        self._lines.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.setWidget(self._body())

    def _pane_action(self, text: str, slot: object) -> QAction:
        action = QAction(text, self)
        action.triggered.connect(slot)
        return action

    def _body(self) -> QWidget:
        bar = QToolBar("Output", self)
        chooser = QWidgetAction(bar)
        chooser.setDefaultWidget(self._choice)
        bar.addAction(chooser)
        bar.addAction(self.copy_action)
        bar.addAction(self.clear_action)
        body = QWidget(self)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(bar)
        layout.addWidget(self._lines)
        return body

    # -- channels -----------------------------------------------------------

    def add_channel(self, channel: OutputChannel) -> None:
        if channel.channel_id in self._channels:
            raise ValueError(f"channel {channel.channel_id!r} is already added")
        self._channels[channel.channel_id] = channel
        self._choice.addItem(channel.title, channel.channel_id)

    def show_channel(self, channel_id: str) -> None:
        index = self._choice.findData(channel_id)
        if index < 0:
            raise ValueError(f"no channel {channel_id!r}")
        self._choice.setCurrentIndex(index)

    @property
    def current_channel(self) -> OutputChannel | None:
        channel_id = self._choice.currentData()
        return self._channels.get(channel_id) if isinstance(channel_id, str) else None

    def _show_index(self, index: int) -> None:
        channel = self.current_channel
        self._proxy.setSourceModel(channel.model if channel is not None else None)

    # -- the pane's commands --------------------------------------------------

    def copy_lines(self) -> str:
        """Copies the selected lines, or every line when none is selected,
        to the clipboard, and returns the text."""
        rows = sorted(
            index.row() for index in self._lines.selectionModel().selectedRows()
        )
        if not rows:
            rows = list(range(self._proxy.rowCount()))
        text = "\n".join(str(self._proxy.index(row, 0).data()) for row in rows)
        QGuiApplication.clipboard().setText(text)
        return text

    def clear_channel(self) -> None:
        channel = self.current_channel
        if channel is not None:
            channel.model.clear()
