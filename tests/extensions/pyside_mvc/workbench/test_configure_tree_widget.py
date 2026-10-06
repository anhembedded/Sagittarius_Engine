"""A grouped `QTreeWidget` — headings with rows under them — is configured
from column specs like every model-backed view, and sorting keeps each
group's rows under its heading (`EPIC-008F`; the reference consumer's
`BOT-151`)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyleOptionViewItem,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
)

from sagittarius_engine.extensions.pyside_mvc import (
    ColumnKind,
    ColumnSpec,
    Selection,
    SpecTreeItem,
    configure_item_view,
    find_unconfigured_item_views,
)

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_SPECS = (
    ColumnSpec("metric", "Metric", ColumnKind.TEXT, stretch=True),
    ColumnSpec("value", "Value", ColumnKind.MONEY),
)


def _row(metric: str, value: Decimal | None) -> SpecTreeItem:
    item = SpecTreeItem()
    item.setData(0, Qt.ItemDataRole.DisplayRole, metric)
    item.setData(1, Qt.ItemDataRole.DisplayRole, value)
    return item


def _grouped(tree: QTreeWidget) -> None:
    """Two headings, three rows each, values out of order."""
    for title, values in (
        ("Returns", [Decimal("30"), None, Decimal("-5")]),
        ("Risk", [Decimal("2.5"), Decimal("10"), Decimal("1")]),
    ):
        heading = QTreeWidgetItem([title])
        tree.addTopLevelItem(heading)
        for number, value in enumerate(values):
            heading.addChild(_row(f"{title} {number}", value))
        heading.setExpanded(True)


def _children(tree: QTreeWidget, heading_text: str) -> list[object]:
    (heading,) = tree.findItems(heading_text, Qt.MatchFlag.MatchExactly, 0)
    return [
        heading.child(row).data(1, Qt.ItemDataRole.DisplayRole)
        for row in range(heading.childCount())
    ]


@pytest.fixture
def tree(qtbot) -> QTreeWidget:
    widget = QTreeWidget()
    qtbot.addWidget(widget)
    return widget


class TestTheSameRulesAsAModelBackedView:
    def test_whole_rows_no_editing_and_the_selection_asked_for(
        self, tree: QTreeWidget
    ) -> None:
        result = configure_item_view(tree, None, _SPECS, selection=Selection.EXTENDED)

        assert result is None
        assert (
            tree.selectionBehavior() is QAbstractItemView.SelectionBehavior.SelectRows
        )
        assert tree.selectionMode() is QAbstractItemView.SelectionMode.ExtendedSelection
        assert tree.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
        assert tree.header().sectionsMovable()
        assert tree.isSortingEnabled()

    def test_the_header_titles_and_alignment_come_from_the_specs(
        self, tree: QTreeWidget
    ) -> None:
        configure_item_view(tree, None, _SPECS)

        header = tree.headerItem()
        assert [header.text(column) for column in range(2)] == ["Metric", "Value"]
        assert header.textAlignment(1) == _RIGHT

    def test_cells_are_written_by_the_formatter_and_aligned_by_kind(
        self, tree: QTreeWidget
    ) -> None:
        configure_item_view(tree, None, _SPECS)
        _grouped(tree)
        heading = tree.model().index(0, 0, QModelIndex())
        index = tree.model().index(0, 1, heading)
        option = QStyleOptionViewItem()

        tree.itemDelegate().initStyleOption(option, index)

        assert option.text == "30"  # type: ignore[attr-defined]
        assert option.displayAlignment == _RIGHT  # type: ignore[attr-defined]

    def test_the_guard_counts_it_configured(self, tree: QTreeWidget) -> None:
        configure_item_view(tree, None, _SPECS)
        assert find_unconfigured_item_views(tree) == ()


class TestSortingWithinGroups:
    def test_a_groups_rows_sort_under_their_heading_on_raw_values(
        self, tree: QTreeWidget
    ) -> None:
        configure_item_view(tree, None, _SPECS)
        _grouped(tree)

        tree.sortByColumn(1, Qt.SortOrder.AscendingOrder)

        assert _children(tree, "Returns") == [Decimal("-5"), Decimal("30"), None]
        assert _children(tree, "Risk") == [Decimal("1"), Decimal("2.5"), Decimal("10")]

    def test_descending_reverses_within_each_group(self, tree: QTreeWidget) -> None:
        configure_item_view(tree, None, _SPECS)
        _grouped(tree)

        tree.sortByColumn(1, Qt.SortOrder.DescendingOrder)

        assert _children(tree, "Risk") == [Decimal("10"), Decimal("2.5"), Decimal("1")]

    def test_nothing_is_sorted_until_asked(self, tree: QTreeWidget) -> None:
        configure_item_view(tree, None, _SPECS)
        _grouped(tree)

        assert _children(tree, "Risk") == [Decimal("2.5"), Decimal("10"), Decimal("1")]

    def test_a_view_whose_order_is_its_meaning_does_not_sort(
        self, tree: QTreeWidget
    ) -> None:
        configure_item_view(tree, None, _SPECS, sortable=False)

        assert not tree.isSortingEnabled()
        assert not tree.header().isSortIndicatorShown()


class TestRefused:
    def test_a_tree_widget_with_a_model_is_refused(self, tree: QTreeWidget) -> None:
        with pytest.raises(ValueError, match="pass None for the model"):
            configure_item_view(tree, QStandardItemModel(0, 2), _SPECS)  # type: ignore[call-overload]

    def test_a_table_without_a_model_is_refused(self, qtbot) -> None:
        table = QTableView()
        qtbot.addWidget(table)
        with pytest.raises(ValueError, match="needs a model"):
            configure_item_view(table, None, _SPECS)  # type: ignore[call-overload]


def test_a_model_backed_view_can_turn_sorting_off(qtbot) -> None:
    table = QTableView()
    qtbot.addWidget(table)

    configure_item_view(table, QStandardItemModel(0, 2), _SPECS, sortable=False)

    assert not table.isSortingEnabled()


def test_destroying_a_configured_tree_widget_measures_nothing(qtbot) -> None:
    """A `QTreeWidget` resets its own model from its destructor; the column
    fitter listening to that reset must not reach the dying view."""
    tree = QTreeWidget()
    configure_item_view(tree, None, _SPECS)
    _grouped(tree)

    with qtbot.waitSignal(tree.destroyed):
        tree.deleteLater()
