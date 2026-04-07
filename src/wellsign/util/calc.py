"""Pure financial-math helpers for investor working interest and cash calls.

Money math goes through ``decimal.Decimal`` with explicit ROUND_HALF_UP so
the result matches what an operator's spreadsheet would produce. The DB
stores REAL (float64) — values cross the Decimal boundary at this layer.

Conventions:
  * working-interest is a fraction in [0, 1], stored to 8 decimal places
    (so 1.000000% participation = ``0.01000000``).
  * dollar amounts are quantised to two decimal places.
  * the WI sum across a project must be 1.00000000 ± 1e-7.
  * the per-investor LLG/DHC sums must equal the project totals ± $0.10.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

# Tolerances
WI_SUM_TOLERANCE = Decimal("0.0000001")     # 1e-7
DOLLAR_SUM_TOLERANCE = Decimal("0.10")      # $0.10

_TWO_PLACES = Decimal("0.01")
_EIGHT_PLACES = Decimal("0.00000001")
_ONE = Decimal("1")


def _to_decimal(value: float | int | Decimal | str | None) -> Decimal:
    if value is None:
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(value: float | Decimal) -> float:
    """Round to two decimal places, half-up. Returns a float for DB storage."""
    d = _to_decimal(value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    return float(d)


def quantize_wi(value: float | Decimal) -> float:
    """Round a WI fraction to 8 decimal places, half-up."""
    d = _to_decimal(value).quantize(_EIGHT_PLACES, rounding=ROUND_HALF_UP)
    return float(d)


def compute_amounts(
    wi_percent: float | Decimal,
    total_llg: float | Decimal,
    total_dhc: float | Decimal,
) -> tuple[float, float]:
    """Return ``(llg_amount, dhc_amount)`` for one investor.

    Both totals are required; pass ``0`` for whichever isn't applicable.
    """
    wi = _to_decimal(wi_percent)
    llg = (wi * _to_decimal(total_llg)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    dhc = (wi * _to_decimal(total_dhc)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    return float(llg), float(dhc)


# ---------------------------------------------------------------------------
# Sum validators
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WiSumResult:
    total: float        # sum as a float (display-friendly)
    delta: float        # signed deviation from 1.0
    ok: bool            # within WI_SUM_TOLERANCE


def validate_wi_sum(wi_percents: Iterable[float | Decimal]) -> WiSumResult:
    total = sum((_to_decimal(v) for v in wi_percents), Decimal(0))
    delta = total - _ONE
    ok = abs(delta) <= WI_SUM_TOLERANCE
    return WiSumResult(total=float(total), delta=float(delta), ok=ok)


@dataclass(frozen=True)
class DollarSumResult:
    total: float
    expected: float
    delta: float
    ok: bool


def validate_dollar_sum(
    amounts: Iterable[float | Decimal],
    expected_total: float | Decimal,
    tolerance: float | Decimal = DOLLAR_SUM_TOLERANCE,
) -> DollarSumResult:
    total = sum((_to_decimal(v) for v in amounts), Decimal(0))
    expected = _to_decimal(expected_total)
    tol = _to_decimal(tolerance)
    delta = total - expected
    ok = abs(delta) <= tol
    return DollarSumResult(
        total=float(total),
        expected=float(expected),
        delta=float(delta),
        ok=ok,
    )
