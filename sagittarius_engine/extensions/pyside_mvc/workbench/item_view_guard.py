"""Finds tables and trees no spec configured (`EPIC-008F`).

A consumer's test boots its window and calls this: every `QTableView` and
`QTreeView` it shows should have come through `configure_item_view()`, which
marks the view. Views inside a combo box's popup are Qt's own and skipped.
Same shape as `find_deep_imports()`: findings a test asserts empty.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QComboBox, QTableView, QTreeView, QWidget

from sagittarius_engine.extensions.pyside_mvc.workbench.configure_item_view import (
    CONFIGURED_PROPERTY,
)


@dataclass(frozen=True, slots=True)
class UnconfiguredItemView:
    class_name: str
    object_name: str


def _inside_combo_box(widget: QWidget) -> bool:
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QComboBox):
            return True
        parent = parent.parentWidget()
    return False


def find_unconfigured_item_views(root: QWidget) -> tuple[UnconfiguredItemView, ...]:
    """Every table or tree under `root` that `configure_item_view()` did not set up."""
    found: list[UnconfiguredItemView] = []
    for view in root.findChildren(QTableView) + root.findChildren(QTreeView):
        if view.property(CONFIGURED_PROPERTY) or _inside_combo_box(view):
            continue
        found.append(UnconfiguredItemView(type(view).__name__, view.objectName()))
    return tuple(found)
