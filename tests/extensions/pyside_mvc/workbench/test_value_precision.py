"""A value is written in the precision its column or its row is quoted in,
not by magnitude: a tick size is per symbol, and only the consumer knows it
(`EPIC-008F`; the reference consumer's `EPIC-033N`)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QStyleOptionViewItem, QTableView

from sagittarius_engine.extensions.pyside_mvc import (
    PRECISION_ROLE,
    ColumnKind,
    ColumnSpec,
    FormatContext,
    PlainValueFormatter,
    Precision,
    ReadoutForm,
    configure_item_view,
)

_TICK = Precision(Decimal("0.05"))
_STEP = Precision(Decimal("0.001"))


class _RecordingFormatter:
    """An `IValueFormatter` that keeps every context it was given."""

    def __init__(self) -> None:
        self.contexts: list[FormatContext] = []

    def format(self, kind: ColumnKind, value: object, context: FormatContext) -> str:
        self.contexts.append(context)
        return str(value)


def _cell_text(view: QTableView, row: int, column: int) -> str:
    option = QStyleOptionViewItem()
    view.itemDelegate().initStyleOption(option, view.model().index(row, column))
    return option.text  # type: ignore[attr-defined]


def _rows(*cells: tuple[float, Precision | None]) -> QStandardItemModel:
    """One price column; each cell may carry its own precision."""
    model = QStandardItemModel(0, 1)
    for price, precision in cells:
        item = QStandardItem()
        item.setData(price, Qt.ItemDataRole.DisplayRole)
        if precision is not None:
            item.setData(precision, PRECISION_ROLE)
        model.appendRow([item])
    return model


class TestPrecision:
    def test_a_quantum_rounds_to_its_nearest_step(self) -> None:
        assert _TICK.quantize(64250.12) == Decimal("64250.10")
        assert _TICK.quantize(64250.13) == Decimal("64250.15")
        assert _TICK.decimals == 2

    def test_decimal_places_are_a_power_of_ten_quantum(self) -> None:
        precision = Precision.of_decimals(3)
        assert precision.quantum == Decimal("0.001")
        assert precision.quantize(Decimal("1.23456")) == Decimal("1.235")

    def test_a_float_is_read_as_its_shortest_text(self) -> None:
        # 2.675 is 2.67499999... in binary; one tenth of a cent is its text.
        assert Precision.of_decimals(2).quantize(0.125) == Decimal("0.12")
        assert Precision.of_decimals(2).quantize(2.675) == Decimal("2.68")

    def test_a_quantum_above_one_has_no_decimals(self) -> None:
        assert Precision(Decimal("10")).decimals == 0
        assert Precision(Decimal("10")).quantize(1234) == Decimal("1230")

    def test_a_large_value_at_a_fine_quantum_does_not_raise(self) -> None:
        # 28 significant digits, the default context, would refuse this.
        assert Precision.of_decimals(8).quantize(1e25) == Decimal(
            "10000000000000000000000000.00000000"
        )

    @pytest.mark.parametrize("quantum", [Decimal(0), Decimal(-1), Decimal("NaN")])
    def test_a_quantum_that_is_not_positive_is_refused(self, quantum: Decimal) -> None:
        with pytest.raises(ValueError, match="positive and finite"):
            Precision(quantum)

    def test_a_float_quantum_is_refused(self) -> None:
        with pytest.raises(TypeError, match="Decimal"):
            Precision(0.1)  # type: ignore[arg-type]


class TestPlainFormatterWithAHint:
    @pytest.mark.parametrize(
        "kind", [ColumnKind.PRICE, ColumnKind.QUANTITY, ColumnKind.MONEY]
    )
    def test_a_number_is_written_to_its_quantum(self, kind: ColumnKind) -> None:
        context = FormatContext("x", _TICK)
        assert PlainValueFormatter().format(kind, 64250.13, context) == "64,250.15"

    def test_a_decimal_keeps_trailing_zeros_the_quantum_asks_for(self) -> None:
        context = FormatContext("qty", _STEP)
        text = PlainValueFormatter().format(ColumnKind.QUANTITY, Decimal("2"), context)
        assert text == "2.000"

    def test_a_percent_ignores_a_tick(self) -> None:
        context = FormatContext("change", _STEP)
        assert PlainValueFormatter().format(ColumnKind.PERCENT, 1.5, context) == "1.50%"

    def test_without_a_hint_nothing_changes(self) -> None:
        formatter = PlainValueFormatter()
        assert formatter.format(ColumnKind.PRICE, 1.5, FormatContext("p")) == "1.5"


class TestTheDelegateHandsThePrecisionOn:
    def test_a_cells_own_precision_reaches_the_formatter(self, qtbot) -> None:
        view = QTableView()
        qtbot.addWidget(view)
        configure_item_view(
            view,
            _rows((64250.13, _TICK), (0.12345, _STEP)),
            (ColumnSpec("price", "Price", ColumnKind.PRICE),),
        )

        assert _cell_text(view, 0, 0) == "64,250.15"
        assert _cell_text(view, 1, 0) == "0.123"

    def test_the_column_precision_applies_where_a_cell_has_none(self, qtbot) -> None:
        view = QTableView()
        qtbot.addWidget(view)
        recorder = _RecordingFormatter()
        configure_item_view(
            view,
            _rows((1.0, None), (2.0, _STEP)),
            (ColumnSpec("price", "Price", ColumnKind.PRICE, precision=_TICK),),
            formatter=recorder,
        )

        recorder.contexts.clear()  # fitting the columns wrote every cell once
        _cell_text(view, 0, 0)
        _cell_text(view, 1, 0)

        assert [context.precision for context in recorder.contexts] == [_TICK, _STEP]

    def test_a_readout_row_uses_its_spec_precision(self, qtbot) -> None:
        form = ReadoutForm(
            (ColumnSpec("entry", "Entry", ColumnKind.PRICE, precision=_TICK),)
        )
        qtbot.addWidget(form)

        form.set_values({"entry": 101.02})

        assert form.value_text("entry") == "101.00"
