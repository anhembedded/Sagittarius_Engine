"""An empty view says what to do, in place (`EPIC-008F`).

Microsoft (`ctrl-list-views`): an empty list view looks broken; show why it
is empty and how to fill it. A `QStackedWidget` holds the instruction and the
view and shows whichever applies — the instruction is a stock `QLabel`, not a
widget drawn over the view, so it lays out, scales and reads like every other
label.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QStackedWidget, QWidget

_INSTRUCTION_PAGE = 0
_VIEW_PAGE = 1


class EmptyStateStack(QStackedWidget):
    """Shows `instruction` while the view's model has no rows."""

    def __init__(
        self,
        view: QAbstractItemView,
        instruction: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        model = view.model()
        if model is None:
            raise ValueError("set the view's model before wrapping it")
        self._model: QAbstractItemModel = model
        self._instruction = QLabel(instruction)
        self._instruction.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._instruction.setWordWrap(True)
        self._instruction.setTextFormat(Qt.TextFormat.PlainText)
        self.insertWidget(_INSTRUCTION_PAGE, self._instruction)
        self.insertWidget(_VIEW_PAGE, view)
        for signal in (
            model.rowsInserted,
            model.rowsRemoved,
            model.modelReset,
            model.layoutChanged,
        ):
            signal.connect(self._follow_rows)
        self._follow_rows()

    @property
    def instruction(self) -> str:
        return self._instruction.text()

    def _follow_rows(self) -> None:
        has_rows = self._model.rowCount() > 0
        self.setCurrentIndex(_VIEW_PAGE if has_rows else _INSTRUCTION_PAGE)
