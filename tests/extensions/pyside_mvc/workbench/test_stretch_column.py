"""The stretch column fills a wide view but never squeezes below its
content, a narrow view scrolls instead of dropping columns, and a view asks
for the width of its columns (`EPIC-008F`; the reference consumer's
`EPIC-033N` Watchlist)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHeaderView,
    QTableView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from sagittarius_engine.extensions.pyside_mvc import (
    ColumnKind,
    ColumnSpec,
    configure_item_view,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.stretch_column import (
    content_width,
)

_SPECS = (
    ColumnSpec("symbol", "Symbol", ColumnKind.TEXT, stretch=True),
    ColumnSpec("price", "Last price", ColumnKind.PRICE),
    ColumnSpec("volume", "Volume", ColumnKind.QUANTITY),
)
_PANEL_HEIGHT = 240
_NARROW = 120
_WIDE = 900


def _quotes(symbol: str = "BNBUSDT") -> QStandardItemModel:
    model = QStandardItemModel(0, len(_SPECS))
    cells = [QStandardItem() for _ in _SPECS]
    for item, value in zip(cells, (symbol, 600.5, 1200.0), strict=True):
        item.setData(value, Qt.ItemDataRole.DisplayRole)
    model.appendRow(cells)
    return model


@dataclass
class _Shown:
    """The view and the panel holding it. The test keeps this object: qtbot
    holds the panel weakly, and a collected panel deletes the view with it."""

    view: QTableView
    panel: QWidget


def _shown(qtbot, width: int, symbol: str = "BNBUSDT") -> _Shown:
    panel = QWidget()
    qtbot.addWidget(panel)
    view = QTableView(panel)
    configure_item_view(view, _quotes(symbol), _SPECS)
    QVBoxLayout(panel).addWidget(view)
    panel.resize(width, _PANEL_HEIGHT)
    panel.show()
    qtbot.waitExposed(panel)
    return _Shown(view, panel)


@pytest.mark.parametrize("width", [_NARROW, _WIDE])
def test_the_stretch_column_never_shows_less_than_its_content(qtbot, width) -> None:
    """Qt's own `Stretch` mode gave the first column what the others left:
    nothing, in a narrow dock, so the Watchlist read "Sym" over "BN…"."""
    shown = _shown(qtbot, width)
    view = shown.view
    header = view.horizontalHeader()

    assert header.sectionSize(0) >= content_width(view, 0)
    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Interactive


def test_a_view_leaving_the_stretch_column_too_little_keeps_it_whole(qtbot) -> None:
    """The Watchlist's case: the dock is a little wider than the columns
    after the first, so Qt's `Stretch` left the first a sliver of its own."""
    shown = _shown(qtbot, _WIDE)
    view = shown.view
    others = content_width(view, 1) + content_width(view, 2)
    frame = shown.panel.width() - view.viewport().width()
    sliver = content_width(view, 0) // 3

    shown.panel.resize(frame + others + sliver, _PANEL_HEIGHT)
    qtbot.waitUntil(lambda: view.viewport().width() <= others + sliver)

    assert view.horizontalHeader().sectionSize(0) >= content_width(view, 0)


def test_a_wide_view_is_filled_by_the_stretch_column(qtbot) -> None:
    shown = _shown(qtbot, _WIDE)
    view = shown.view

    header = view.horizontalHeader()
    assert header.length() == view.viewport().width()
    assert header.sectionSize(0) > content_width(view, 0)
    # Filled by the filler, not by Qt's `Stretch`, so the person can still
    # resize it, and a narrow view cannot squeeze it.
    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Interactive


def test_a_narrow_view_scrolls_with_every_column_whole(qtbot) -> None:
    # A symbol wider than Qt's default section size, which is what a
    # `Stretch` column keeps when the viewport leaves it nothing.
    shown = _shown(qtbot, _NARROW, "ETHUSDT_PERPETUAL_DELIVERY")
    view = shown.view
    header = view.horizontalHeader()

    assert header.length() > view.viewport().width()
    assert view.horizontalScrollBar().maximum() > 0
    for column in range(header.count()):
        assert header.sectionSize(column) >= content_width(view, column)


def test_the_view_asks_for_the_width_of_its_columns(qtbot) -> None:
    """A dock opens at its content's size hint: a hint taken from the columns
    gives the dock room for all of them, where a scroll area's default is a
    fixed 256 px."""
    view = QTableView()
    qtbot.addWidget(view)
    # Wider than Qt's default hint for a scroll area, which ignores content.
    configure_item_view(view, _quotes("ETHUSDT_PERPETUAL_DELIVERY_250627"), _SPECS)
    natural = sum(content_width(view, column) for column in range(len(_SPECS)))

    assert view.sizeHint().width() >= natural


def test_a_tree_widget_stretch_column_fills_it_too(qtbot) -> None:
    tree = QTreeWidget()
    qtbot.addWidget(tree)
    configure_item_view(tree, None, _SPECS)
    tree.addTopLevelItem(QTreeWidgetItem(["BNBUSDT", "600.5", "1200"]))
    tree.resize(_WIDE, _PANEL_HEIGHT)
    tree.show()
    qtbot.waitExposed(tree)

    header = tree.header()
    assert header.length() == tree.viewport().width()
    assert header.sectionSize(0) > content_width(tree, 0)
    assert header.sectionResizeMode(0) is QHeaderView.ResizeMode.Interactive
