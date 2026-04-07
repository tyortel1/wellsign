"""Unit tests for util/calc.py — the financial math is legally important."""

from __future__ import annotations

from wellsign.util.calc import (
    compute_amounts,
    quantize_wi,
    round_money,
    validate_dollar_sum,
    validate_wi_sum,
)


def test_round_money_half_up():
    assert round_money(1.005) == 1.01
    assert round_money(1.004) == 1.00
    assert round_money(0) == 0.0


def test_quantize_wi_eight_places():
    assert quantize_wi(0.0123456789) == 0.01234568
    assert quantize_wi(0.01) == 0.01


def test_compute_amounts_basic():
    # 1% of $1,500,000 LLG and $2,750,000 DHC
    llg, dhc = compute_amounts(0.01, 1_500_000, 2_750_000)
    assert llg == 15_000.00
    assert dhc == 27_500.00


def test_compute_amounts_fractional():
    # 2.5% of $1,000,000 = $25,000.00
    llg, dhc = compute_amounts(0.025, 1_000_000, 0)
    assert llg == 25_000.00
    assert dhc == 0.0


def test_compute_amounts_rounding():
    # 0.333333% of $1,000 -> $3.3333... -> rounds to $3.33
    llg, _ = compute_amounts(0.00333333, 1_000, 0)
    assert llg == 3.33


def test_validate_wi_sum_exactly_one():
    res = validate_wi_sum([0.5, 0.25, 0.25])
    assert res.ok
    assert res.total == 1.0
    assert res.delta == 0.0


def test_validate_wi_sum_within_tolerance():
    # Off by 5e-8 -> still ok (tolerance is 1e-7)
    res = validate_wi_sum([0.99999995])
    assert res.ok


def test_validate_wi_sum_outside_tolerance():
    res = validate_wi_sum([0.5, 0.25])  # sums to 0.75
    assert not res.ok
    assert res.delta < 0


def test_validate_wi_sum_empty():
    res = validate_wi_sum([])
    assert not res.ok


def test_validate_dollar_sum_within_tolerance():
    # 5 investors at $30,000 each = $150,000 expected
    amounts = [30_000.00, 30_000.00, 30_000.00, 30_000.00, 30_000.00]
    res = validate_dollar_sum(amounts, 150_000.00)
    assert res.ok
    assert res.delta == 0.0


def test_validate_dollar_sum_just_outside_tolerance():
    # $0.11 over -> fails
    res = validate_dollar_sum([100_000.11], 100_000.00)
    assert not res.ok


def test_validate_dollar_sum_just_inside_tolerance():
    # $0.10 over -> passes (boundary)
    res = validate_dollar_sum([100_000.10], 100_000.00)
    assert res.ok
