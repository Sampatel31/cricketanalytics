"""Shared utility functions for the intelligence layer."""

from __future__ import annotations

import numpy as np


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        vec1: First vector.
        vec2: Second vector.

    Returns:
        Cosine similarity in [-1, 1].  Returns 0.0 for zero vectors.
    """
    norm1 = float(np.linalg.norm(vec1))
    norm2 = float(np.linalg.norm(vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def nearest_archetype(
    player_features: np.ndarray,
    archetype_centroids: np.ndarray,
) -> tuple[int, float]:
    """Find the nearest archetype centroid to a player's feature vector.

    Args:
        player_features: 1-D feature array (54-dim or reduced).
        archetype_centroids: 2-D array of shape (n_archetypes, n_features).

    Returns:
        Tuple of (cluster_index, similarity_score).
    """
    similarities = np.array(
        [cosine_similarity(player_features, c) for c in archetype_centroids]
    )
    idx = int(np.argmax(similarities))
    return idx, float(similarities[idx])


def feature_extremes(
    feature_dict: dict[str, float],
    top_k: int = 3,
) -> list[tuple[str, float]]:
    """Return the *top_k* features with the highest absolute values.

    Args:
        feature_dict: Mapping from feature name to value.
        top_k: Number of extreme features to return.

    Returns:
        List of (feature_name, value) sorted by |value| descending.
    """
    sorted_items = sorted(
        feature_dict.items(), key=lambda kv: abs(kv[1]), reverse=True
    )
    return sorted_items[:top_k]


# Feature description vocabulary for auto-naming
_FEATURE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "clutch_delta": {
        "high": "performs better in death overs than powerplay",
        "low": "struggles to accelerate under pressure",
    },
    "dot_pct_spi_extreme": {
        "high": "dot-ball heavy in extreme pressure",
        "low": "avoids dot balls even in extreme pressure",
    },
    "sr_spi_extreme": {
        "high": "high strike rate in extreme pressure",
        "low": "conserves wicket in extreme pressure",
    },
    "sr_spi_low": {
        "high": "very aggressive in low-pressure situations",
        "low": "cautious even in low-pressure situations",
    },
    "boundary_pct_spi_extreme": {
        "high": "boundary-dependent in extreme pressure",
        "low": "relies on rotation in extreme pressure",
    },
    "consistency_index": {
        "high": "highly consistent scorer",
        "low": "inconsistent output",
    },
    "recovery_rate": {
        "high": "recovers quickly after dot balls",
        "low": "struggles to recover after dot balls",
    },
    "big_match_index": {
        "high": "elevates performance in big matches",
        "low": "does not differentiate in big matches",
    },
    "cold_start_sr": {
        "high": "aggressive from ball one",
        "low": "slow to start innings",
    },
    "home_away_delta": {
        "high": "significantly better at home",
        "low": "consistent across venues",
    },
    "aggression_escalation": {
        "high": "escalates aggression through innings",
        "low": "maintains steady tempo throughout",
    },
    "hmm_form_regime": {
        "high": "in stable good form",
        "low": "volatile form",
    },
}


def feature_to_description(feature_name: str, value: float) -> str:
    """Map a feature name and value to a human-readable behavioural description.

    Args:
        feature_name: The feature field name.
        value: The feature value (sign determines high/low).

    Returns:
        Human-readable string describing the feature's meaning.
    """
    descriptors = _FEATURE_DESCRIPTIONS.get(feature_name)
    if descriptors is None:
        direction = "high" if value >= 0 else "low"
        return f"{direction} {feature_name.replace('_', ' ')}"
    direction = "high" if value >= 0 else "low"
    return descriptors.get(direction, f"{direction} {feature_name.replace('_', ' ')}")


def assign_to_nearest_centroid(
    point: np.ndarray,
    centroids: np.ndarray,
) -> int:
    """Assign a noise point to the nearest cluster centroid by Euclidean distance.

    Args:
        point: 1-D array of shape (n_features,).
        centroids: 2-D array of shape (n_clusters, n_features).

    Returns:
        Index of the nearest centroid.
    """
    distances = np.linalg.norm(centroids - point, axis=1)
    return int(np.argmin(distances))
