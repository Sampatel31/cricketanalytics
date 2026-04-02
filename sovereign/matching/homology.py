"""Homology scorer — cosine similarity between players and franchise DNA.

Scores every player in a feature DataFrame against a ``FranchiseDNA``
vector and returns a ranked list of ``PlayerScore`` objects.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import polars as pl

from sovereign.features.models import FeatureVector
from sovereign.matching.models import FranchiseDNA, PlayerScore
from sovereign.matching.utils import cosine_similarity, get_recommendation

_FEATURE_NAMES: list[str] = list(FeatureVector.model_fields.keys())
_N_FEATURES: int = len(_FEATURE_NAMES)


class HomologyScorer:
    """Score players against a franchise DNA vector.

    For each player the scorer computes:

    1. ``homology_score`` = cosine similarity of the player's 54-D feature
       vector with the franchise DNA vector (clamped to [0, 1]).
    2. ``archetype_bonus`` = +0.05 if the player's archetype code is in
       ``target_archetypes``, else 0.0.
    3. ``confidence_weight`` from the ``confidence_weight`` column of
       *features_df* (falls back to 1.0 if the column is absent).
    4. Final score = (homology_score + archetype_bonus) × confidence_weight.

    Players are sorted by final score descending.
    """

    def compute_scores(
        self,
        dna: FranchiseDNA,
        player_ids: list[str],
        features_df: pl.DataFrame,
        archetypes_df: pl.DataFrame,
        target_archetypes: Optional[list[str]] = None,
    ) -> list[PlayerScore]:
        """Score a set of players against the provided franchise DNA.

        Args:
            dna: Franchise DNA built by ``FranchiseDNABuilder``.
            player_ids: Subset of player IDs to score.  Players missing
                from *features_df* are silently skipped.
            features_df: DataFrame with ``player_id`` and 54 feature
                columns.  Optional columns: ``player_name``,
                ``confidence_weight``.
            archetypes_df: DataFrame with ``player_id``,
                ``archetype_code``, and ``archetype_label`` columns.
            target_archetypes: Archetype codes that earn a +0.05 bonus.
                Falls back to ``dna.target_archetypes`` if ``None``.

        Returns:
            List of ``PlayerScore`` objects sorted by
            ``(homology_score + archetype_bonus) × confidence_weight``
            descending.
        """
        effective_targets: list[str] = (
            target_archetypes
            if target_archetypes is not None
            else dna.target_archetypes
        )

        # Build DNA array
        dna_vec = np.array(
            [dna.feature_vector.get(name, 0.0) for name in _FEATURE_NAMES],
            dtype=float,
        )

        # Index look-ups
        feat_ids = set(features_df["player_id"].to_list())
        arc_ids = set(archetypes_df["player_id"].to_list())

        # Pre-build archetype lookup: player_id → (code, label)
        arc_lookup: dict[str, tuple[str, str]] = {}
        for row in archetypes_df.iter_rows(named=True):
            arc_lookup[row["player_id"]] = (
                row.get("archetype_code", "UNKNOWN"),
                row.get("archetype_label", "Unknown"),
            )

        # Pre-build player name lookup
        name_lookup: dict[str, str] = {}
        if "player_name" in features_df.columns:
            for row in features_df.iter_rows(named=True):
                name_lookup[row["player_id"]] = row.get("player_name", row["player_id"])

        # Confidence weight lookup
        conf_lookup: dict[str, float] = {}
        if "confidence_weight" in features_df.columns:
            for row in features_df.iter_rows(named=True):
                conf_lookup[row["player_id"]] = float(
                    row.get("confidence_weight", 1.0)
                )

        scores: list[PlayerScore] = []

        for pid in player_ids:
            if pid not in feat_ids:
                continue  # silently skip missing players

            # Extract feature vector for this player
            player_row = features_df.filter(pl.col("player_id") == pid)
            missing_cols = [c for c in _FEATURE_NAMES if c not in player_row.columns]
            if missing_cols:
                continue

            player_vec = (
                player_row.select(_FEATURE_NAMES).to_numpy()[0].astype(float)
            )

            if np.any(np.isnan(player_vec)):
                player_vec = np.nan_to_num(player_vec, nan=0.0)

            homology = cosine_similarity(player_vec, dna_vec)

            archetype_code, archetype_label = arc_lookup.get(
                pid, ("UNKNOWN", "Unknown")
            )

            archetype_bonus = (
                0.05 if archetype_code in effective_targets else 0.0
            )
            confidence_weight = conf_lookup.get(pid, 1.0)

            # Fair value and market_price placeholders — valuation is done
            # separately by ValuationModel; here we leave them at 0 and let
            # the caller enrich them.
            scores.append(
                PlayerScore(
                    player_id=pid,
                    player_name=name_lookup.get(pid, pid),
                    archetype_code=archetype_code,
                    archetype_label=archetype_label,
                    homology_score=homology,
                    archetype_bonus=archetype_bonus,
                    confidence_weight=confidence_weight,
                    fair_value=0.0,
                    market_price=0.0,
                    arbitrage_gap=0.0,
                    arbitrage_pct=0.0,
                    recommendation="NEUTRAL",
                )
            )

        # Sort by (homology + bonus) × confidence descending
        scores.sort(
            key=lambda s: (s.homology_score + s.archetype_bonus)
            * s.confidence_weight,
            reverse=True,
        )
        return scores
