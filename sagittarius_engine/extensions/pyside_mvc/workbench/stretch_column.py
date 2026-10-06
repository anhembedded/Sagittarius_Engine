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
from PySide6.QtCore import QEvent, QModelIndex, QObject
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

    Refills on the viewport's resize and show, on another column's resize,
    and on a model reset or row insert (the content may have grown)."""

    def __init__(self, view: QTableView | QTreeView, column: int) -> None:
        super().__init__(view)
        self._view = view
        self._column = column
        header_of(view).sectionResized.connect(self._on_section_resized)
        view.viewport().installEventFilter(self)
        model = view.model()
        model.modelReset.connect(self.fill)
        model.rowsInserted.connect(self._on_rows_inserted)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.fill()
        return False

    def _on_section_resized(self, column: int, _old: int, _new: int) -> None:
        if column != self._column:
            self.fill()

    def _on_rows_inserted(self, _parent: QModelIndex, _first: int, _last: int) -> None:
        self.fill()

    def fill(self) -> None:
        """Content width while the view is hidden: a hidden viewport's size
        is Qt's placeholder, and a size hint taken before the first show
        would grow the dock to fit it."""
        # A `QTreeWidget` resets its own model from its destructor, after
        # PySide has invalidated the wrapper; a dying view has no width.
        if not shiboken6.isValid(self._view):
            return
        header = header_of(self._view)
        width = content_width(self._view, self._column)
        if self._view.isVisible():
            others = header.length() - header.sectionSize(self._column)
            width = max(width, self._view.viewport().width() - others)
        if header.sectionSize(self._column) != width:
            header.resizeSection(self._column, width)
