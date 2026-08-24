"""
@brief `Overlay` — the abstract gate for modal dialogs in this package.
Its own single-inheritance chain from `QDialog`, independent of
`Surface`/`Card` (see `widgets.style` for why they cannot share a base).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .style import StyleRole, apply_role


class Overlay(QDialog):
    """
    @brief A modal `QDialog` with token-styled chrome, a title/subtitle
    header, and a footer button row a subclass supplies. Abstract — always
    instantiate a subclass (`ConfirmOverlay`, `PickerOverlay`, or an app's
    own), never `Overlay` itself.

    @details `type(self) is Overlay` guard, same reasoning as `Surface`'s —
    `abc.abstractmethod` does not reliably block instantiation for a Qt
    widget subclass under this PySide6/Shiboken version (verified
    empirically, see `Surface`'s docstring).
    """

    def __init__(
        self, title: str, subtitle: str = "", *, parent: QWidget | None = None
    ) -> None:
        if type(self) is Overlay:
            raise TypeError(
                "Overlay is abstract — instantiate a subclass (e.g. "
                "ConfirmOverlay, PickerOverlay)."
            )
        super().__init__(parent)
        self.setModal(True)
        apply_role(self, StyleRole.SURFACE)

        outer = QVBoxLayout(self)

        self._title_label = QLabel(title)
        outer.addWidget(self._title_label)

        self._subtitle_label = QLabel(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))
        outer.addWidget(self._subtitle_label)

        self.body_layout = QVBoxLayout()
        outer.addLayout(self.body_layout, 1)

        outer.addLayout(self._build_buttons())

    @property
    def title(self) -> str:
        return self._title_label.text()

    @title.setter
    def title(self, value: str) -> None:
        self._title_label.setText(value)

    @property
    def subtitle(self) -> str:
        return self._subtitle_label.text()

    @subtitle.setter
    def subtitle(self, value: str) -> None:
        self._subtitle_label.setText(value)
        self._subtitle_label.setVisible(bool(value))

    def _build_buttons(self) -> QHBoxLayout:
        """
        @brief Returns the footer button row. A subclass overrides this to
        supply its own buttons (Cancel/Confirm, a search field's action
        row, ...) — called once, from `Overlay.__init__`, before the
        subclass's own `__init__` body runs any further, so a subclass
        wanting to keep a reference to a button it creates here must
        capture it in an instance attribute inside its own override, not
        rely on this method's return value being kept around afterward.
        @details Default: an empty row. Not `@abstractmethod` for the same
        reason `Surface`'s abstractness uses a `type(self) is` guard rather
        than `abc` — a subclass that genuinely wants no buttons (unlikely,
        but not this base's business to forbid) is not blocked from having
        none.
        """
        return QHBoxLayout()
