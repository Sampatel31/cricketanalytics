"""Tests for sovereign.features.builder."""

from __future__ import annotations

import polars as pl
import pytest

from sovereign.features.builder import FeatureBuilder
from sovereign.features.models import FeatureVector


def _make_multi_player_df(n_players: int = 3, balls_per_player: int = 60) -> pl.DataFrame:
    """Build a deliveries DataFrame for multiple players."""
    rows = []
    for p_idx in range(n_players):
        pid = f"player_{p_idx:03d}"
        for d_idx in range(balls_per_player):
            over_no = d_idx // 6 + 1
            runs = [1, 0, 4, 1, 0, 2][d_idx % 6]
            rows.append(
                {
                    "batter_id": pid,
                    "match_id": f"m_{p_idx:03d}_{d_idx // 30:02d}",
                    "innings_number": 1,
                    "over_number": over_no,
                    "ball_in_innings": d_idx + 1,
                    "runs_batter": runs,
                    "runs_total": runs,
                    "is_legal_ball": True,
                    "wicket": False,
                    "spi_total": float((d_idx + p_idx) % 10),
                    "is_boundary": runs >= 4,
                    "is_home": d_idx % 2 == 0,
                    "target": None,
                    "opposition_elo": 1300.0 + (p_idx * 100.0),
                }
            )
    return pl.DataFrame(rows)


class TestOutputShape:
    """Output DataFrame has correct shape."""

    def test_correct_row_count(self) -> None:
        n_players = 3
        df = _make_multi_player_df(n_players=n_players)
        builder = FeatureBuilder(n_workers=1, batch_size=10)
        result = builder.build_all(
            player_ids=[f"player_{i:03d}" for i in range(n_players)],
            deliveries_df=df,
            format_type="T20I",
            season="2024",
        )
        assert len(result) == n_players

    def test_correct_column_count(self) -> None:
        n_players = 2
        df = _make_multi_player_df(n_players=n_players)
        builder = FeatureBuilder(n_workers=1, batch_size=10)
        result = builder.build_all(
            player_ids=[f"player_{i:03d}" for i in range(n_players)],
            deliveries_df=df,
            format_type="T20I",
            season="2024",
        )
        # 5 metadata cols + 54 feature cols = 59
        assert len(result.columns) == 59


class TestNoNullsInOutput:
    """No NaN or null values should remain after imputation."""

    def test_no_nulls(self) -> None:
        df = _make_multi_player_df(n_players=3)
        builder = FeatureBuilder(n_workers=1)
        result = builder.build_all(
            player_ids=[f"player_{i:03d}" for i in range(3)],
            deliveries_df=df,
            format_type="T20I",
            season="2024",
        )
        feat_cols = [c for c in list(FeatureVector.model_fields.keys()) if c in result.columns]
        for col in feat_cols:
            null_count = result[col].null_count()
            assert null_count == 0, f"Column '{col}' has {null_count} nulls"


class TestConfidenceWeight:
    """Confidence weight is in [0, 1] for all players."""

    def test_confidence_weight_bounds(self) -> None:
        df = _make_multi_player_df(n_players=3)
        builder = FeatureBuilder(n_workers=1)
        result = builder.build_all(
            player_ids=[f"player_{i:03d}" for i in range(3)],
            deliveries_df=df,
            format_type="T20I",
            season="2024",
        )
        cw = result["confidence_weight"]
        assert cw.min() >= 0.0
        assert cw.max() <= 1.0


class TestFeaturesWithinRange:
    """Spot-check that feature values stay within their documented bounds."""

    def test_sr_fields_within_400(self) -> None:
        df = _make_multi_player_df(n_players=2)
        builder = FeatureBuilder(n_workers=1)
        result = builder.build_all(
            player_ids=[f"player_{i:03d}" for i in range(2)],
            deliveries_df=df,
        )
        for col in ("sr_spi_low", "sr_spi_medium", "sr_powerplay"):
            if col in result.columns:
                assert result[col].max() <= 400.0
                assert result[col].min() >= 0.0

    def test_pct_fields_within_100(self) -> None:
        df = _make_multi_player_df(n_players=2)
        builder = FeatureBuilder(n_workers=1)
        result = builder.build_all(
            player_ids=[f"player_{i:03d}" for i in range(2)],
            deliveries_df=df,
        )
        for col in ("dot_pct_spi_low", "boundary_pct_spi_low"):
            if col in result.columns:
                assert result[col].max() <= 100.0
                assert result[col].min() >= 0.0


class TestParquetSaveLoad:
    """Feature matrix can be saved and reloaded from Parquet."""

    def test_save_and_reload(self, tmp_path: str) -> None:
        df = _make_multi_player_df(n_players=2)
        builder = FeatureBuilder(n_workers=1)
        result = builder.build_all(
            player_ids=[f"player_{i:03d}" for i in range(2)],
            deliveries_df=df,
            format_type="T20I",
            season="2024",
            output_dir=str(tmp_path),
        )
        import pathlib

        parquet_files = list(pathlib.Path(tmp_path).glob("*.parquet"))
        assert len(parquet_files) == 1

        reloaded = pl.read_parquet(str(parquet_files[0]))
        assert reloaded.shape == result.shape


class TestBuildPlayer:
    """build_player returns a valid PlayerFeatures object."""

    def test_build_player_returns_player_features(self) -> None:
        from sovereign.features.models import PlayerFeatures

        df = _make_multi_player_df(n_players=1, balls_per_player=60)
        player_df = df.filter(pl.col("batter_id") == "player_000")
        builder = FeatureBuilder(n_workers=1)
        pf = builder.build_player(
            player_id="player_000",
            deliveries_df=player_df,
            format_type="T20I",
        )
        assert isinstance(pf, PlayerFeatures)
        assert pf.player_id == "player_000"
        assert 0.0 <= pf.confidence_weight <= 1.0
