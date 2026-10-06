"""How one value of one kind is written (`EPIC-008F`).

The engine decides *where* a value is formatted (one delegate, one read-out
form) so no screen formats its own; the consumer decides *how* (a price's
precision is a symbol's tick size, which only the consumer knows). The
`PlainValueFormatter` is the engine's default: correct, unopinionated.

The consumer's knowledge reaches the formatter through `FormatContext`: the
column's key, and, when the column or the row knows it, the `Precision` a
value is quoted in (`ColumnSpec.precision`, or a model's `PRECISION_ROLE` for
one cell). A formatter that ignores `precision` keeps working unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from sagittarius_engine.extensions.pyside_mvc.workbench.column_kind import ColumnKind
from sagittarius_engine.extensions.pyside_mvc.workbench.value_precision import (
    Precision,
)

_PERCENT_DIGITS = 2
_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

type DisplayValue = str | int | float | Decimal | datetime | timedelta | None

#: The kinds a `Precision` hint applies to in `PlainValueFormatter`. A percent
#: and a duration have units of their own; a quantum is a price's tick, a
#: quantity's step or a currency's smallest unit.
_QUANTIZED = frozenset({ColumnKind.PRICE, ColumnKind.QUANTITY, ColumnKind.MONEY})


@dataclass(frozen=True, slots=True)
class FormatContext:
    """Which column or read-out row the value belongs to, and the precision
    it is quoted in when the column or its row knows one."""

    key: str
    #: `None`: no hint; the formatter decides (by magnitude, say).
    precision: Precision | None = None


class IValueFormatter(Protocol):
    """Turns a raw value into the text a display shows."""

    def format(
        self, kind: ColumnKind, value: DisplayValue, context: FormatContext
    ) -> str:
        """Never raises for a value of the declared kind; `None` is empty."""
        ...


def _duration_text(seconds: float) -> str:
    # The sign first: `divmod` floors, so -30 s would read -1:59:30.
    sign = "-" if seconds < 0 else ""
    whole = int(abs(seconds))
    hours, remainder = divmod(whole, _SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, _SECONDS_PER_MINUTE)
    return f"{sign}{hours}:{minutes:02d}:{secs:02d}"


class PlainValueFormatter:
    """The default: numbers with grouping, percents with two decimals,
    timestamps to the second, durations as h:mm:ss. A price, quantity or
    money value with a `precision` hint is rounded to its quantum and written
    with exactly the quantum's decimals."""

    def format(
        self, kind: ColumnKind, value: DisplayValue, context: FormatContext
    ) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime(_TIMESTAMP_FORMAT)
        if isinstance(value, timedelta):
            return _duration_text(value.total_seconds())
        if isinstance(value, str):
            return value
        if kind is ColumnKind.PERCENT:
            return f"{value:,.{_PERCENT_DIGITS}f}%"
        if kind is ColumnKind.DURATION:
            return _duration_text(float(value))
        if context.precision is not None and kind in _QUANTIZED:
            quantized = context.precision.quantize(value)
            return f"{quantized:,.{context.precision.decimals}f}"
        return f"{value:,}"
