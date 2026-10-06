"""The order of display values, for every sortable view (`EPIC-008F`).

A view sorts on the raw value a model serves, but Qt orders only what it can
convert: a Python `Decimal` or `datetime` reaches `QSortFilterProxyModel`'s
default `lessThan` as an opaque object, and a column of them stays in model
order whatever the header says (measured on PySide6 6.11: three `datetime`s
and three `Decimal`s, sorted ascending, came back unsorted). The reference
consumer worked around it by serving moments as POSIX seconds. This module is
the order instead, so a model hands over the value it holds.

The order, ascending:

1. numbers — `int`, `float`, `Decimal`, and any other `numbers.Real` such as
   a NumPy scalar — by value, compared exactly across the built-in types;
2. durations (`timedelta`);
3. moments (`datetime`); a naive one, or one whose zone gives no offset, is
   read as UTC, so a column of naive
   values keeps its own order and a mixed column does not raise;
4. text;
5. anything else, by its `str()`;
6. unknown last: `None` and NaN, as Qt already put an invalid value
   (`QAbstractItemModelPrivate::isVariantLessThan`).

Two values of different groups order by group, so a column that mixes them
still has one strict weak order, which a sort needs to be stable and finite.
Text against text is not decided here: Qt's own comparison honours the view's
case sensitivity and locale settings, so a caller hands that pair back to Qt
(`needs_text_comparison`).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import IntEnum
from numbers import Integral, Real


class _Group(IntEnum):
    NUMBER = 0
    DURATION = 1
    MOMENT = 2
    TEXT = 3
    OTHER = 4
    UNKNOWN = 5


type _Key = tuple[_Group, int | float | Decimal | timedelta | datetime | str]


def _is_unknown(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, Decimal):
        return value.is_nan()
    # Any real number, a NumPy NaN included, which would otherwise compare
    # equal to every number (review of PR #230).
    return isinstance(value, Real) and math.isnan(float(value))


def _sort_key(value: object) -> _Key:
    if _is_unknown(value):
        return (_Group.UNKNOWN, 0)
    if isinstance(value, int | float | Decimal):
        return (_Group.NUMBER, value)
    if isinstance(value, Real):
        # A number of another library (a NumPy scalar) orders by its value,
        # not its text (review of PR #230).
        return (
            _Group.NUMBER,
            int(value) if isinstance(value, Integral) else float(value),
        )
    if isinstance(value, timedelta):
        return (_Group.DURATION, value)
    if isinstance(value, datetime):
        # Naive, or carrying a zone that names no offset (`utcoffset()` is
        # None, which Python then treats as naive and refuses to compare
        # with an aware moment): read as UTC (review of PR #230).
        moment = value if value.utcoffset() is not None else value.replace(tzinfo=UTC)
        return (_Group.MOMENT, moment)
    if isinstance(value, str):
        return (_Group.TEXT, value)
    return (_Group.OTHER, str(value))


def needs_text_comparison(left: object, right: object) -> bool:
    """Both values are text, which the view's own collation orders."""
    return isinstance(left, str) and isinstance(right, str)


def display_value_less_than(left: object, right: object) -> bool:
    """Whether `left` sorts before `right` ascending, in the module's order.
    Never raises for two display values."""
    left_key = _sort_key(left)
    right_key = _sort_key(right)
    if left_key[0] != right_key[0]:
        return left_key[0] < right_key[0]
    if left_key[0] is _Group.UNKNOWN:
        return False
    # Same group, so the second elements are mutually comparable: numbers
    # with numbers (Python compares int, float and Decimal exactly), aware
    # moments with aware moments, durations, strings.
    return left_key[1] < right_key[1]  # type: ignore[operator]
