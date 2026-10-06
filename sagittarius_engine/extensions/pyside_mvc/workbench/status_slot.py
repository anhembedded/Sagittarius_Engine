"""
@brief `StatusSlot` — where one permanent status-bar widget sits in the shell.

@details
Two parties decide whether a status-bar widget shows. The shell decides
whether it belongs to the current mode (`WorkbenchShell.add_status_widget`'s
`mode_id`). Its owner decides whether it has anything to say: a task's
progress bar is hidden while no task runs. `BUG-021`: the shell answered both
questions on the owner's widget with one `setVisible()`, so each mode change
showed what the owner had hidden. An idle task's progress bar, left
indeterminate behind its owner's `hide()`, appeared busy from start-up in
every mode of the reference consumer.

The slot keeps the two answers apart. The shell sets only the slot's scope;
the owner keeps calling `show()` and `hide()` on its own widget, which the
shell never touches. The slot shows when both say yes. It follows the owner
through the `ShowToParent` and `HideToParent` events Qt sends when a child's
own visibility changes, so an owner needs no API of the shell's. An owner
that deletes its widget leaves no empty box: the slot stays hidden after.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget


class StatusSlot(QWidget):
    """
    @brief Holds one status-bar widget; visible while the widget is in scope
    and its owner has not hidden it.
    """

    def __init__(self, widget: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._widget: QWidget | None = widget
        self._in_scope = True
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        widget.installEventFilter(self)
        widget.destroyed.connect(self._forget_widget)
        self._refresh()

    @property
    def widget(self) -> QWidget | None:
        """The owner's widget; `None` once the owner deleted it."""
        return self._widget

    def set_in_scope(self, in_scope: bool) -> None:
        """The shell's answer: whether the current mode shows this widget."""
        self._in_scope = in_scope
        self._refresh()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if watched is self._widget and event.type() in (
            QEvent.Type.ShowToParent,
            QEvent.Type.HideToParent,
        ):
            self._refresh()
        return super().eventFilter(watched, event)

    def _forget_widget(self) -> None:
        self._widget = None
        self._refresh()

    def _refresh(self) -> None:
        widget = self._widget
        self.setVisible(
            self._in_scope and widget is not None and not _owner_hid(widget)
        )


def _owner_hid(widget: QWidget) -> bool:
    """Whether the owner hid `widget` itself. The shell never calls
    `setVisible()` on it, so an explicit hide is the owner's. Plain
    `isHidden()` would not do: a widget never shown, or one just moved into
    its slot, reads hidden until its parent shows, and Qt shows such a child
    with its parent."""
    return widget.isHidden() and widget.testAttribute(
        Qt.WidgetAttribute.WA_WState_ExplicitShowHide
    )
