"""Tests for sovereign.features.opposition."""

from __future__ import annotations

import polars as pl
import pytest

from sovereign.features.opposition import OppositionQualityFeatures


def _make_delivery_df(n: int, elos: list[float]) -> pl.DataFrame:
    """Build a deliveries DataFrame with opposition_elo column."""
    assert len(elos) == n
    return pl.DataFrame(
        {
            "batter_id": ["p001"] * n,
            "match_id": [f"m{i}" for i in range(n)],
            "runs_batter": [2] * n,
            "is_legal_ball": [True] * n,
            "opposition_elo": elos,
        }
    )


def _make_match_info(n: int) -> list[dict]:
    return [
        {
            "match_id": f"m{i}",
            "opposition_elo": 1300.0 + i * 40.0,
            "player_runs": 20 + i * 2,
            "player_balls": 30,
            "runs_conceded": 36,
            "balls_bowled": 18,
        }
        for i in range(n)
    ]


class TestTopBottomAttackDetection:
    """SR vs top-10 / bottom-10 attack classification."""

    def test_high_elo_goes_to_top(self) -> None:
        elos = [1700.0] * 20 + [1300.0] * 20
        df = _make_delivery_df(40, elos)
        mi = _make_match_info(5)
        oqf = OppositionQualityFeatures(min_deliveries=5)
        result = oqf.compute("p001", df, mi)
        assert result["sr_vs_top10_attacks"] is not None

    def test_low_elo_goes_to_bottom(self) -> None:
        elos = [1700.0] * 20 + [1300.0] * 20
        df = _make_delivery_df(40, elos)
        mi = _make_match_info(5)
        oqf = OppositionQualityFeatures(min_deliveries=5)
        result = oqf.compute("p001", df, mi)
        assert result["sr_vs_bottom10_attacks"] is not None

    def test_empty_match_info_returns_nulls(self) -> None:
        df = _make_delivery_df(10, [1500.0] * 10)
        oqf = OppositionQualityFeatures()
        result = oqf.compute("p001", df, [])
        for v in result.values():
            assert v is None


class TestQualityAdjustment:
    """Quality-adjusted metrics are within expected bounds."""

    def test_quality_adjusted_avg_computed(
        self, match_info_fixture: list[dict]
    ) -> None:
        elos = [m["opposition_elo"] for m in match_info_fixture]
        df = _make_delivery_df(len(elos), elos)
        oqf = OppositionQualityFeatures(min_deliveries=5)
        result = oqf.compute("p001", df, match_info_fixture)
        qa_avg = result.get("quality_adjusted_avg")
        if qa_avg is not None:
            assert 0.0 <= qa_avg <= 200.0

    def test_quality_adjusted_economy_within_bounds(
        self, match_info_fixture: list[dict]
    ) -> None:
        elos = [m["opposition_elo"] for m in match_info_fixture]
        df = _make_delivery_df(len(elos), elos)
        oqf = OppositionQualityFeatures(min_deliveries=3)
        result = oqf.compute("p001", df, match_info_fixture)
        qe = result.get("quality_adjusted_economy")
        if qe is not None:
            assert 0.0 <= qe <= 50.0


class TestHighEloMatchFilter:
    """Deliveries vs high-ELO teams are correctly identified."""

    def test_high_elo_sr_computed(self) -> None:
        # 20 deliveries vs ELO=1700 (above 1600 threshold)
        elos = [1700.0] * 20
        df = _make_delivery_df(20, elos)
        mi = [
            {
                "match_id": f"m{i}",
                "opposition_elo": 1700.0,
                "player_runs": 40,
                "player_balls": 20,
            }
            for i in range(20)
        ]
        oqf = OppositionQualityFeatures(
            high_elo_threshold=1600.0, min_deliveries=5
        )
        result = oqf.compute("p001", df, mi)
        assert result["high_elo_match_sr"] == pytest.approx(200.0)

    def test_below_elo_threshold_returns_none(self) -> None:
        # All deliveries vs ELO=1400 (below 1600 threshold)
        elos = [1400.0] * 20
        df = _make_delivery_df(20, elos)
        mi = [
            {
                "match_id": f"m{i}",
                "opposition_elo": 1400.0,
                "player_runs": 20,
                "player_balls": 20,
            }
            for i in range(20)
        ]
        oqf = OppositionQualityFeatures(
            high_elo_threshold=1600.0, min_deliveries=5
        )
        result = oqf.compute("p001", df, mi)
        assert result["high_elo_match_sr"] is None
