"""Label-value read-outs, written by kind (`EPIC-008F`).

An account summary or a run's metrics is a list of facts, not a table: a
`QFormLayout` of labels and values, the platform's own form arrangement. The
values go through the same `IValueFormatter` as every table cell, so a price
in a read-out and the same price in a table read alike.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from sagittarius_engine.extensions.pyside_mvc.workbench.column_spec import (
    ColumnSpec,
    spec_problems,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.i_value_formatter import (
    DisplayValue,
    FormatContext,
    IValueFormatter,
    PlainValueFormatter,
)

_VALUE_ALIGNMENT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


class ReadoutForm(QWidget):
    """One row per spec: its title, then its value, right-aligned."""

    def __init__(
        self,
        specs: Sequence[ColumnSpec],
        formatter: IValueFormatter | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        problems = spec_problems(specs)
        if problems:
            raise ValueError("; ".join(problems))
        self._specs = {spec.key: spec for spec in specs}
        self._formatter = formatter or PlainValueFormatter()
        self._values: dict[str, QLabel] = {}
        layout = QFormLayout(self)
        for spec in specs:
            value = QLabel()
            value.setObjectName(f"readout::{spec.key}")
            value.setAlignment(_VALUE_ALIGNMENT)
            value.setTextFormat(Qt.TextFormat.PlainText)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addRow(spec.title, value)
            self._values[spec.key] = value

    def set_values(self, values: Mapping[str, DisplayValue]) -> None:
        """Writes the given values; keys left out keep their text."""
        unknown = sorted(set(values) - set(self._specs))
        if unknown:
            raise KeyError(f"no read-out row for {unknown}")
        for key, raw in values.items():
            spec = self._specs[key]
            context = FormatContext(key, spec.precision)
            text = self._formatter.format(spec.kind, raw, context)
            self._values[key].setText(text)

    def value_text(self, key: str) -> str:
        return self._values[key].text()
