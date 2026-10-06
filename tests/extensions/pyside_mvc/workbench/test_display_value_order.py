"""A view sorts the raw values a model holds — `Decimal`s and `datetime`s
included, which Qt's own comparison leaves in model order — with unknown
values last ascending (`EPIC-008F`; the reference consumer's `EPIC-033N`)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTableView

from sagittarius_engine.extensions.pyside_mvc import (
    ColumnKind,
    ColumnSpec,
    configure_item_view,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.display_value_order import (
    display_value_less_than,
)

_SPEC = (ColumnSpec("value", "Value", ColumnKind.TEXT),)


def _model(values: Sequence[object]) -> QStandardItemModel:
    model = QStandardItemModel(0, 1)
    for value in values:
        item = QStandardItem()
        item.setData(value, Qt.ItemDataRole.DisplayRole)
        model.appendRow([item])
    return model


def _sorted(qtbot, values: Sequence[object], order: Qt.SortOrder) -> list[object]:
    view = QTableView()
    qtbot.addWidget(view)
    proxy = configure_item_view(view, _model(values), _SPEC)
    view.sortByColumn(0, order)
    return [proxy.index(row, 0).data() for row in range(proxy.rowCount())]


_ASCENDING = Qt.SortOrder.AscendingOrder
_DESCENDING = Qt.SortOrder.DescendingOrder


class TestTheProxySortsWhatQtCannot:
    def test_decimals_sort_by_value(self, qtbot) -> None:
        values = [Decimal("10.5"), Decimal("-2"), Decimal("3")]
        assert _sorted(qtbot, values, _ASCENDING) == [
            Decimal("-2"),
            Decimal("3"),
            Decimal("10.5"),
        ]

    def test_moments_sort_in_time(self, qtbot) -> None:
        late = datetime(2026, 10, 6, tzinfo=UTC)
        early = datetime(2024, 1, 1, tzinfo=UTC)
        middle = datetime(2025, 6, 1, tzinfo=UTC)
        assert _sorted(qtbot, [late, early, middle], _ASCENDING) == [
            early,
            middle,
            late,
        ]

    def test_unknown_sorts_last_ascending_and_first_descending(self, qtbot) -> None:
        values = [Decimal("2"), None, Decimal("1")]
        assert _sorted(qtbot, values, _ASCENDING) == [Decimal("1"), Decimal("2"), None]
        assert _sorted(qtbot, values, _DESCENDING) == [None, Decimal("2"), Decimal("1")]

    def test_numbers_of_every_type_sort_together(self, qtbot) -> None:
        values = [2.5, Decimal("1.25"), 3, 0.5]
        assert _sorted(qtbot, values, _ASCENDING) == [0.5, Decimal("1.25"), 2.5, 3]

    def test_text_keeps_the_proxys_case_setting(self, qtbot) -> None:
        view = QTableView()
        qtbot.addWidget(view)
        proxy = configure_item_view(view, _model(["b", "A", "a", "B"]), _SPEC)
        proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        view.sortByColumn(0, _ASCENDING)

        texts = [proxy.index(row, 0).data() for row in range(4)]
        assert [text.lower() for text in texts] == ["a", "a", "b", "b"]


class TestTheOrder:
    def test_a_naive_moment_is_utc_and_does_not_raise_against_an_aware_one(
        self,
    ) -> None:
        naive = datetime(2026, 1, 1, 12)
        aware = datetime(2026, 1, 1, 13, tzinfo=UTC)
        assert display_value_less_than(naive, aware)
        assert not display_value_less_than(aware, naive)

    @pytest.mark.parametrize("unknown", [None, float("nan"), Decimal("NaN")])
    def test_unknown_is_after_everything_and_equal_to_itself(
        self, unknown: object
    ) -> None:
        assert display_value_less_than(1, unknown)
        assert not display_value_less_than(unknown, 1)
        assert not display_value_less_than(unknown, None)

    def test_mixed_kinds_order_by_kind(self) -> None:
        ordered: list[object] = [
            1,
            timedelta(seconds=1),
            datetime(2026, 1, 1, tzinfo=UTC),
            "text",
            frozenset({"something else"}),
            None,
        ]
        for left, right in zip(ordered[:-1], ordered[1:], strict=True):
            assert display_value_less_than(left, right)
            assert not display_value_less_than(right, left)

    def test_durations_sort_by_length(self) -> None:
        assert display_value_less_than(timedelta(minutes=1), timedelta(hours=1))
