"""Tests for sovereign/matching/dna.py (4 tests)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from sovereign.matching.dna import FranchiseDNABuilder, _FEATURE_NAMES
from sovereign.matching.models import DNABuildError

from tests.test_matching.conftest import make_features_df


@pytest.fixture
def builder() -> FranchiseDNABuilder:
    """Return a fresh DNA builder."""
    return FranchiseDNABuilder()


@pytest.fixture
def features_df() -> pl.DataFrame:
    """20-player synthetic feature DataFrame."""
    return make_features_df()


class TestSliderMode:
    """Tests for FranchiseDNABuilder.build_slider."""

    def test_slider_builds_correctly(self, builder: FranchiseDNABuilder) -> None:
        """build_slider should return a normalized FranchiseDNA with mode='slider'."""
        weights = {name: float(i + 1) for i, name in enumerate(_FEATURE_NAMES)}
        dna = builder.build_slider(weights, franchise_name="Mumbai Indians")

        assert dna.dna_mode == "slider"
        assert dna.franchise_name == "Mumbai Indians"
        assert len(dna.feature_vector) == 54
        # Verify unit norm
        vec = np.array(list(dna.feature_vector.values()))
        assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-6

    def test_slider_zero_weight_raises(self, builder: FranchiseDNABuilder) -> None:
        """All-zero weights should raise DNABuildError (zero norm)."""
        with pytest.raises(DNABuildError, match="zero norm"):
            builder.build_slider({}, franchise_name="Test FC")

    def test_slider_partial_features_defaults_zero(
        self, builder: FranchiseDNABuilder
    ) -> None:
        """Features not in the weights dict default to 0."""
        weights = {_FEATURE_NAMES[0]: 1.0}
        dna = builder.build_slider(weights)
        # Only one non-zero entry
        vec = np.array(list(dna.feature_vector.values()))
        assert float(np.linalg.norm(vec)) == pytest.approx(1.0, abs=1e-6)


class TestExemplarMode:
    """Tests for FranchiseDNABuilder.build_exemplar."""

    def test_exemplar_averages_correctly(
        self, builder: FranchiseDNABuilder, features_df: pl.DataFrame
    ) -> None:
        """build_exemplar should average named player vectors and normalize."""
        player_ids = ["p000", "p001", "p002"]
        dna = builder.build_exemplar(
            player_ids, features_df, franchise_name="CSK"
        )

        assert dna.dna_mode == "exemplar"
        assert len(dna.feature_vector) == 54
        assert "Average DNA of" in dna.description

        # Verify unit norm
        vec = np.array(list(dna.feature_vector.values()))
        assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-6

    def test_exemplar_missing_player_raises(
        self, builder: FranchiseDNABuilder, features_df: pl.DataFrame
    ) -> None:
        """Requesting a player not in features_df should raise DNABuildError."""
        with pytest.raises(DNABuildError, match="not found in features_df"):
            builder.build_exemplar(
                ["p000", "nonexistent_player"], features_df
            )

    def test_exemplar_empty_ids_raises(
        self, builder: FranchiseDNABuilder, features_df: pl.DataFrame
    ) -> None:
        """Empty player_ids list should raise DNABuildError."""
        with pytest.raises(DNABuildError):
            builder.build_exemplar([], features_df)


class TestHistoricalMode:
    """Tests for FranchiseDNABuilder.build_historical."""

    def test_historical_reverses_engineered_dna(
        self, builder: FranchiseDNABuilder, features_df: pl.DataFrame
    ) -> None:
        """build_historical should produce a normalized unit vector in historical mode."""
        player_ids = [f"p{i:03d}" for i in range(5)]
        dna = builder.build_historical(
            player_ids, features_df, franchise_name="RCB"
        )

        assert dna.dna_mode == "historical"
        assert "Reverse-engineered" in dna.description
        assert "5 picks" in dna.description

        vec = np.array(list(dna.feature_vector.values()))
        assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-6


class TestNormalization:
    """Verify that all build modes produce properly normalized vectors."""

    def test_normalization_works_across_modes(
        self, builder: FranchiseDNABuilder, features_df: pl.DataFrame
    ) -> None:
        """Unit vector check for all three modes."""
        player_ids = ["p000", "p001"]

        # Slider
        weights = {n: 1.0 for n in _FEATURE_NAMES}
        dna_slider = builder.build_slider(weights)
        v_slider = np.array(list(dna_slider.feature_vector.values()))
        assert abs(float(np.linalg.norm(v_slider)) - 1.0) < 1e-6

        # Exemplar
        dna_ex = builder.build_exemplar(player_ids, features_df)
        v_ex = np.array(list(dna_ex.feature_vector.values()))
        assert abs(float(np.linalg.norm(v_ex)) - 1.0) < 1e-6

        # Historical
        dna_hist = builder.build_historical(player_ids, features_df)
        v_hist = np.array(list(dna_hist.feature_vector.values()))
        assert abs(float(np.linalg.norm(v_hist)) - 1.0) < 1e-6
