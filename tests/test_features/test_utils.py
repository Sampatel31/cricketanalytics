"""Tests for sovereign.features.utils."""

from __future__ import annotations

import polars as pl
import pytest

from sovereign.features.utils import (
    clamp,
    coefficient_of_variation,
    compute_boundary_pct,
    compute_dot_pct,
    compute_economy,
    compute_sr,
    normalize_score,
    rolling_mean,
    safe_divide,
)


class TestClamp:
    def test_below_min(self) -> None:
        assert clamp(-5.0, 0.0, 10.0) == 0.0

    def test_above_max(self) -> None:
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_within_range(self) -> None:
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_boundary_values(self) -> None:
        assert clamp(0.0, 0.0, 10.0) == 0.0
        assert clamp(10.0, 0.0, 10.0) == 10.0


class TestSafeDivide:
    def test_normal_division(self) -> None:
        assert safe_divide(10.0, 4.0) == pytest.approx(2.5)

    def test_zero_denominator_returns_default(self) -> None:
        assert safe_divide(5.0, 0.0) == 0.0

    def test_custom_default(self) -> None:
        assert safe_divide(5.0, 0.0, default=99.0) == 99.0

    def test_negative_numerator(self) -> None:
        assert safe_divide(-8.0, 2.0) == pytest.approx(-4.0)


class TestComputeSR:
    def test_standard(self) -> None:
        # 50 runs off 50 balls = SR 100
        assert compute_sr(50.0, 50.0) == pytest.approx(100.0)

    def test_zero_balls_returns_none(self) -> None:
        assert compute_sr(10.0, 0.0) is None

    def test_six_sixes(self) -> None:
        # 36 runs off 6 balls = SR 600 (no upper bound in this function)
        assert compute_sr(36.0, 6.0) == pytest.approx(600.0)


class TestComputeEconomy:
    def test_standard(self) -> None:
        # 24 runs off 6 balls (1 over) = economy 24
        assert compute_economy(24.0, 6.0) == pytest.approx(24.0)

    def test_zero_balls_returns_none(self) -> None:
        assert compute_economy(12.0, 0.0) is None


class TestComputeDotPct:
    def test_all_dots(self) -> None:
        assert compute_dot_pct(10.0, 10.0) == pytest.approx(100.0)

    def test_no_dots(self) -> None:
        assert compute_dot_pct(0.0, 10.0) == pytest.approx(0.0)

    def test_zero_balls(self) -> None:
        assert compute_dot_pct(5.0, 0.0) is None


class TestComputeBoundaryPct:
    def test_half_boundaries(self) -> None:
        assert compute_boundary_pct(5.0, 10.0) == pytest.approx(50.0)

    def test_zero_balls(self) -> None:
        assert compute_boundary_pct(3.0, 0.0) is None


class TestRollingMean:
    def test_output_length(self) -> None:
        s = pl.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = rolling_mean(s, window=3)
        assert len(result) == 5

    def test_no_nulls(self) -> None:
        s = pl.Series([1.0, 2.0, 3.0, 4.0])
        result = rolling_mean(s, window=2)
        assert result.null_count() == 0


class TestCoefficientOfVariation:
    def test_consistent_series(self) -> None:
        # All same values → std = 0 → CV = 0
        s = pl.Series([5.0, 5.0, 5.0, 5.0])
        cv = coefficient_of_variation(s)
        assert cv == pytest.approx(0.0, abs=1e-6)

    def test_empty_series(self) -> None:
        s = pl.Series([], dtype=pl.Float64)
        assert coefficient_of_variation(s) is None

    def test_zero_mean(self) -> None:
        s = pl.Series([0.0, 0.0, 0.0])
        assert coefficient_of_variation(s) is None


class TestNormalizeScore:
    def test_mid_value(self) -> None:
        assert normalize_score(5.0, 0.0, 10.0) == pytest.approx(0.5)

    def test_min_value(self) -> None:
        assert normalize_score(0.0, 0.0, 10.0) == pytest.approx(0.0)

    def test_max_value(self) -> None:
        assert normalize_score(10.0, 0.0, 10.0) == pytest.approx(1.0)

    def test_equal_min_max_returns_default(self) -> None:
        assert normalize_score(5.0, 5.0, 5.0) == pytest.approx(0.5)
