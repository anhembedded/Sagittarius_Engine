"""One page of Tools → Options (`EPIC-008E`).

A module contributes the page for its own settings; the dialog owns the
commit buttons and their meaning (MS `win-dialog-box`): OK applies and
closes, Cancel reverts and closes, Apply applies and stays. So a page never
saves on its own, and every page is applied, or reverted, together.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PySide6.QtWidgets import QWidget


class IOptionsPage(Protocol):
    """What the Options dialog needs of a page."""

    @property
    def title(self) -> str:
        """The section name in the list on the left. Title case, no "&"."""
        ...

    def widget(self) -> QWidget:
        """The page itself: stock controls, built once."""
        ...

    def apply(self) -> None:
        """Writes the edited values. Called only when `is_dirty()`."""
        ...

    def revert(self) -> None:
        """Puts the page back to the saved values."""
        ...

    def is_dirty(self) -> bool:
        """Whether the page holds edits not yet applied."""
        ...

    def validation_message(self) -> str | None:
        """Why the page's values cannot be applied, or `None`."""
        ...

    def set_change_listener(self, listener: Callable[[], None]) -> None:
        """The dialog's callback for any edit, so it can re-evaluate Apply and
        OK without polling. Called once, before the dialog shows."""
        ...
