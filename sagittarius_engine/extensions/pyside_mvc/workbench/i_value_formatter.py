"""How one value of one kind is written (`EPIC-008F`).

The engine decides *where* a value is formatted (one delegate, one read-out
form) so no screen formats its own; the consumer decides *how* (a price's
precision is a symbol's tick size, which only the consumer knows). The
`PlainValueFormatter` is the engine's default: correct, unopinionated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from sagittarius_engine.extensions.pyside_mvc.workbench.column_kind import ColumnKind

_PERCENT_DIGITS = 2
_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

type DisplayValue = str | int | float | datetime | timedelta | None


@dataclass(frozen=True, slots=True)
class FormatContext:
    """Which column or read-out row the value belongs to."""

    key: str


class IValueFormatter(Protocol):
    """Turns a raw value into the text a display shows."""

    def format(
        self, kind: ColumnKind, value: DisplayValue, context: FormatContext
    ) -> str:
        """Never raises for a value of the declared kind; `None` is empty."""
        ...


def _duration_text(seconds: float) -> str:
    whole = int(seconds)
    hours, remainder = divmod(whole, _SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, _SECONDS_PER_MINUTE)
    return f"{hours}:{minutes:02d}:{secs:02d}"


class PlainValueFormatter:
    """The default: numbers with grouping, percents with two decimals,
    timestamps to the second, durations as h:mm:ss."""

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
        return f"{value:,}"
