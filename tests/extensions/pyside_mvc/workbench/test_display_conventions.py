"""Every table, list and read-out of a kind behaves the same, because the
kind decides (`EPIC-008F`; Microsoft `ctrl-list-views`)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QStyleOptionViewItem,
    QTableView,
    QTreeView,
    QWidget,
)

from sagittarius_engine.extensions.pyside_mvc import (
    ColumnKind,
    ColumnSpec,
    EmptyStateStack,
    FormatContext,
    ItemViewStateStore,
    PlainValueFormatter,
    ReadoutForm,
    Selection,
    configure_item_view,
    find_unconfigured_item_views,
)

_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
_SPECS = (
    ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
    ColumnSpec("price", "Price", ColumnKind.PRICE),
)


def _model(rows: list[tuple[str, float]]) -> QStandardItemModel:
    model = QStandardItemModel(0, 2)
    for symbol, price in rows:
        symbol_item, price_item = QStandardItem(), QStandardItem()
        symbol_item.setData(symbol, Qt.ItemDataRole.DisplayRole)
        price_item.setData(price, Qt.ItemDataRole.DisplayRole)
        model.appendRow([symbol_item, price_item])
    return model


_CLICK_HOLD_MS = 50
_TABLE_WIDTH = 400
_TABLE_HEIGHT = 300


def _click(qtbot, widget: QWidget, pos: QPoint) -> None:
    """A press and a release apart: `QHeaderView` ignores a zero-length
    click synthesised in one call."""
    qtbot.mousePress(widget, Qt.MouseButton.LeftButton, pos=pos)
    qtbot.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=pos, delay=_CLICK_HOLD_MS)


class _ShoutingFormatter:
    """An `IValueFormatter` that marks every value it wrote."""

    def format(self, kind: ColumnKind, value: object, context: FormatContext) -> str:
        return f"<{context.key}:{value}>"


@pytest.fixture
def table(qtbot) -> QTableView:
    view = QTableView()
    qtbot.addWidget(view)
    return view


class TestColumnKind:
    @pytest.mark.parametrize(
        "kind",
        [
            ColumnKind.PRICE,
            ColumnKind.QUANTITY,
            ColumnKind.MONEY,
            ColumnKind.PERCENT,
            ColumnKind.DURATION,
        ],
    )
    def test_numbers_align_right(self, kind: ColumnKind) -> None:
        assert kind.alignment == _RIGHT

    @pytest.mark.parametrize(
        "kind",
        [ColumnKind.TEXT, ColumnKind.TIMESTAMP, ColumnKind.SIDE, ColumnKind.STATUS],
    )
    def test_text_and_dates_align_left(self, kind: ColumnKind) -> None:
        assert kind.alignment == _LEFT


class TestConfigureItemView:
    def test_whole_rows_no_editing_no_row_numbers(self, table: QTableView) -> None:
        configure_item_view(table, _model([("BTC", 1.0)]), _SPECS)

        assert (
            table.selectionBehavior() is QAbstractItemView.SelectionBehavior.SelectRows
        )
        assert table.selectionMode() is QAbstractItemView.SelectionMode.SingleSelection
        assert table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
        assert table.verticalHeader().isHidden()
        assert table.horizontalHeader().sectionsMovable()

    def test_extended_selection_when_asked(self, table: QTableView) -> None:
        configure_item_view(table, _model([]), _SPECS, selection=Selection.EXTENDED)
        assert (
            table.selectionMode() is QAbstractItemView.SelectionMode.ExtendedSelection
        )

    def test_the_header_and_alignment_come_from_the_specs(
        self, table: QTableView
    ) -> None:
        proxy = configure_item_view(table, _model([("BTC", 1.0)]), _SPECS)

        assert proxy.headerData(1, Qt.Orientation.Horizontal) == "Price"
        assert proxy.index(0, 1).data(Qt.ItemDataRole.TextAlignmentRole) == _RIGHT
        assert proxy.index(0, 0).data(Qt.ItemDataRole.TextAlignmentRole) == _LEFT

    def test_nothing_is_sorted_until_a_click_and_the_first_click_ascends(
        self, qtbot, table: QTableView
    ) -> None:
        proxy = configure_item_view(
            table, _model([("A", 10.0), ("B", 9.0), ("C", 100.0)]), _SPECS
        )
        table.resize(_TABLE_WIDTH, _TABLE_HEIGHT)
        table.show()
        qtbot.waitExposed(table)
        header = table.horizontalHeader()
        assert [proxy.index(row, 0).data() for row in range(3)] == ["A", "B", "C"]
        price_header = QPoint(
            header.sectionViewportPosition(1) + header.sectionSize(1) // 2,
            header.height() // 2,
        )

        _click(qtbot, header.viewport(), price_header)

        assert [proxy.index(row, 1).data() for row in range(3)] == [9.0, 10.0, 100.0]

        _click(qtbot, header.viewport(), price_header)

        assert [proxy.index(row, 1).data() for row in range(3)] == [100.0, 10.0, 9.0]

    def test_cells_are_written_by_the_formatter(self, table: QTableView) -> None:
        configure_item_view(
            table, _model([("BTC", 1.5)]), _SPECS, formatter=_ShoutingFormatter()
        )
        delegate = table.itemDelegate()
        index = table.model().index(0, 1)
        option = QStyleOptionViewItem()
        delegate.initStyleOption(option, index)

        assert option.text == "<price:1.5>"

    def test_a_model_with_other_columns_is_refused(self, table: QTableView) -> None:
        with pytest.raises(ValueError, match="3 columns and 2 specs"):
            configure_item_view(table, QStandardItemModel(0, 3), _SPECS)

    def test_two_stretching_columns_are_refused(self, table: QTableView) -> None:
        specs = (
            ColumnSpec("a", "A", ColumnKind.TEXT, stretch=True),
            ColumnSpec("b", "B", ColumnKind.TEXT, stretch=True),
        )
        with pytest.raises(ValueError, match="only one column stretches"):
            configure_item_view(table, QStandardItemModel(0, 2), specs)

    def test_a_tree_view_is_configured_too(self, qtbot) -> None:
        tree = QTreeView()
        qtbot.addWidget(tree)
        configure_item_view(tree, _model([("BTC", 1.0)]), _SPECS)
        assert tree.isSortingEnabled()


class TestTheGuard:
    def test_it_finds_a_hand_built_table(self, qtbot) -> None:
        root = QWidget()
        qtbot.addWidget(root)
        configure_item_view(QTableView(root), _model([]), _SPECS)
        loose = QTableView(root)
        loose.setObjectName("loose")

        (finding,) = find_unconfigured_item_views(root)

        assert finding.object_name == "loose"

    def test_a_combo_box_popup_is_not_a_finding(self, qtbot) -> None:
        root = QWidget()
        qtbot.addWidget(root)
        QComboBox(root).setView(QTreeView())

        assert find_unconfigured_item_views(root) == ()


class TestEmptyState:
    def test_the_instruction_shows_while_there_are_no_rows(self, qtbot) -> None:
        # Not the fixture: the stack takes ownership of the view, so only
        # the stack is registered for teardown.
        table = QTableView()
        model = _model([])
        configure_item_view(table, model, _SPECS)
        stack = EmptyStateStack(table, "No bots yet. Use Bots, New bot to create one.")
        qtbot.addWidget(stack)
        assert stack.currentWidget() is not table

        model.appendRow([QStandardItem("BTC"), QStandardItem("1")])

        assert stack.currentWidget() is table

    def test_a_view_without_a_model_is_refused(self, table: QTableView) -> None:
        with pytest.raises(ValueError, match="model"):
            EmptyStateStack(table, "Nothing here.")


class TestReadoutForm:
    def test_values_are_formatted_by_kind_and_right_aligned(self, qtbot) -> None:
        form = ReadoutForm(
            (
                ColumnSpec("balance", "Balance", ColumnKind.MONEY),
                ColumnSpec("change", "Change", ColumnKind.PERCENT),
                ColumnSpec("held", "Held for", ColumnKind.DURATION),
            )
        )
        qtbot.addWidget(form)

        form.set_values(
            {"balance": 12500.5, "change": 1.234, "held": timedelta(hours=2, minutes=5)}
        )

        assert form.value_text("balance") == "12,500.5"
        assert form.value_text("change") == "1.23%"
        assert form.value_text("held") == "2:05:00"
        label = form.findChild(QWidget, "readout::balance")
        assert label is not None and label.alignment() == _RIGHT  # type: ignore[attr-defined]

    def test_an_unknown_key_is_refused(self, qtbot) -> None:
        form = ReadoutForm((ColumnSpec("balance", "Balance", ColumnKind.MONEY),))
        qtbot.addWidget(form)
        with pytest.raises(KeyError, match="no read-out row"):
            form.set_values({"balanse": 1.0})


class TestPlainFormatter:
    def test_none_is_empty_and_text_is_kept(self) -> None:
        formatter = PlainValueFormatter()
        assert formatter.format(ColumnKind.PRICE, None, FormatContext("p")) == ""
        assert formatter.format(ColumnKind.SIDE, "BUY", FormatContext("s")) == "BUY"


class TestItemViewStateStore:
    def test_moved_columns_come_back_after_a_restart(self, qtbot) -> None:
        first = QTableView()
        qtbot.addWidget(first)
        configure_item_view(first, _model([("BTC", 1.0)]), _SPECS)
        first.horizontalHeader().moveSection(1, 0)
        store = ItemViewStateStore()
        store.register("bots.list", first.horizontalHeader())
        saved = store.capture_state()

        second = QTableView()
        qtbot.addWidget(second)
        configure_item_view(second, _model([("BTC", 1.0)]), _SPECS)
        restarted = ItemViewStateStore()
        restarted.register("bots.list", second.horizontalHeader())
        restarted.restore_state(saved)

        assert second.horizontalHeader().visualIndex(1) == 0

    def test_an_unreadable_entry_keeps_the_default(self, qtbot) -> None:
        view = QTableView()
        qtbot.addWidget(view)
        configure_item_view(view, _model([]), _SPECS)
        store = ItemViewStateStore()
        store.register("v", view.horizontalHeader())

        store.restore_state({"v": "%%%"})

        assert view.horizontalHeader().visualIndex(1) == 1


def test_a_negative_duration_keeps_its_sign() -> None:
    formatter = PlainValueFormatter()
    assert formatter.format(ColumnKind.DURATION, -30, FormatContext("d")) == "-0:00:30"


def test_a_destroyed_view_is_forgotten(qtbot) -> None:
    view = QTableView()
    configure_item_view(view, _model([]), _SPECS)
    store = ItemViewStateStore()
    store.register("gone", view.horizontalHeader())

    view.deleteLater()

    qtbot.waitUntil(lambda: store.capture_state() == {})


def test_an_empty_table_fits_its_columns_when_the_first_rows_arrive(qtbot) -> None:
    view = QTableView()
    qtbot.addWidget(view)
    model = _model([])
    configure_item_view(view, model, _SPECS)
    before = view.columnWidth(1)

    wide = QStandardItem()
    wide.setData(123456789012345.5, Qt.ItemDataRole.DisplayRole)
    model.appendRow([QStandardItem("BTC"), wide])

    assert view.columnWidth(1) > before
