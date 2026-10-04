"""Asking before a risky command runs (`EPIC-008C`).

Microsoft (`mess-confirm`): confirm only what is risky or cannot be undone,
say what will happen, answer with specific verbs, and make the safe answer
the default so a reflexive Enter does nothing harmful. The dialog is a stock
`QMessageBox`; the decision of *whether* to ask belongs to the command's
`ActionConfirmation`, never to the handler, so no command forgets.

`IActionConfirmer` is the seam: the registry asks it, a test answers it.
"""

from __future__ import annotations

from typing import Protocol

from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from sagittarius_engine.extensions.pyside_mvc.workbench.action_descriptor import (
    ActionConfirmation,
)


class IActionConfirmer(Protocol):
    """Answers whether a confirmed command may run."""

    def confirm(self, parent: QWidget | None, confirmation: ActionConfirmation) -> bool:
        """`True` only when the user chose the accepting answer."""
        ...


def build_confirmation_box(
    parent: QWidget | None, confirmation: ActionConfirmation
) -> tuple[QMessageBox, QPushButton]:
    """The dialog, and the button that accepts it. The reject button is the
    default and the escape button."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(confirmation.title)
    box.setText(confirmation.consequence)
    # Parented to the box: a button Python alone holds is freed when this
    # function returns, and the box would keep a dangling default button.
    accept = QPushButton(confirmation.accept_text, box)
    reject = QPushButton(confirmation.reject_text, box)
    box.addButton(accept, QMessageBox.ButtonRole.AcceptRole)
    box.addButton(reject, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(reject)
    box.setEscapeButton(reject)
    return box, accept


class MessageBoxConfirmer:
    """Asks with a modal `QMessageBox`."""

    def confirm(self, parent: QWidget | None, confirmation: ActionConfirmation) -> bool:
        box, accept = build_confirmation_box(parent, confirmation)
        box.exec()
        return box.clickedButton() is accept
