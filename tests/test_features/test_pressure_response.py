"""Tests for sovereign.features.pressure_response."""

from __future__ import annotations

from typing import Optional

import polars as pl
import pytest

from sovereign.features.pressure_response import PressureResponseFeatures


def _make_df(
    spi_values: list[float],
    runs_values: list[int],
    legal: Optional[list[bool]] = None,
) -> pl.DataFrame:
    n = len(spi_values)
    if legal is None:
        legal = [True] * n
    return pl.DataFrame(
        {
            "batter_id": ["p001"] * n,
            "spi_total": spi_values,
            "runs_batter": runs_values,
            "is_legal_ball": legal,
            "is_boundary": [r >= 4 for r in runs_values],
        }
    )


class TestPressureResponseSR:
    """Strike rate computed correctly at each SPI tier."""

    def test_sr_low_tier(self) -> None:
        # 15 balls in low tier: all score 2 runs → SR = 200
        df = _make_df([1.0] * 15, [2] * 15)
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", df)
        assert result["sr_spi_low"] == pytest.approx(200.0)

    def test_sr_medium_tier(self) -> None:
        # 15 balls in medium tier: all score 4 → SR = 400
        df = _make_df([4.0] * 15, [4] * 15)
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", df)
        assert result["sr_spi_medium"] == pytest.approx(400.0)

    def test_sr_high_tier(self) -> None:
        # 12 balls in high tier: all score 1 → SR = 100
        df = _make_df([7.0] * 12, [1] * 12)
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", df)
        assert result["sr_spi_high"] == pytest.approx(100.0)

    def test_sr_extreme_tier(self) -> None:
        # 10 balls in extreme tier (spi=9): all score 0 → SR = 0
        df = _make_df([9.0] * 10, [0] * 10)
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", df)
        assert result["sr_spi_extreme"] == pytest.approx(0.0)


class TestDotAndBoundaryPct:
    """Dot and boundary percentages computed correctly."""

    def test_dot_pct_calculation(self, spi_tier_df: pl.DataFrame) -> None:
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", spi_tier_df)
        # Each tier has 15 balls
        for tier in ("low", "medium", "high", "extreme"):
            key = f"dot_pct_spi_{tier}"
            assert result[key] is not None, f"{key} should not be None"
            assert 0.0 <= result[key] <= 100.0

    def test_boundary_pct_all_boundaries(self) -> None:
        # All balls are boundaries (runs >= 4)
        df = _make_df([1.0] * 15, [4] * 15)
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", df)
        assert result["boundary_pct_spi_low"] == pytest.approx(100.0)

    def test_boundary_pct_no_boundaries(self) -> None:
        df = _make_df([1.0] * 15, [1] * 15)
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", df)
        assert result["boundary_pct_spi_low"] == pytest.approx(0.0)


class TestInsufficientData:
    """Returns None for tiers with fewer than min_deliveries."""

    def test_none_when_below_threshold(self) -> None:
        # Only 5 balls in low tier (below default 10)
        df = _make_df([1.0] * 5, [1] * 5)
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", df)
        assert result["sr_spi_low"] is None
        assert result["dot_pct_spi_low"] is None
        assert result["boundary_pct_spi_low"] is None

    def test_returns_none_not_zero(self) -> None:
        # Verify None is used (not 0) for sparse tiers
        df = _make_df([1.0] * 3, [0] * 3)
        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("p001", df)
        assert result["sr_spi_low"] is None

    def test_missing_columns_returns_nulls(self) -> None:
        df = pl.DataFrame({"batter_id": ["p001"], "runs_batter": [1]})
        prf = PressureResponseFeatures()
        result = prf.compute("p001", df)
        for v in result.values():
            assert v is None
