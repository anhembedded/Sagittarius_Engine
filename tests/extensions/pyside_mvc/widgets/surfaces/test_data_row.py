"""Tests for `widgets.surfaces.data_row.DataRow`."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from sagittarius_engine.extensions.pyside_mvc.widgets import (
    Column,
    DataRow,
    Panel,
    RowAction,
    StyleRole,
)

_COLUMNS = (
    Column("Symbol", 22),
    Column("Interval", 10, Qt.AlignmentFlag.AlignCenter),
    Column("Total", 18, Qt.AlignmentFlag.AlignRight),
)


def test_is_a_panel_with_one_cell_per_column(qtbot):
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    assert isinstance(row, Panel)
    assert row.columns == _COLUMNS
    assert row.cell_texts() == ["", "", ""]


def test_rejects_an_empty_column_spec(qtbot):
    with pytest.raises(ValueError, match="at least one column"):
        DataRow([])


def test_set_cells_fills_left_to_right(qtbot):
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    row.set_cells(["BTCUSDT", "1m", "1,204,551"])

    assert row.cell_texts() == ["BTCUSDT", "1m", "1,204,551"]


def test_set_cells_is_repeatable(qtbot):
    """The whole reason cells are filled rather than passed to the
    constructor: the consumer's gap row takes its data at construction and
    so cannot be refreshed, forcing its dialog to rebuild every row."""
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    row.set_cells(["BTCUSDT", "1m", "1"])
    row.set_cells(["ETHUSDT", "1h", "2"])

    assert row.cell_texts() == ["ETHUSDT", "1h", "2"]


@pytest.mark.parametrize("values", [["a"], ["a", "b", "c", "d"], []])
def test_wrong_value_count_is_refused(qtbot, values):
    """Padding or truncating would slide a record's columns out of line
    with the heading above them, and misaligned data still looks like
    data."""
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    with pytest.raises(ValueError, match="3 columns"):
        row.set_cells(values)


def test_alignment_comes_from_the_column_spec(qtbot):
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)

    assert row._cells[1].alignment() & Qt.AlignmentFlag.AlignCenter
    assert row._cells[2].alignment() & Qt.AlignmentFlag.AlignRight


def test_actions_emit_their_position(qtbot):
    row = DataRow(
        _COLUMNS,
        actions=[RowAction("KLines"), RowAction("Clear", StyleRole.DANGER_BUTTON)],
    )
    qtbot.addWidget(row)

    with qtbot.waitSignal(row.action_triggered, timeout=1000) as blocker:
        row.action_buttons[1].click()

    assert blocker.args == [1]


def test_an_action_can_be_hidden_per_row(qtbot):
    """The consumer's status row hides its "gaps" button on healthy
    records rather than disabling it."""
    row = DataRow(_COLUMNS, actions=[RowAction("Gaps")])
    qtbot.addWidget(row)

    row.set_action_visible(0, False)

    assert row.action_buttons[0].isVisibleTo(row) is False


def test_a_destructive_action_renders_differently(qtbot, fake_theme_bridge):
    row = DataRow(
        _COLUMNS,
        actions=[RowAction("Sync"), RowAction("Clear", StyleRole.DANGER_BUTTON)],
    )
    qtbot.addWidget(row)

    assert row.action_buttons[0].styleSheet() != row.action_buttons[1].styleSheet()


def test_a_cell_can_be_restyled(qtbot, fake_theme_bridge):
    row = DataRow(_COLUMNS)
    qtbot.addWidget(row)
    before = row._cells[1].styleSheet()

    row.set_cell_role(1, StyleRole.BADGE)

    assert row._cells[1].styleSheet() != before
