"""Tests for sovereign.features.phase_performance."""

from __future__ import annotations

import polars as pl
import pytest

from sovereign.features.phase_performance import (
    PhasePerformanceFeatures,
    _get_boundaries,
)


class TestPhaseBoundaries:
    """Phase boundaries are correct per format."""

    def test_t20i_boundaries(self) -> None:
        pp, mid = _get_boundaries("T20I")
        assert pp == 6
        assert mid == 15

    def test_odi_boundaries(self) -> None:
        pp, mid = _get_boundaries("ODI")
        assert pp == 10
        assert mid == 40

    def test_test_boundaries(self) -> None:
        pp, mid = _get_boundaries("TEST")
        assert pp == 10
        assert mid == 80

    def test_unknown_format_uses_default(self) -> None:
        pp, mid = _get_boundaries("UNKNOWN")
        assert pp == 6  # default
        assert mid == 15


class TestBatterPhaseMetrics:
    """SR and dot % computed correctly for batters at each phase."""

    def test_sr_increases_in_death(self, phase_df: pl.DataFrame) -> None:
        ppf = PhasePerformanceFeatures(min_deliveries=5)
        result = ppf.compute("p001", phase_df, "T20I", "batter")
        # phase_df has runs=1 in PP, 2 in middle, 4 in death
        assert result["sr_powerplay"] == pytest.approx(100.0)
        assert result["sr_middle"] == pytest.approx(200.0)
        assert result["sr_death"] == pytest.approx(400.0)

    def test_dot_pct_powerplay_no_dots(self, phase_df: pl.DataFrame) -> None:
        ppf = PhasePerformanceFeatures(min_deliveries=5)
        result = ppf.compute("p001", phase_df, "T20I", "batter")
        # All PP deliveries score 1 → no dots
        assert result["dot_pct_powerplay"] == pytest.approx(0.0)

    def test_batter_returns_none_for_bowling_metrics(
        self, phase_df: pl.DataFrame
    ) -> None:
        ppf = PhasePerformanceFeatures(min_deliveries=5)
        result = ppf.compute("p001", phase_df, "T20I", "batter")
        for phase in ("powerplay", "middle", "death"):
            assert result[f"economy_{phase}"] is None
            assert result[f"wicket_prob_{phase}"] is None


class TestBowlerPhaseMetrics:
    """Economy and wicket probability computed for bowlers."""

    def test_economy_computed(self) -> None:
        # 30 balls, 24 runs → 5 overs → economy = 24/5 = 4.8
        n = 30
        df = pl.DataFrame(
            {
                "batter_id": ["b001"] * n,
                "over_number": [1] * 6 + [2] * 6 + [3] * 6 + [8] * 6 + [17] * 6,
                "runs_batter": [0] * n,
                "runs_total": [0, 1, 0, 1, 0, 2] * 5,
                "is_legal_ball": [True] * n,
                "wicket": [False, False, True, False, False, False] * 5,
            }
        )
        ppf = PhasePerformanceFeatures(min_deliveries=5)
        result = ppf.compute("b001", df, "T20I", "bowler")
        assert result["economy_powerplay"] is not None
        assert result["wicket_prob_powerplay"] is not None
        assert result["sr_powerplay"] is None


class TestMissingPhases:
    """Graceful handling when a phase has no deliveries."""

    def test_none_for_missing_phase(self) -> None:
        # Only powerplay overs (1–6)
        n = 36
        df = pl.DataFrame(
            {
                "batter_id": ["p001"] * n,
                "over_number": list(range(1, 7)) * 6,
                "runs_batter": [1] * n,
                "runs_total": [1] * n,
                "is_legal_ball": [True] * n,
                "wicket": [False] * n,
            }
        )
        ppf = PhasePerformanceFeatures(min_deliveries=5)
        result = ppf.compute("p001", df, "T20I", "batter")
        assert result["sr_powerplay"] is not None
        assert result["sr_middle"] is None  # no middle-over deliveries
        assert result["sr_death"] is None
