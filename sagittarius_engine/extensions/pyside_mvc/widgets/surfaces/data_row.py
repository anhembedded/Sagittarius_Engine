"""
@brief `DataRow` — a `Panel` laying out one record as a row of cells.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ..controls import StyledButton
from ..style import StyleRole, apply_role
from ..surface import Panel


@dataclass(frozen=True)
class Column:
    """
    @brief One column: its heading, its share of the width, and how its
    cells align.

    @details Shared with `TableCard`, which draws the heading strip these
    same specs describe. The reference consumer keeps three incompatible
    versions of this — a `(label, stretch, alignment)` triple, a
    `(label, stretch)` pair whose header sets no alignment at all, and a
    pair of parallel tuples that must be kept the same length by hand. One
    of those also duplicates its stretch list between the row widget and
    the header builder, which is exactly the drift a single spec prevents.
    """

    label: str
    stretch: int = 1
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft


@dataclass(frozen=True)
class RowAction:
    """One trailing button on a row."""

    label: str
    #: Which button role it renders as — a destructive row action should
    #: not look like an ordinary one.
    role: StyleRole = StyleRole.SECONDARY_BUTTON


class DataRow(Panel):
    """
    @brief A `Panel` holding one label per column, optionally followed by a
    row of action buttons.

    @details
    Built from three of the reference consumer's four row widgets — its
    status row (6 cells + 4 action buttons), its candle row (8 cells, one
    of which is already written as exactly this loop over a column spec),
    and its gap row (5 cells + 1 button).

    **Its trade-log row is deliberately excluded**, and this is the call
    `EPIC-007B`'s own risk note asked for. That widget is not a wider
    version of this one: it *is* a `QPushButton`, three of its six columns
    stack two lines of differently-styled text, two of its cells are
    recoloured badges, it owns a collapsible detail pane of three further
    columns, and it emits a toggle signal. Fitting it would need a
    per-cell widget factory, an expandable-body hook and a click signal —
    at which point every part of the base is overridden and the base is
    carrying parameters that exist to please one caller.

    **Cells are filled by `set_cells`, never by the constructor.** Three of
    the four consumers already work this way, building empty and refilling
    on model change; the gap row instead takes its data as constructor
    arguments and therefore cannot be updated at all, which is why its own
    dialog has to destroy and rebuild every row on every refresh. Adopting
    the fillable shape is what lets a consumer stop doing that.
    """

    #: Emits the index of the action pressed, within the `actions` sequence
    #: this row was built with. Not the label: labels are display text and
    #: change with locale, while the position is what the caller wired up.
    action_triggered = Signal(int)

    def __init__(
        self,
        columns: Sequence[Column],
        *,
        actions: Sequence[RowAction] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not columns:
            raise ValueError("DataRow needs at least one column")

        self._columns = tuple(columns)
        self._cells: list[QLabel] = []

        row = QHBoxLayout()
        for column in self._columns:
            cell = QLabel()
            cell.setAlignment(column.alignment | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(cell, column.stretch)
            self._cells.append(cell)

        self.action_buttons: list[StyledButton] = []
        for position, action in enumerate(actions):
            button = StyledButton(action.label, role=action.role)
            button.clicked.connect(
                lambda _checked=False, i=position: self.action_triggered.emit(i)
            )
            row.addWidget(button)
            self.action_buttons.append(button)

        self.body_layout.addLayout(row)

    @property
    def columns(self) -> tuple[Column, ...]:
        return self._columns

    def cell_texts(self) -> list[str]:
        """@brief What every cell currently reads, left to right."""
        return [cell.text() for cell in self._cells]

    def set_cells(self, values: Sequence[str]) -> None:
        """
        @brief Fills every cell, left to right.

        @raise ValueError If `values` is not exactly as long as the column
        spec. Silently padding or truncating would put a record's columns
        out of alignment with the heading above them, and a row of data
        shifted one column left is worse than a loud failure — it still
        looks like data.
        """
        if len(values) != len(self._cells):
            raise ValueError(
                f"DataRow has {len(self._cells)} columns, got {len(values)} values"
            )
        for cell, value in zip(self._cells, values, strict=True):
            cell.setText(value)

    def set_action_visible(self, position: int, visible: bool) -> None:
        """@brief Shows or hides one action button — the consumer's status
        row hides its "gaps" button on healthy records rather than
        disabling it."""
        self.action_buttons[position].setVisible(visible)

    def set_cell_role(self, position: int, role: StyleRole) -> None:
        """@brief Restyles one cell — for a status cell that reads as a
        badge, or a value that should carry a section label's muted
        treatment."""
        apply_role(self._cells[position], role)
