"""A row of a grouped `QTreeWidget` that sorts on its raw value
(`EPIC-008F`).

A `QTreeWidget` sorts by asking each item `operator<`, whose default compares
the two `DisplayRole` values the way Qt's proxy does — so a `Decimal` or a
`datetime` held raw, as `KindDelegate` expects, would not sort. A
`SpecTreeItem` compares them in `display_value_order`'s order instead, as
`SpecProxyModel` does for a model-backed view. A heading is a `SpecTreeItem`
too, or a plain `QTreeWidgetItem` holding text: sorting orders each parent's
children among themselves, so a group's rows stay under their heading.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

from sagittarius_engine.extensions.pyside_mvc.workbench.display_value_order import (
    display_value_less_than,
    needs_text_comparison,
)


class SpecTreeItem(QTreeWidgetItem):
    """Holds raw values in `DisplayRole` (`setData(column,
    Qt.ItemDataRole.DisplayRole, value)`), which the configured tree's
    delegate writes and its sort orders.

    Every sortable row under one heading is a `SpecTreeItem`: Qt compares two
    siblings with the left one's `operator<`, so a plain `QTreeWidgetItem`
    beside these orders by Qt's text comparison when it is on the left, and
    the level has no single order (review of PR #230). Headings, which are
    siblings only of other headings, may stay plain."""

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        tree = self.treeWidget()
        column = tree.sortColumn() if tree is not None else 0
        left = self.data(column, Qt.ItemDataRole.DisplayRole)
        right = other.data(column, Qt.ItemDataRole.DisplayRole)
        if needs_text_comparison(left, right):
            # Text orders as a `QTreeWidget` orders it by default: case
            # sensitive, not locale aware, by code point. Not
            # `super().__lt__`: PySide dispatches the base operator back to
            # this override, which recursed until the process crashed on the
            # first header click (found adopting PR #230).
            return str(left) < str(right)
        return display_value_less_than(left, right)
