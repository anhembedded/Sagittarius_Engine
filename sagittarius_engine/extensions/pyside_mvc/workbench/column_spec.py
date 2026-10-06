"""One column of a table, declared as data (`EPIC-008F`).

A table is a list of `ColumnSpec`s: the consumer says which columns and of
what kind; `configure_item_view()` does everything the kind decides.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from sagittarius_engine.extensions.pyside_mvc.workbench.column_kind import ColumnKind
from sagittarius_engine.extensions.pyside_mvc.workbench.value_precision import (
    Precision,
)


class Selection(Enum):
    """How many rows the user may select. Always whole rows."""

    SINGLE = "single"
    EXTENDED = "extended"


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """`key` names the value for the formatter; `title` is the header text."""

    key: str
    title: str
    kind: ColumnKind
    #: The one column that takes the remaining width; others fit their content.
    stretch: bool = False
    #: The precision every value of this column is quoted in, handed to the
    #: formatter as `FormatContext.precision`. A cell's own hint
    #: (`PRECISION_ROLE`) wins: a price column's tick is usually per symbol.
    precision: Precision | None = None


def spec_problems(specs: Sequence[ColumnSpec]) -> tuple[str, ...]:
    """What makes a column list unusable, empty when nothing does."""
    problems: list[str] = []
    if not specs:
        problems.append("a table has at least one column")
    keys = [spec.key for spec in specs]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        problems.append(f"column keys {duplicates} appear more than once")
    stretched = [spec.key for spec in specs if spec.stretch]
    if len(stretched) > 1:
        problems.append(f"only one column stretches; {stretched} all do")
    return tuple(problems)
