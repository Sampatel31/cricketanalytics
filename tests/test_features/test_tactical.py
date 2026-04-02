"""Tests for sovereign.features.tactical."""

from __future__ import annotations

import polars as pl
import pytest

from sovereign.features.tactical import TacticalFeatures


def _make_df(
    n: int = 60,
    runs: list[int] | None = None,
    over_numbers: list[int] | None = None,
    spi: list[float] | None = None,
) -> pl.DataFrame:
    if runs is None:
        runs = [1, 0, 4, 1, 0, 2] * (n // 6 + 1)
    if over_numbers is None:
        over_numbers = [(i // 6) + 1 for i in range(n)]
    if spi is None:
        spi = [float(i % 10) for i in range(n)]

    runs = runs[:n]
    over_numbers = over_numbers[:n]
    spi = spi[:n]

    return pl.DataFrame(
        {
            "batter_id": ["p001"] * n,
            "over_number": over_numbers,
            "runs_batter": runs,
            "is_legal_ball": [True] * n,
            "spi_total": spi,
            "is_boundary": [r >= 4 for r in runs],
            "is_home": [i % 2 == 0 for i in range(n)],
            "innings_number": [1] * n,
        }
    )


class TestClutchDelta:
    """clutch_delta = SR in death - SR in powerplay."""

    def test_positive_clutch_delta(self) -> None:
        # PP overs 1-6: score 1; Death overs 16-20: score 4
        n = 120
        runs = []
        overs = []
        for over in range(1, 21):
            for _ in range(6):
                overs.append(over)
                runs.append(4 if over > 15 else 1)
        df = _make_df(n=n, runs=runs, over_numbers=overs)
        tf = TacticalFeatures(min_balls=5)
        result = tf.compute("p001", df)
        assert result["clutch_delta"] is not None
        assert result["clutch_delta"] > 0

    def test_clutch_delta_within_range(self) -> None:
        df = _make_df(n=120)
        tf = TacticalFeatures()
        result = tf.compute("p001", df)
        if result["clutch_delta"] is not None:
            assert -200.0 <= result["clutch_delta"] <= 200.0


class TestRecoveryRate:
    """recovery_rate should be between 0 and 1."""

    def test_recovery_rate_bounds(self, basic_df: pl.DataFrame) -> None:
        tf = TacticalFeatures()
        result = tf.compute("p001", basic_df)
        if result["recovery_rate"] is not None:
            assert 0.0 <= result["recovery_rate"] <= 1.0

    def test_never_dots_gives_high_recovery(self) -> None:
        # No dots → no "after dot" events → returns 1.0 sentinel
        df = _make_df(n=30, runs=[2] * 30)
        tf = TacticalFeatures()
        result = tf.compute("p001", df)
        assert result["recovery_rate"] == pytest.approx(1.0)


class TestHomeAwayDelta:
    """home_away_delta computed when is_home column present."""

    def test_home_away_present(self) -> None:
        n = 60
        runs = [4 if i % 2 == 0 else 1 for i in range(n)]
        df = _make_df(n=n, runs=runs)
        tf = TacticalFeatures(min_balls=5)
        result = tf.compute("p001", df)
        assert result["home_away_delta"] is not None

    def test_home_away_within_range(self) -> None:
        df = _make_df(n=60)
        tf = TacticalFeatures()
        result = tf.compute("p001", df)
        if result["home_away_delta"] is not None:
            assert -100.0 <= result["home_away_delta"] <= 100.0


class TestMomentumScores:
    """momentum_riding_score and momentum_reset_score are in [0, 1]."""

    def test_riding_score_bounds(self, basic_df: pl.DataFrame) -> None:
        tf = TacticalFeatures()
        result = tf.compute("p001", basic_df)
        if result["momentum_riding_score"] is not None:
            assert 0.0 <= result["momentum_riding_score"] <= 1.0

    def test_reset_score_bounds(self, basic_df: pl.DataFrame) -> None:
        tf = TacticalFeatures()
        result = tf.compute("p001", basic_df)
        if result["momentum_reset_score"] is not None:
            assert 0.0 <= result["momentum_reset_score"] <= 1.0


class TestShortCareerGrace:
    """Handles very short careers (fewer than min_balls) gracefully."""

    def test_too_few_balls_returns_nulls(self) -> None:
        df = _make_df(n=5)
        tf = TacticalFeatures(min_balls=10)
        result = tf.compute("p001", df)
        for v in result.values():
            assert v is None

    def test_returns_all_expected_keys(self, basic_df: pl.DataFrame) -> None:
        tf = TacticalFeatures()
        result = tf.compute("p001", basic_df)
        expected_keys = {
            "clutch_delta", "recovery_rate", "running_score_avg",
            "partnership_acceleration", "cold_start_sr",
            "pace_vs_spin_delta", "home_away_delta", "innings_type_delta",
            "consistency_index", "momentum_riding_score",
            "momentum_reset_score", "aggression_escalation",
            "boundary_dependency", "dot_ball_anxiety", "big_match_index",
        }
        assert set(result.keys()) == expected_keys
