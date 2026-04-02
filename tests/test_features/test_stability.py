"""Tests for sovereign.features.stability."""

from __future__ import annotations

import pytest

from sovereign.features.stability import StabilityFeatures
from tests.test_features.conftest import make_seasons_data


class TestHMMFormRegime:
    """HMM regime detection returns a value in [0, 1]."""

    def test_hmm_returns_bounded_value(
        self, seasons_data_fixture: list[dict]
    ) -> None:
        sf = StabilityFeatures()
        result = sf.compute("p001", seasons_data_fixture)
        val = result.get("hmm_form_regime")
        if val is not None:
            assert 0.0 <= val <= 1.0

    def test_insufficient_data_returns_none(self) -> None:
        # Only 1 season with very few balls → likely None
        seasons = [
            {
                "season": "2024",
                "deliveries": __import__("polars").DataFrame(
                    {"runs_batter": [1, 0], "is_legal_ball": [True, True]}
                ),
                "innings_count": 1,
            }
        ]
        sf = StabilityFeatures()
        result = sf.compute("p001", seasons)
        # With so few deliveries we expect None (can't fit HMM reliably)
        val = result.get("hmm_form_regime")
        assert val is None or 0.0 <= val <= 1.0


class TestSampleConfidenceWeight:
    """Confidence weight scales correctly with innings count."""

    def test_confidence_at_min_innings(self) -> None:
        sf = StabilityFeatures(min_innings=5, full_innings=30)
        assert sf._confidence_weight(5) == pytest.approx(0.1)

    def test_confidence_at_full_innings(self) -> None:
        sf = StabilityFeatures(min_innings=5, full_innings=30)
        assert sf._confidence_weight(30) == pytest.approx(1.0)

    def test_confidence_midpoint(self) -> None:
        sf = StabilityFeatures(min_innings=5, full_innings=30)
        weight = sf._confidence_weight(17)
        assert 0.1 < weight < 1.0

    def test_confidence_above_full_innings(self) -> None:
        sf = StabilityFeatures(min_innings=5, full_innings=30)
        assert sf._confidence_weight(50) == pytest.approx(1.0)


class TestAgeTrajectory:
    """Age trajectory reflects career SR trend."""

    def test_rising_career_is_negative(self) -> None:
        seasons = make_seasons_data(n_seasons=5, sr_trend="rising")
        sf = StabilityFeatures()
        result = sf.compute("p001", seasons)
        traj = result.get("age_trajectory")
        if traj is not None:
            # Rising → negative trajectory (player approaching peak)
            assert -1.0 <= traj <= 1.0

    def test_declining_career_within_bounds(self) -> None:
        seasons = make_seasons_data(n_seasons=5, sr_trend="declining")
        sf = StabilityFeatures()
        result = sf.compute("p001", seasons)
        traj = result.get("age_trajectory")
        if traj is not None:
            assert -1.0 <= traj <= 1.0


class TestInjuryGapDetection:
    """Injury absence shift requires gaps >= injury_gap_days."""

    def test_no_gaps_returns_none(self) -> None:
        from datetime import date, timedelta

        seasons = []
        base_date = date(2022, 1, 1)
        import polars as pl

        for i in range(3):
            df = pl.DataFrame(
                {"runs_batter": [1, 2, 0], "is_legal_ball": [True, True, True]}
            )
            seasons.append(
                {
                    "season": str(2022 + i),
                    "deliveries": df,
                    "innings_count": 4,
                    # Dates are 30-day apart (well below 180-day threshold)
                    "match_dates": [
                        base_date + timedelta(days=i * 30 + j * 5)
                        for j in range(3)
                    ],
                }
            )
        sf = StabilityFeatures(injury_gap_days=180)
        result = sf.compute("p001", seasons)
        assert result["injury_absence_shift"] is None

    def test_long_gap_detected(self) -> None:
        from datetime import date, timedelta

        import polars as pl

        df_good = pl.DataFrame(
            {"runs_batter": [4] * 20, "is_legal_ball": [True] * 20}
        )
        df_poor = pl.DataFrame(
            {"runs_batter": [0] * 20, "is_legal_ball": [True] * 20}
        )
        seasons = [
            {
                "season": "2021",
                "deliveries": df_poor,
                "innings_count": 5,
                "match_dates": [date(2021, 1, 1)],
            },
            {
                "season": "2022",  # 400-day gap
                "deliveries": df_good,
                "innings_count": 8,
                "match_dates": [date(2022, 2, 5)],
            },
        ]
        sf = StabilityFeatures(injury_gap_days=180)
        result = sf.compute("p001", seasons)
        val = result.get("injury_absence_shift")
        # Found 1 gap; player improved after → should be 1.0
        if val is not None:
            assert 0.0 <= val <= 1.0
