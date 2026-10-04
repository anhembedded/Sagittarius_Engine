"""What kind of value a column, list or read-out shows, and what every
display of that kind shares (`EPIC-008F`).

The component-boundary law (`ui-architecture.md` §1.2): a mechanism owns what
is the same on every use. Every price on every screen aligns the same way and
formats through the same formatter; which columns a table has is the
consumer's. Before this, the reference consumer configured each of its twelve
tables by hand and formatted values per screen, so one price printed two ways.

Alignment follows Microsoft's list-view guidance (`ctrl-list-views`): numbers
right-aligned so their digits line up, text and dates left.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt

_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class ColumnKind(Enum):
    """The kinds of value a display widget shows."""

    TEXT = "text"
    QUANTITY = "quantity"
    PRICE = "price"
    PERCENT = "percent"
    MONEY = "money"
    TIMESTAMP = "timestamp"
    DURATION = "duration"
    SIDE = "side"
    STATUS = "status"

    @property
    def alignment(self) -> Qt.AlignmentFlag:
        """Right for every number, left for everything else."""
        return _RIGHT if self in _NUMERIC else _LEFT

    @property
    def is_numeric(self) -> bool:
        return self in _NUMERIC


_NUMERIC = frozenset(
    {
        ColumnKind.QUANTITY,
        ColumnKind.PRICE,
        ColumnKind.PERCENT,
        ColumnKind.MONEY,
        ColumnKind.DURATION,
    }
)
