"""Every table and tree configured one way, from its column specs
(`EPIC-008F`).

What a view does is decided here, once, by the column kinds — never by the
screen (`ui-architecture.md` §1.2): whole-row selection, no in-place editing,
sorting on the raw value, header titles and alignment from the specs, values
written by one `IValueFormatter`, movable columns, no row-number header,
alternating rows. Microsoft's list-view guidance (`ctrl-list-views`) is the
source for each.

The model keeps raw values in `DisplayRole` — numbers, `Decimal`s,
`datetime`s, text, `None` for unknown — and a `SpecProxyModel` adds the
header and the alignment and sorts on those raw values in one order
(`display_value_order`); a `KindDelegate` writes them. So a price sorts as a number and prints as the formatter says,
and no model formats for display.

A grouped `QTreeWidget` (headings with rows under them) owns its model, so
it is configured in place — `configure_item_view(tree, None, specs)` — with
the same rules; its rows are `SpecTreeItem`s so they sort on raw values too.

A model that knows a cell's precision — a price's tick size from its row's
symbol — answers `PRECISION_ROLE` for that cell with a `Precision`; the
delegate hands it to the formatter in `FormatContext.precision`, ahead of the
column's own `ColumnSpec.precision`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from typing import overload

import shiboken6
from PySide6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTreeView,
    QTreeWidget,
)

from sagittarius_engine.extensions.pyside_mvc.workbench.column_spec import (
    ColumnSpec,
    Selection,
    spec_problems,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.display_value_order import (
    display_value_less_than,
    needs_text_comparison,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.i_value_formatter import (
    FormatContext,
    IValueFormatter,
    PlainValueFormatter,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.value_precision import (
    Precision,
)

#: The dynamic property `find_unconfigured_item_views()` reads.
CONFIGURED_PROPERTY = "sagittariusConfiguredView"

#: The item data role a model answers with a cell's `Precision` (or `None`).
#: Far above `Qt.UserRole` so it does not meet a consumer's own roles, which
#: are customarily counted up from `UserRole + 1`.
PRECISION_ROLE = int(Qt.ItemDataRole.UserRole) + 0x5347

_SELECTION_MODE = {
    Selection.SINGLE: QAbstractItemView.SelectionMode.SingleSelection,
    Selection.EXTENDED: QAbstractItemView.SelectionMode.ExtendedSelection,
}

type AnyIndex = QModelIndex | QPersistentModelIndex


class SpecProxyModel(QSortFilterProxyModel):
    """Header titles and alignment from the specs; sorts on raw values.

    Qt's own `lessThan` cannot order a Python `Decimal` or `datetime`, so a
    column of them would stay in model order; this one orders every display
    value (`display_value_order`). Text against text stays Qt's, so the
    proxy's case-sensitivity and locale settings still apply."""

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

    def lessThan(self, source_left: AnyIndex, source_right: AnyIndex) -> bool:  # noqa: N802 - Qt override
        left = source_left.data(self.sortRole())
        right = source_right.data(self.sortRole())
        if needs_text_comparison(left, right):
            return super().lessThan(source_left, source_right)
        return display_value_less_than(left, right)


class KindDelegate(QStyledItemDelegate):
    """Writes each cell through the formatter, by its column's kind, with the
    cell's precision (`PRECISION_ROLE`) or else its column's."""

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
        hint = index.data(PRECISION_ROLE)
        precision = hint if isinstance(hint, Precision) else spec.precision
        context = FormatContext(spec.key, precision)
        option.text = self._formatter.format(spec.kind, raw, context)  # type: ignore[attr-defined]
        # The kind decides the alignment here too, for a view with no proxy
        # to serve it (a `QTreeWidget`); with one, it is the same value.
        option.displayAlignment = spec.kind.alignment  # type: ignore[attr-defined]


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


class _FirstRowsFitter(QObject):
    """Fits the columns when a view's first rows arrive, and never again until
    the model resets: once at the top level (a table's rows, a tree's
    headings) and once at the first rows under any heading (a grouped tree's
    data arrives after its headings). A later group leaves the widths alone,
    so a width the person set, or a saved one restored, survives a live tree
    (review of Engine PR #230)."""

    def __init__(
        self,
        model: QAbstractItemModel,
        fit: Callable[[], None],
        view: QTableView | QTreeView,
    ) -> None:
        # A child of the view: it lives as long as the view, and Qt drops its
        # connections with it. A plain Python object here is collected at
        # once, since PySide holds a bound method's owner weakly.
        super().__init__(view)
        self._model = model
        self._fit = fit
        self._fitted_children = False

    def on_reset(self) -> None:
        self._fitted_children = False
        self._fit()

    def on_rows_inserted(self, parent: QModelIndex, first: int, last: int) -> None:
        if not parent.isValid():
            if self._model.rowCount(parent) == last - first + 1:
                self._fit()
        else:
            self._fit_children_once()

    def on_expanded(self, _index: QModelIndex) -> None:
        """A heading added with its rows already under it raises no insert
        for them, and Qt measures only shown rows: the first time a heading
        opens is when its rows can first be measured (review of PR #230)."""
        self._fit_children_once()

    def _fit_children_once(self) -> None:
        if self._fitted_children:
            return
        self._fitted_children = True
        # A tree lays out rows under a heading after the signal, so a fit now
        # measures nothing new; the next turn of the event loop sees them
        # (measured: 67 px now, 213 px a turn later).
        QTimer.singleShot(0, self._fit)


def _fit_columns(view: QTableView | QTreeView, specs: Sequence[ColumnSpec]) -> None:
    # A `QTreeWidget` resets its own model from its destructor, after PySide
    # has already invalidated the Python wrapper (measured: "Internal C++
    # object (QTreeWidget) already deleted"). A view being destroyed has
    # nothing to measure; every other reset reaches a live view.
    if not shiboken6.isValid(view):
        return
    for column, spec in enumerate(specs):
        if not spec.stretch:
            view.resizeColumnToContents(column)


def _model_to_show(
    view: QTableView | QTreeView,
    model: QAbstractItemModel | None,
    specs: Sequence[ColumnSpec],
) -> QAbstractItemModel:
    """The model the view will show — a `QTreeWidget`'s own, any other
    view's `model` — or a `ValueError` naming everything unusable."""
    problems = list(spec_problems(specs))
    shown: QAbstractItemModel | None = model
    if isinstance(view, QTreeWidget):
        shown = view.model()
        if model is not None:
            problems.append(
                "a QTreeWidget shows its own items; pass None for the model"
            )
    elif model is None:
        problems.append(f"a {type(view).__name__} needs a model")
    elif model.columnCount() != len(specs):
        problems.append(
            f"the model has {model.columnCount()} columns and {len(specs)} specs"
        )
    if problems or shown is None:
        raise ValueError("; ".join(problems))
    return shown


def _set_up_tree_widget(tree: QTreeWidget, specs: Sequence[ColumnSpec]) -> None:
    """The header a proxy would serve, written on the widget's own header
    item: titles and alignment from the specs."""
    tree.setColumnCount(len(specs))
    tree.setHeaderLabels([spec.title for spec in specs])
    header_item = tree.headerItem()
    for column, spec in enumerate(specs):
        header_item.setTextAlignment(column, spec.kind.alignment)


def _apply_conventions(
    view: QTableView | QTreeView,
    specs: Sequence[ColumnSpec],
    formatter: IValueFormatter,
    selection: Selection,
    sortable: bool,
) -> None:
    view.setItemDelegate(KindDelegate(specs, formatter, view))
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(_SELECTION_MODE[selection])
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setAlternatingRowColors(True)
    if isinstance(view, QTableView):
        view.verticalHeader().hide()
        header = view.horizontalHeader()
    else:
        header = view.header()
    _configure_header(header, specs)
    header.setSortIndicatorShown(sortable)
    # No column is sorted until the user clicks one; the first click on a
    # column sorts it ascending (`ctrl-list-views`).
    header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
    view.setSortingEnabled(sortable)


def _fit_and_keep_fitting(
    view: QTableView | QTreeView,
    model: QAbstractItemModel,
    specs: Sequence[ColumnSpec],
) -> None:
    _fit_columns(view, specs)
    fit = partial(_fit_columns, view, tuple(specs))
    # A view that starts empty fits when its first rows arrive; later
    # inserts leave the widths alone, so a live table is not re-measured.
    fitter = _FirstRowsFitter(model, fit, view)
    model.modelReset.connect(fitter.on_reset)
    model.rowsInserted.connect(fitter.on_rows_inserted)
    if isinstance(view, QTreeView):
        view.expanded.connect(fitter.on_expanded)


@overload
def configure_item_view(
    view: QTreeWidget,
    model: None,
    specs: Sequence[ColumnSpec],
    *,
    formatter: IValueFormatter | None = None,
    selection: Selection = Selection.SINGLE,
    sortable: bool = True,
) -> None: ...


@overload
def configure_item_view(
    view: QTableView | QTreeView,
    model: QAbstractItemModel,
    specs: Sequence[ColumnSpec],
    *,
    formatter: IValueFormatter | None = None,
    selection: Selection = Selection.SINGLE,
    sortable: bool = True,
) -> SpecProxyModel: ...


def configure_item_view(
    view: QTableView | QTreeView,
    model: QAbstractItemModel | None,
    specs: Sequence[ColumnSpec],
    *,
    formatter: IValueFormatter | None = None,
    selection: Selection = Selection.SINGLE,
    sortable: bool = True,
) -> SpecProxyModel | None:
    """Shows `model` in `view` the one way every view of the application
    behaves. Returns the proxy, which a caller maps selections through.

    A `QTreeWidget` — a grouped tree whose headings and rows are items —
    owns its model and forbids `setModel`, so it is configured in place:
    `model` is `None`, nothing is returned, the header is written from the
    specs, and the same delegate, selection, editing, sorting and header
    rules apply. Its rows sort on their raw values when they are
    `SpecTreeItem`s; sorting orders each heading's rows among themselves, so
    a group's rows stay under it.

    `sortable=False` turns sorting off and hides the sort indicator, for a
    view whose order is its meaning (a readout in the order its rules build).
    """
    shown = _model_to_show(view, model, specs)
    chosen_formatter = formatter or PlainValueFormatter()
    if isinstance(view, QTreeWidget):
        _set_up_tree_widget(view, specs)
        _apply_conventions(view, specs, chosen_formatter, selection, sortable)
        _fit_and_keep_fitting(view, shown, specs)
        view.setProperty(CONFIGURED_PROPERTY, True)
        return None
    proxy = SpecProxyModel(specs, view)
    proxy.setSourceModel(shown)
    view.setModel(proxy)
    if isinstance(view, QTreeView):
        view.setRootIsDecorated(False)
    _apply_conventions(view, specs, chosen_formatter, selection, sortable)
    _fit_and_keep_fitting(view, proxy, specs)
    view.setProperty(CONFIGURED_PROPERTY, True)
    return proxy
