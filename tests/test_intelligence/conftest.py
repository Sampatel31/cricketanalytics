"""Fixtures for intelligence layer tests."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from sovereign.features.models import FeatureVector


# Number of synthetic players
N_PLAYERS = 60
N_FEATURES = 54
FEATURE_NAMES = list(FeatureVector.model_fields.keys())


def make_synthetic_features(
    n_players: int = N_PLAYERS,
    seed: int = 42,
) -> pl.DataFrame:
    """Generate a synthetic player × 54 feature DataFrame."""
    rng = np.random.default_rng(seed)
    data: dict[str, list] = {"player_id": [f"p{i:03d}" for i in range(n_players)]}
    for name in FEATURE_NAMES:
        field = FeatureVector.model_fields[name]
        # Extract bounds from metadata
        low = 0.0
        high = 1.0
        for meta in field.metadata:
            if hasattr(meta, "ge"):
                low = float(meta.ge)
            if hasattr(meta, "le"):
                high = float(meta.le)
        data[name] = rng.uniform(low, high, n_players).tolist()
    data["format_type"] = ["T20I"] * n_players
    data["season"] = ["2024"] * n_players
    data["confidence_weight"] = [1.0] * n_players
    data["innings_count"] = [20] * n_players
    return pl.DataFrame(data)


def make_cluster_coords(
    n_players: int = N_PLAYERS,
    n_dims: int = 10,
    n_clusters: int = 4,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (coords_10d, true_labels) with clear cluster structure."""
    rng = np.random.default_rng(seed)
    coords = []
    labels = []
    per_cluster = n_players // n_clusters
    for c in range(n_clusters):
        center = rng.uniform(-5, 5, n_dims)
        cluster_pts = rng.normal(center, 0.3, (per_cluster, n_dims))
        coords.append(cluster_pts)
        labels.extend([c] * per_cluster)
    remainder = n_players - n_clusters * per_cluster
    if remainder:
        center = rng.uniform(-5, 5, n_dims)
        coords.append(rng.normal(center, 0.3, (remainder, n_dims)))
        labels.extend([n_clusters - 1] * remainder)
    return np.vstack(coords), np.array(labels)


@pytest.fixture
def synthetic_features_df() -> pl.DataFrame:
    """60-player × 54-feature synthetic DataFrame."""
    return make_synthetic_features(n_players=N_PLAYERS)


@pytest.fixture
def cluster_coords() -> tuple[np.ndarray, np.ndarray]:
    """60×10 coords with 4 clear clusters + true labels."""
    return make_cluster_coords(n_players=N_PLAYERS, n_clusters=4)


@pytest.fixture
def small_features_df() -> pl.DataFrame:
    """Small (5 players) feature DataFrame for edge-case tests."""
    return make_synthetic_features(n_players=5)
