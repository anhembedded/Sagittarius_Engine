"""The one column that takes the remaining width, without ever being
squeezed below its content (`EPIC-008F`).

Qt's own `QHeaderView.Stretch` gives a column whatever the viewport leaves
after the others. In a dock narrower than the columns that is nothing: the
column falls to the header's minimum section size (the reference consumer's
Watchlist read "Sym" over "BN…") while the columns after it ran off the
edge. So a `ColumnSpec.stretch` column is an ordinary content-sized
`Interactive` column like every other, and a `StretchColumnFiller` widens it
to fill what the others leave, never below its content width. A view
narrower than its columns then scrolls horizontally with every column whole
(MS `ctrl-list-views`: a column shows its content).
"""

from __future__ import annotations

import shiboken6
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QHeaderView, QTableView, QTreeView


def header_of(view: QTableView | QTreeView) -> QHeaderView:
    """The header that holds a view's columns."""
    return view.horizontalHeader() if isinstance(view, QTableView) else view.header()


def content_width(view: QTableView | QTreeView, column: int) -> int:
    """The width `column` needs to show its title and its visible cells whole."""
    return max(header_of(view).sectionSizeHint(column), view.sizeHintForColumn(column))


class StretchColumnFiller(QObject):
    """Gives `column` the width the other columns leave in the viewport, but
    never less than its content. A child of the view, so it lives and dies
    with it.

    The content width is measured only when the view's columns are fitted
    (`remeasure`, on configure, a reset and a view's first rows) and kept as
    the floor; a resize then only compares that floor with the space left.
    Measuring is `sizeHintForColumn`, up to a thousand rows each time, so
    measuring on every row insert made appending a thousand rows to a shown
    table take 21 s instead of 0.05 s, and reset a width the person dragged
    on each insert (review of Engine PR #230)."""

    def __init__(self, view: QTableView | QTreeView, column: int) -> None:
        super().__init__(view)
        self._view = view
        self._column = column
        self._floor = header_of(view).sectionSizeHint(column)
        header_of(view).sectionResized.connect(self._on_section_resized)
        view.viewport().installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.fill()
        return False

    def _on_section_resized(self, column: int, _old: int, _new: int) -> None:
        if column != self._column:
            self.fill()

    def remeasure(self) -> None:
        """Takes the column's content width as its new floor, then fills."""
        if not shiboken6.isValid(self._view):
            return
        self._floor = content_width(self._view, self._column)
        self.fill()

    def fill(self) -> None:
        """The floor alone while the view is hidden: a hidden viewport's size
        is Qt's placeholder, and a size hint taken before the first show
        would grow the dock to fit it."""
        # A `QTreeWidget` resets its own model from its destructor, after
        # PySide has invalidated the wrapper; a dying view has no width.
        if not shiboken6.isValid(self._view):
            return
        header = header_of(self._view)
        width = self._floor
        if self._view.isVisible():
            others = header.length() - header.sectionSize(self._column)
            width = max(width, self._view.viewport().width() - others)
        if header.sectionSize(self._column) != width:
            header.resizeSection(self._column, width)
