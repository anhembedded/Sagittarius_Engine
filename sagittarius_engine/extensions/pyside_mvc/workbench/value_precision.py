"""The step a number moves in, as a hint to the formatter (`EPIC-008F`).

A price is quoted in ticks and a quantity traded in steps, and both are the
consumer's knowledge — usually per row, from the row's symbol. A formatter
that only sees the column cannot know them, so it can only round by
magnitude. `Precision` is the hint a column (`ColumnSpec.precision`) or a
model (`PRECISION_ROLE`, per cell) hands the formatter through
`FormatContext.precision`; a formatter that ignores it keeps working.

One shape for both ways a venue states precision: a quantum (`0.05`, `0.001`,
`10`) or a number of decimal places, which is the quantum `10**-places`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

_ONE = Decimal(1)
_DEFAULT_DIGITS = 28
#: The digit before the point that `adjusted()` does not count, and one more.
_SPARE_DIGITS = 2


def _decimal(value: int | float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(repr(value))
    return Decimal(int(value))


@dataclass(frozen=True, slots=True)
class Precision:
    """A positive, finite quantum: every written value is a whole number of
    them (`0.01` for a cent, `0.05` for a five-cent tick)."""

    quantum: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.quantum, Decimal):
            raise TypeError(
                f"a quantum is a Decimal, not {type(self.quantum).__name__}; "
                "a float cannot hold 0.1 exactly"
            )
        if not self.quantum.is_finite() or self.quantum <= 0:
            raise ValueError(f"a quantum is positive and finite, not {self.quantum}")

    @classmethod
    def of_decimals(cls, places: int) -> Precision:
        """`places` digits after the point: `of_decimals(2)` is a quantum of 0.01."""
        if places < 0:
            raise ValueError(f"decimal places are zero or more, not {places}")
        return cls(_ONE.scaleb(-places))

    @property
    def decimals(self) -> int:
        """How many digits after the point the quantum needs: 2 for `0.05`,
        0 for `10`."""
        exponent = self.quantum.normalize().as_tuple().exponent
        # Only a NaN or an infinity has a letter for an exponent, and the
        # constructor refused both.
        return max(0, -exponent) if isinstance(exponent, int) else 0

    def quantize(self, value: int | float | Decimal) -> Decimal:
        """`value` rounded to the nearest whole quantum (half to even), with
        exactly `decimals` digits after the point. A float is read as the
        shortest text that round-trips, so `0.1` is one tenth, not its binary
        neighbour. A NaN or an infinity comes back as it is."""
        number = _decimal(value)
        if not number.is_finite():
            return number
        # Enough significant digits for every one the result writes: the
        # default context's 28 would refuse a large float at a fine quantum.
        digits = max(_DEFAULT_DIGITS, number.adjusted() + self.decimals + _SPARE_DIGITS)
        with localcontext() as context:
            context.prec = digits
            steps = (number / self.quantum).to_integral_value(rounding=ROUND_HALF_EVEN)
            return (steps * self.quantum).quantize(_ONE.scaleb(-self.decimals))
