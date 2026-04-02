"""Tests for sovereign/matching/homology.py (5 tests)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from sovereign.matching.homology import HomologyScorer
from sovereign.matching.models import FranchiseDNA

from tests.test_matching.conftest import (
    FEATURE_NAMES,
    make_archetypes_df,
    make_features_df,
    make_franchise_dna,
)


@pytest.fixture
def scorer() -> HomologyScorer:
    """Return a fresh HomologyScorer."""
    return HomologyScorer()


@pytest.fixture
def features_df() -> pl.DataFrame:
    """20-player synthetic feature DataFrame."""
    return make_features_df()


@pytest.fixture
def archetypes_df() -> pl.DataFrame:
    """20-player archetype mapping DataFrame."""
    return make_archetypes_df()


@pytest.fixture
def dna() -> FranchiseDNA:
    """FranchiseDNA targeting ARC_001."""
    return make_franchise_dna(seed=7)


class TestCosineSimilarityComputed:
    """Homology scores are cosine similarities in [0, 1]."""

    def test_homology_score_in_unit_interval(
        self,
        scorer: HomologyScorer,
        dna: FranchiseDNA,
        features_df: pl.DataFrame,
        archetypes_df: pl.DataFrame,
    ) -> None:
        """All homology scores must be in [0, 1]."""
        player_ids = features_df["player_id"].to_list()
        scores = scorer.compute_scores(dna, player_ids, features_df, archetypes_df)

        assert len(scores) > 0
        for s in scores:
            assert 0.0 <= s.homology_score <= 1.0


class TestArchetypeBonus:
    """Archetype bonus is +0.05 for matching archetypes."""

    def test_archetype_bonus_applied(
        self,
        scorer: HomologyScorer,
        dna: FranchiseDNA,
        features_df: pl.DataFrame,
        archetypes_df: pl.DataFrame,
    ) -> None:
        """Players in target archetypes receive a +0.05 bonus."""
        player_ids = features_df["player_id"].to_list()
        # dna targets ARC_001; players p000, p003, p006, ... are ARC_001
        arc001_players = archetypes_df.filter(
            pl.col("archetype_code") == "ARC_001"
        )["player_id"].to_list()
        other_players = archetypes_df.filter(
            pl.col("archetype_code") != "ARC_001"
        )["player_id"].to_list()

        scores = scorer.compute_scores(dna, player_ids, features_df, archetypes_df)
        score_map = {s.player_id: s for s in scores}

        for pid in arc001_players:
            if pid in score_map:
                assert score_map[pid].archetype_bonus == pytest.approx(0.05)
        for pid in other_players:
            if pid in score_map:
                assert score_map[pid].archetype_bonus == pytest.approx(0.0)

    def test_no_target_archetypes_gives_zero_bonus(
        self,
        scorer: HomologyScorer,
        features_df: pl.DataFrame,
        archetypes_df: pl.DataFrame,
    ) -> None:
        """When target_archetypes is empty, all bonuses should be 0.0."""
        dna_no_targets = FranchiseDNA(
            dna_id="no-targets",
            franchise_name="Test",
            dna_mode="slider",
            feature_vector={n: 1 / len(FEATURE_NAMES) for n in FEATURE_NAMES},
            target_archetypes=[],
        )
        player_ids = features_df["player_id"].to_list()
        scores = scorer.compute_scores(
            dna_no_targets,
            player_ids,
            features_df,
            archetypes_df,
            target_archetypes=[],
        )
        for s in scores:
            assert s.archetype_bonus == pytest.approx(0.0)


class TestConfidenceWeight:
    """Confidence weight is correctly read from the features_df."""

    def test_confidence_weight_applied(
        self,
        scorer: HomologyScorer,
        dna: FranchiseDNA,
        archetypes_df: pl.DataFrame,
    ) -> None:
        """confidence_weight column in features_df must be stored on the score."""
        # Give half the players confidence 0.5
        df = make_features_df()
        half = len(df) // 2
        weights = [0.5] * half + [1.0] * (len(df) - half)
        df = df.with_columns(pl.Series("confidence_weight", weights))

        player_ids = df["player_id"].to_list()
        scores = scorer.compute_scores(dna, player_ids, df, archetypes_df)
        score_map = {s.player_id: s for s in scores}

        for i, pid in enumerate(df["player_id"].to_list()):
            expected_cw = 0.5 if i < half else 1.0
            assert score_map[pid].confidence_weight == pytest.approx(expected_cw)


class TestSortedByScore:
    """Results should be sorted by final score descending."""

    def test_sorted_descending(
        self,
        scorer: HomologyScorer,
        dna: FranchiseDNA,
        features_df: pl.DataFrame,
        archetypes_df: pl.DataFrame,
    ) -> None:
        """Returned list must be ordered by final score (high → low)."""
        player_ids = features_df["player_id"].to_list()
        scores = scorer.compute_scores(dna, player_ids, features_df, archetypes_df)

        final_scores = [
            (s.homology_score + s.archetype_bonus) * s.confidence_weight
            for s in scores
        ]
        assert final_scores == sorted(final_scores, reverse=True)


class TestMissingArchetypes:
    """Players missing from archetypes_df get UNKNOWN archetype."""

    def test_handles_missing_archetypes(
        self,
        scorer: HomologyScorer,
        dna: FranchiseDNA,
        features_df: pl.DataFrame,
    ) -> None:
        """Players absent from archetypes_df should get archetype_code='UNKNOWN'."""
        empty_archetypes = pl.DataFrame(
            {
                "player_id": pl.Series([], dtype=pl.Utf8),
                "archetype_code": pl.Series([], dtype=pl.Utf8),
                "archetype_label": pl.Series([], dtype=pl.Utf8),
            }
        )
        player_ids = features_df["player_id"].to_list()
        scores = scorer.compute_scores(
            dna, player_ids, features_df, empty_archetypes
        )
        for s in scores:
            assert s.archetype_code == "UNKNOWN"
            assert s.archetype_bonus == pytest.approx(0.0)
