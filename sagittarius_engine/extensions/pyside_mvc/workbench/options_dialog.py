"""Tools → Options: every module's settings in one dialog (`EPIC-008E`).

Microsoft's dialog guidance (`win-dialog-box`), as Visual Studio and Qt
Creator apply it: sections on the left, the chosen page on the right, and
one row of commit buttons from `QDialogButtonBox`, which orders them the
platform's way. Apply is enabled only while some page holds edits; OK is
disabled while a page cannot be applied, and the reason shows above the
buttons. Cancel, Esc and the title-bar close revert every page.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sagittarius_engine.extensions.pyside_mvc.workbench.i_options_page import (
    IOptionsPage,
)

OPTIONS_TITLE = "Options"
_Buttons = QDialogButtonBox.StandardButton


class OptionsDialog(QDialog):
    """The Options dialog over the contributed pages."""

    def __init__(
        self, pages: Sequence[IOptionsPage], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(OPTIONS_TITLE)
        self.setObjectName("workbench::options")
        self._pages = tuple(pages)
        self._sections = QListWidget(self)
        self._sections.setObjectName("workbench::options::sections")
        self._stack = QStackedWidget(self)
        for page in self._pages:
            self._sections.addItem(page.title)
            self._stack.addWidget(page.widget())
            page.set_change_listener(self._refresh)
        self._sections.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._message = QLabel(self)
        self._message.setObjectName("workbench::options::message")
        self._message.setTextFormat(Qt.TextFormat.PlainText)
        self._message.setWordWrap(True)
        self._buttons = QDialogButtonBox(
            _Buttons.Ok | _Buttons.Cancel | _Buttons.Apply, self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        self._button(_Buttons.Apply).clicked.connect(self.apply)
        self._lay_out()
        if self._pages:
            self._sections.setCurrentRow(0)
        self._refresh()

    def _lay_out(self) -> None:
        body = QHBoxLayout()
        body.addWidget(self._sections, 1)
        body.addWidget(self._stack, 3)
        layout = QVBoxLayout(self)
        layout.addLayout(body)
        layout.addWidget(self._message)
        layout.addWidget(self._buttons)

    def _button(self, which: QDialogButtonBox.StandardButton) -> QPushButton:
        button = self._buttons.button(which)
        if button is None:
            raise LookupError(f"the dialog has no {which!r} button")
        return button

    # -- state ------------------------------------------------------------

    def _first_problem(self) -> str | None:
        for page in self._pages:
            message = page.validation_message()
            if message:
                return f"{page.title}: {message}"
        return None

    def _refresh(self) -> None:
        problem = self._first_problem()
        dirty = any(page.is_dirty() for page in self._pages)
        self._message.setText(problem or "")
        self._message.setVisible(problem is not None)
        self._button(_Buttons.Ok).setEnabled(problem is None)
        self._button(_Buttons.Apply).setEnabled(dirty and problem is None)

    # -- the commit buttons ----------------------------------------------------

    def apply(self) -> None:
        """Applies every page holding edits; the dialog stays open."""
        if self._first_problem() is not None:
            return
        for page in self._pages:
            if page.is_dirty():
                page.apply()
        self._refresh()

    def accept(self) -> None:
        if self._first_problem() is not None:
            return
        self.apply()
        super().accept()

    def reject(self) -> None:
        """Cancel, Esc and the title-bar close all land here."""
        for page in self._pages:
            page.revert()
        super().reject()
