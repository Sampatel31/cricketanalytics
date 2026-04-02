"""Shared fixtures for feature engineering tests."""

from __future__ import annotations

from typing import Optional

import polars as pl
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_delivery_df(
    n: int = 60,
    spi_values: Optional[list[float]] = None,
    runs_values: Optional[list[int]] = None,
    over_numbers: Optional[list[int]] = None,
) -> pl.DataFrame:
    """Build a synthetic delivery-level Polars DataFrame."""
    import random

    if spi_values is None:
        spi_values = [float(i % 10) for i in range(n)]
    if runs_values is None:
        runs_values = [random.choice([0, 1, 2, 4, 6]) for _ in range(n)]
    if over_numbers is None:
        over_numbers = [(i // 6) + 1 for i in range(n)]

    is_boundary = [r >= 4 for r in runs_values]
    return pl.DataFrame(
        {
            "batter_id": ["p001"] * n,
            "match_id": [f"m{i // 30}" for i in range(n)],
            "innings_number": [1] * n,
            "over_number": over_numbers[:n],
            "ball_in_innings": list(range(1, n + 1)),
            "runs_batter": runs_values[:n],
            "runs_total": runs_values[:n],
            "is_legal_ball": [True] * n,
            "wicket": [False] * n,
            "spi_total": spi_values[:n],
            "is_boundary": is_boundary[:n],
            "is_home": [i % 2 == 0 for i in range(n)],
            "target": [None] * n,
        }
    )


def make_seasons_data(
    n_seasons: int = 3,
    innings_per_season: int = 12,
    sr_trend: str = "flat",  # "flat" | "rising" | "declining"
) -> list[dict]:
    """Generate synthetic seasons_data for stability tests."""
    seasons = []
    for i in range(n_seasons):
        if sr_trend == "rising":
            runs_factor = 1 + i * 0.3
        elif sr_trend == "declining":
            runs_factor = max(0.5, 1 - i * 0.2)
        else:
            runs_factor = 1.0

        deliveries = [int(min(6, max(0, round(r * runs_factor)))) for r in
                      [0, 1, 4, 1, 0, 2] * 20]
        df = pl.DataFrame(
            {
                "runs_batter": deliveries,
                "is_legal_ball": [True] * len(deliveries),
            }
        )
        seasons.append(
            {
                "season": str(2020 + i),
                "deliveries": df,
                "innings_count": innings_per_season,
                "archetype": "aggressive" if i < n_seasons // 2 + 1 else "anchor",
                "format": "T20I",
                "tournament_stage": "final" if i == n_seasons - 1 else "group",
            }
        )
    return seasons


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_df() -> pl.DataFrame:
    """60-ball delivery DataFrame with realistic data."""
    return make_delivery_df(n=60)


@pytest.fixture
def spi_tier_df() -> pl.DataFrame:
    """DataFrame with exactly 15 deliveries per SPI tier."""
    # 60 deliveries: 15 in each of [0-3), [3-6), [6-8), [8-10]
    spi = (
        [1.0] * 15   # low
        + [4.5] * 15  # medium
        + [7.0] * 15  # high
        + [9.0] * 15  # extreme
    )
    runs = [1, 0, 4, 1, 0, 0, 2, 1, 0, 6, 4, 0, 1, 0, 2] * 4
    return pl.DataFrame(
        {
            "batter_id": ["p001"] * 60,
            "runs_batter": runs,
            "is_legal_ball": [True] * 60,
            "spi_total": spi,
            "is_boundary": [r >= 4 for r in runs],
        }
    )


@pytest.fixture
def phase_df() -> pl.DataFrame:
    """DataFrame covering all three phases in T20 format (20 overs)."""
    over_numbers = []
    runs = []
    for over in range(1, 21):
        for ball in range(6):
            over_numbers.append(over)
            runs.append(1 if over <= 6 else (2 if over <= 15 else 4))
    n = len(over_numbers)
    return pl.DataFrame(
        {
            "batter_id": ["p001"] * n,
            "match_id": ["m001"] * n,
            "over_number": over_numbers,
            "runs_batter": runs,
            "runs_total": runs,
            "is_legal_ball": [True] * n,
            "wicket": [False] * n,
        }
    )


@pytest.fixture
def seasons_data_fixture() -> list[dict]:
    """Three seasons of synthetic data."""
    return make_seasons_data(n_seasons=3, innings_per_season=12)


@pytest.fixture
def match_info_fixture() -> list[dict]:
    """10 matches with varying opposition ELO."""
    return [
        {
            "match_id": f"m{i:03d}",
            "opposition_elo": 1300.0 + i * 50.0,  # 1300 to 1750
            "player_runs": 20 + i * 3,
            "player_balls": 25,
            "runs_conceded": 30,
            "balls_bowled": 18,
        }
        for i in range(10)
    ]
