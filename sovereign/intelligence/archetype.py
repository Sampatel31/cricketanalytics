"""Archetype discovery — auto-naming and registry creation."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import polars as pl

from sovereign.intelligence.models import Archetype
from sovereign.intelligence.utils import feature_extremes, feature_to_description

logger = logging.getLogger(__name__)

# Pre-defined archetype name pool (fallback for when auto-naming is ambiguous)
_ARCHETYPE_NAME_POOL = [
    "Pressure Accumulator",
    "Early Dominator",
    "Invisible Anchor",
    "Chaos Agent",
    "Format Shapeshifter",
    "Cold Blooded Finisher",
    "Surgical Economist",
    "Pressure Breaker",
    "Powerplay Predator",
    "Death Overs Specialist",
    "Middle Overs Maestro",
    "All-Round Disruptor",
]

# Feature → archetype name heuristics (ordered priority rules)
_NAMING_RULES: list[tuple[str, float, str]] = [
    # (feature_name, threshold, name_if_above)
    ("clutch_delta", 20.0, "Cold Blooded Finisher"),
    ("clutch_delta", -20.0, "Early Dominator"),  # Note: checked as below threshold
    ("sr_spi_extreme", 150.0, "Pressure Accumulator"),
    ("dot_pct_spi_extreme", 50.0, "Invisible Anchor"),
    ("big_match_index", 0.7, "Pressure Breaker"),
    ("aggression_escalation", 0.7, "Chaos Agent"),
    ("consistency_index", 0.8, "Surgical Economist"),
    ("cold_start_sr", 150.0, "Early Dominator"),
    ("sr_spi_low", 150.0, "Format Shapeshifter"),
]


class ArchetypeDiscoverer:
    """Discover, name, and describe behavioural archetypes from cluster data.

    Args:
        feature_names: Ordered list of 54 feature names. Defaults to the
            canonical order from ``FeatureVector``.
    """

    def __init__(self, feature_names: Optional[list[str]] = None) -> None:
        if feature_names is None:
            from sovereign.features.models import FeatureVector
            feature_names = list(FeatureVector.model_fields.keys())
        self._feature_names = feature_names

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(
        self,
        coords_10d: np.ndarray,
        features_df: pl.DataFrame,
        cluster_labels: np.ndarray,
        centroids: np.ndarray,
        stability_ari: float = 0.0,
    ) -> list[Archetype]:
        """Create an :class:`Archetype` record for each cluster.

        Args:
            coords_10d: Reduced coordinates (n_players × 10).
            features_df: Original 54D feature DataFrame.
            cluster_labels: Cluster label per player.
            centroids: Centroid coordinates (n_clusters × 10).
            stability_ari: Bootstrap ARI to store on each archetype.

        Returns:
            List of :class:`Archetype` instances, one per cluster.
        """
        unique_clusters = sorted(set(cluster_labels))
        feature_cols = self._get_feature_columns(features_df)
        feat_np = features_df.select(feature_cols).to_numpy().astype(np.float64)

        archetypes: list[Archetype] = []
        used_names: set[str] = set()

        for idx, cluster_id in enumerate(unique_clusters):
            mask = cluster_labels == cluster_id
            cluster_feat = feat_np[mask]
            centroid_54d = cluster_feat.mean(axis=0)
            centroid_dict = dict(zip(self._feature_names[:len(centroid_54d)], centroid_54d.tolist()))

            code = f"ARC_{idx + 1:03d}"
            label = self._auto_name(centroid_dict, used_names)
            used_names.add(label)
            description = self._generate_description(code, centroid_dict)

            archetypes.append(
                Archetype(
                    code=code,
                    label=label,
                    description=description,
                    centroid_features=centroid_dict,
                    cluster_size=int(mask.sum()),
                    stability_ari=max(0.0, min(1.0, stability_ari)),
                )
            )
            logger.info(
                "Archetype %s: %s (%d players)", code, label, int(mask.sum())
            )

        return archetypes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auto_name(
        self, feature_dict: dict[str, float], used_names: set[str]
    ) -> str:
        """Auto-name an archetype from its centroid feature profile.

        Checks heuristic naming rules first, then falls back to the
        pre-defined name pool.

        Args:
            feature_dict: Centroid feature values.
            used_names: Already-assigned names (to avoid duplicates).

        Returns:
            Human-readable archetype label.
        """
        for feat, threshold, name in _NAMING_RULES:
            if feat not in feature_dict:
                continue
            val = feature_dict[feat]
            # For rules where threshold is negative, check val < threshold
            if threshold < 0:
                if val < threshold and name not in used_names:
                    return name
            else:
                if val >= threshold and name not in used_names:
                    return name

        # Fallback: use feature extremes to create a descriptive name
        extremes = feature_extremes(feature_dict, top_k=2)
        if extremes:
            primary_desc = feature_to_description(extremes[0][0], extremes[0][1])
            # Capitalise and trim to reasonable length
            candidate = primary_desc.title()
            if candidate not in used_names:
                return candidate

        # Final fallback: use pool
        for name in _ARCHETYPE_NAME_POOL:
            if name not in used_names:
                return name

        # If all pool names used, generate numbered variant
        return f"Archetype_{len(used_names) + 1}"

    def _generate_description(
        self, archetype_code: str, feature_dict: dict[str, float]
    ) -> str:
        """Generate a narrative description for an archetype.

        Args:
            archetype_code: The archetype code (e.g. ``'ARC_001'``).
            feature_dict: Centroid feature values.

        Returns:
            Multi-sentence behavioural description.
        """
        extremes = feature_extremes(feature_dict, top_k=3)
        parts: list[str] = []
        for feat, val in extremes:
            desc = feature_to_description(feat, val)
            parts.append(desc)

        body = "; ".join(parts) if parts else "balanced across all dimensions"
        return (
            f"Players in {archetype_code} are characterised by: {body}. "
            f"This archetype contains players who show distinctive patterns "
            f"across {len(feature_dict)} behavioural dimensions."
        )

    def _get_feature_columns(self, features_df: pl.DataFrame) -> list[str]:
        """Return feature column names present in *features_df*."""
        _META = {"player_id", "format_type", "season", "confidence_weight", "innings_count"}
        return [c for c in features_df.columns if c not in _META]
