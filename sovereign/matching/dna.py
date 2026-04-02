"""Franchise DNA builder — three construction modes.

Provides the ``FranchiseDNABuilder`` class which creates a
``FranchiseDNA`` instance from slider weights, exemplar player IDs,
or historical pick lists.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
import polars as pl

from sovereign.features.models import FeatureVector
from sovereign.matching.models import DNABuildError, FranchiseDNA
from sovereign.matching.utils import normalize_vector

# Canonical list of 54 feature names in fixed order
_FEATURE_NAMES: list[str] = list(FeatureVector.model_fields.keys())
_N_FEATURES: int = len(_FEATURE_NAMES)  # 54


class FranchiseDNABuilder:
    """Build franchise DNA vectors in three modes.

    All three build methods validate the resulting vector for:
    - Exactly 54 dimensions
    - No NaN values
    - Unit norm (L2 ≈ 1.0) after normalization
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def build_slider(
        self,
        feature_weights: dict[str, float],
        franchise_name: str = "",
        target_archetypes: list[str] | None = None,
    ) -> FranchiseDNA:
        """Build DNA from manual slider weights (0–100 per feature).

        Any feature not supplied in *feature_weights* defaults to 0.
        The resulting vector is L2-normalised before storage.

        Args:
            feature_weights: Dict mapping feature name → weight in [0, 100].
            franchise_name: Optional franchise label.
            target_archetypes: Optional preferred archetype codes.

        Returns:
            ``FranchiseDNA`` with ``dna_mode="slider"``.

        Raises:
            DNABuildError: If the weight vector has zero norm or contains
                invalid values.
        """
        raw = np.zeros(_N_FEATURES, dtype=float)
        for i, name in enumerate(_FEATURE_NAMES):
            raw[i] = float(feature_weights.get(name, 0.0))

        self._validate_raw_vector(raw, mode="slider")
        normalized = normalize_vector(raw)
        self._validate_unit_vector(normalized, mode="slider")

        return FranchiseDNA(
            dna_id=str(uuid.uuid4()),
            franchise_name=franchise_name,
            dna_mode="slider",
            feature_vector=dict(zip(_FEATURE_NAMES, normalized.tolist())),
            target_archetypes=target_archetypes or [],
            created_at=datetime.now(timezone.utc),
            description=(
                f"Slider-based DNA for {franchise_name or 'unknown franchise'} "
                f"with {sum(1 for v in feature_weights.values() if v > 0)} "
                f"active features."
            ),
        )

    def build_exemplar(
        self,
        player_ids: list[str],
        features_df: pl.DataFrame,
        franchise_name: str = "",
        target_archetypes: list[str] | None = None,
    ) -> FranchiseDNA:
        """Build DNA by averaging feature vectors of named players.

        Args:
            player_ids: List of exemplar player identifiers.
            features_df: DataFrame with ``player_id`` column and 54 feature
                columns (must include all ``_FEATURE_NAMES``).
            franchise_name: Optional franchise label.
            target_archetypes: Optional preferred archetype codes.

        Returns:
            ``FranchiseDNA`` with ``dna_mode="exemplar"``.

        Raises:
            DNABuildError: If any player is not found or the averaged vector
                is invalid.
        """
        if not player_ids:
            raise DNABuildError("player_ids must not be empty for exemplar mode")

        vectors = self._extract_player_vectors(player_ids, features_df, mode="exemplar")
        avg = vectors.mean(axis=0)

        self._validate_raw_vector(avg, mode="exemplar")
        normalized = normalize_vector(avg)
        self._validate_unit_vector(normalized, mode="exemplar")

        # Build description with player names if available
        name_col = "player_name" if "player_name" in features_df.columns else None
        if name_col:
            name_map = dict(
                zip(
                    features_df["player_id"].to_list(),
                    features_df[name_col].to_list(),
                )
            )
            names_str = ", ".join(
                name_map.get(pid, pid) for pid in player_ids
            )
        else:
            names_str = ", ".join(player_ids)

        return FranchiseDNA(
            dna_id=str(uuid.uuid4()),
            franchise_name=franchise_name,
            dna_mode="exemplar",
            feature_vector=dict(zip(_FEATURE_NAMES, normalized.tolist())),
            target_archetypes=target_archetypes or [],
            created_at=datetime.now(timezone.utc),
            description=f"Average DNA of: {names_str}",
        )

    def build_historical(
        self,
        player_ids: list[str],
        features_df: pl.DataFrame,
        franchise_name: str = "",
        target_archetypes: list[str] | None = None,
    ) -> FranchiseDNA:
        """Reverse-engineer DNA from a franchise's historical picks.

        Computes the average feature vector across all historical picks
        to reveal what behavioral archetype the franchise has implicitly
        been targeting.

        Args:
            player_ids: List of player IDs from historical picks.
            features_df: DataFrame with ``player_id`` and 54 feature columns.
            franchise_name: Optional franchise label.
            target_archetypes: Optional preferred archetype codes.

        Returns:
            ``FranchiseDNA`` with ``dna_mode="historical"``.

        Raises:
            DNABuildError: If no players are found or the vector is invalid.
        """
        if not player_ids:
            raise DNABuildError(
                "player_ids must not be empty for historical mode"
            )

        vectors = self._extract_player_vectors(
            player_ids, features_df, mode="historical"
        )
        avg = vectors.mean(axis=0)

        self._validate_raw_vector(avg, mode="historical")
        normalized = normalize_vector(avg)
        self._validate_unit_vector(normalized, mode="historical")

        n_picks = len(player_ids)
        return FranchiseDNA(
            dna_id=str(uuid.uuid4()),
            franchise_name=franchise_name,
            dna_mode="historical",
            feature_vector=dict(zip(_FEATURE_NAMES, normalized.tolist())),
            target_archetypes=target_archetypes or [],
            created_at=datetime.now(timezone.utc),
            description=(
                f"Reverse-engineered from your last {n_picks} picks"
            ),
        )

    # ------------------------------------------------------------------ #
    # Private helpers                                                       #
    # ------------------------------------------------------------------ #

    def _extract_player_vectors(
        self,
        player_ids: list[str],
        features_df: pl.DataFrame,
        mode: str,
    ) -> np.ndarray:
        """Extract feature matrix for the given player IDs.

        Args:
            player_ids: Players to look up.
            features_df: Source DataFrame (must have ``player_id`` column).
            mode: Build mode for error messages.

        Returns:
            2-D array of shape ``(n_players, 54)``.

        Raises:
            DNABuildError: If any player is missing from the DataFrame.
        """
        available = set(features_df["player_id"].to_list())
        missing = [pid for pid in player_ids if pid not in available]
        if missing:
            raise DNABuildError(
                f"[{mode}] Players not found in features_df: {missing}"
            )

        subset = features_df.filter(
            pl.col("player_id").is_in(player_ids)
        )

        # Keep only the 54 canonical feature columns
        missing_cols = [c for c in _FEATURE_NAMES if c not in subset.columns]
        if missing_cols:
            raise DNABuildError(
                f"[{mode}] features_df is missing columns: {missing_cols[:5]}…"
            )

        matrix = subset.select(_FEATURE_NAMES).to_numpy().astype(float)

        if matrix.shape[1] != _N_FEATURES:
            raise DNABuildError(
                f"[{mode}] Expected {_N_FEATURES} features, "
                f"got {matrix.shape[1]}"
            )
        return matrix

    @staticmethod
    def _validate_raw_vector(vec: np.ndarray, mode: str) -> None:
        """Ensure the raw vector has no NaNs and is not all zeros.

        Args:
            vec: 1-D array of length 54.
            mode: Build mode label for error messages.

        Raises:
            DNABuildError: On invalid vector.
        """
        if vec.shape[0] != _N_FEATURES:
            raise DNABuildError(
                f"[{mode}] Vector must have {_N_FEATURES} dimensions, "
                f"got {vec.shape[0]}"
            )
        if np.any(np.isnan(vec)):
            raise DNABuildError(f"[{mode}] Vector contains NaN values")
        if float(np.linalg.norm(vec)) < 1e-8:
            raise DNABuildError(
                f"[{mode}] Vector has zero norm — cannot normalize"
            )

    @staticmethod
    def _validate_unit_vector(vec: np.ndarray, mode: str) -> None:
        """Verify the vector is a unit vector (L2 norm ≈ 1.0).

        Args:
            vec: Normalized 1-D array.
            mode: Build mode label for error messages.

        Raises:
            DNABuildError: If the norm deviates from 1.0 by more than 1e-6.
        """
        norm = float(np.linalg.norm(vec))
        if abs(norm - 1.0) > 1e-6:
            raise DNABuildError(
                f"[{mode}] Normalized vector norm is {norm:.8f}, expected 1.0"
            )
