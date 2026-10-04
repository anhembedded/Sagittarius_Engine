"""Every table and tree configured one way, from its column specs
(`EPIC-008F`).

What a view does is decided here, once, by the column kinds — never by the
screen (`ui-architecture.md` §1.2): whole-row selection, no in-place editing,
sorting on the raw value, header titles and alignment from the specs, values
written by one `IValueFormatter`, movable columns, no row-number header,
alternating rows. Microsoft's list-view guidance (`ctrl-list-views`) is the
source for each.

The model keeps raw values in `DisplayRole`; a `SpecProxyModel` adds the
header and the alignment and sorts on those raw values, and a `KindDelegate`
writes them. So a price sorts as a number and prints as the formatter says,
and no model formats for display.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial

from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTreeView,
)

from sagittarius_engine.extensions.pyside_mvc.workbench.column_spec import (
    ColumnSpec,
    Selection,
    spec_problems,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.i_value_formatter import (
    FormatContext,
    IValueFormatter,
    PlainValueFormatter,
)

#: The dynamic property `find_unconfigured_item_views()` reads.
CONFIGURED_PROPERTY = "sagittariusConfiguredView"

_SELECTION_MODE = {
    Selection.SINGLE: QAbstractItemView.SelectionMode.SingleSelection,
    Selection.EXTENDED: QAbstractItemView.SelectionMode.ExtendedSelection,
}

type AnyIndex = QModelIndex | QPersistentModelIndex


class SpecProxyModel(QSortFilterProxyModel):
    """Header titles and alignment from the specs; sorts on raw values."""

    def __init__(
        self, specs: Sequence[ColumnSpec], parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._specs = tuple(specs)

    @property
    def specs(self) -> tuple[ColumnSpec, ...]:
        return self._specs

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if orientation is Qt.Orientation.Horizontal and 0 <= section < len(self._specs):
            spec = self._specs[section]
            if role == Qt.ItemDataRole.DisplayRole:
                return spec.title
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return spec.kind.alignment
        return super().headerData(section, orientation, role)

    def data(self, index: AnyIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        column = index.column()
        if role == Qt.ItemDataRole.TextAlignmentRole and 0 <= column < len(self._specs):
            return self._specs[column].kind.alignment
        return super().data(index, role)


class KindDelegate(QStyledItemDelegate):
    """Writes each cell through the formatter, by its column's kind."""

    def __init__(
        self,
        specs: Sequence[ColumnSpec],
        formatter: IValueFormatter,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._specs = tuple(specs)
        self._formatter = formatter

    def initStyleOption(self, option: QStyleOptionViewItem, index: AnyIndex) -> None:
        super().initStyleOption(option, index)
        column = index.column()
        if not 0 <= column < len(self._specs):
            return
        spec = self._specs[column]
        raw = index.data(Qt.ItemDataRole.DisplayRole)
        option.text = self._formatter.format(spec.kind, raw, FormatContext(spec.key))  # type: ignore[attr-defined]


def _configure_header(header: QHeaderView, specs: Sequence[ColumnSpec]) -> None:
    header.setSectionsMovable(True)
    header.setSortIndicatorShown(True)
    header.setStretchLastSection(False)
    for column, spec in enumerate(specs):
        # `Interactive`, not `ResizeToContents`: the latter measures every
        # row on every change, which Qt warns against for large, live models.
        # Widths fit the content on configure and on each model reset; the
        # user may resize in between.
        mode = (
            QHeaderView.ResizeMode.Stretch
            if spec.stretch
            else QHeaderView.ResizeMode.Interactive
        )
        header.setSectionResizeMode(column, mode)


def _fit_when_first_rows_arrive(
    proxy: QSortFilterProxyModel,
    fit: Callable[[], None],
    parent: QModelIndex,
    first: int,
    last: int,
) -> None:
    if not parent.isValid() and proxy.rowCount() == last - first + 1:
        fit()


def _fit_columns(view: QTableView | QTreeView, specs: Sequence[ColumnSpec]) -> None:
    for column, spec in enumerate(specs):
        if not spec.stretch:
            view.resizeColumnToContents(column)


def configure_item_view(
    view: QTableView | QTreeView,
    model: QAbstractItemModel,
    specs: Sequence[ColumnSpec],
    *,
    formatter: IValueFormatter | None = None,
    selection: Selection = Selection.SINGLE,
) -> SpecProxyModel:
    """Shows `model` in `view` the one way every view of the application
    behaves. Returns the proxy, which a caller maps selections through."""
    problems = list(spec_problems(specs))
    if model.columnCount() != len(specs):
        problems.append(
            f"the model has {model.columnCount()} columns and {len(specs)} specs"
        )
    if problems:
        raise ValueError("; ".join(problems))
    proxy = SpecProxyModel(specs, view)
    proxy.setSourceModel(model)
    view.setModel(proxy)
    view.setItemDelegate(KindDelegate(specs, formatter or PlainValueFormatter(), view))
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(_SELECTION_MODE[selection])
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setAlternatingRowColors(True)
    if isinstance(view, QTableView):
        view.verticalHeader().hide()
        header = view.horizontalHeader()
    else:
        view.setRootIsDecorated(False)
        header = view.header()
    _configure_header(header, specs)
    # No column is sorted until the user clicks one; the first click on a
    # column sorts it ascending (`ctrl-list-views`).
    header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
    view.setSortingEnabled(True)
    _fit_columns(view, specs)
    fit = partial(_fit_columns, view, tuple(specs))
    proxy.modelReset.connect(fit)
    # A table that starts empty fits when its first rows arrive; later
    # inserts leave the widths alone, so a live table is not re-measured.
    proxy.rowsInserted.connect(partial(_fit_when_first_rows_arrive, proxy, fit))
    view.setProperty(CONFIGURED_PROPERTY, True)
    return proxy
