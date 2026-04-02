"""Fixtures for matching engine tests."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from sovereign.features.models import FeatureVector
from sovereign.intelligence.models import Archetype
from sovereign.matching.models import FranchiseDNA

FEATURE_NAMES: list[str] = list(FeatureVector.model_fields.keys())
N_FEATURES: int = len(FEATURE_NAMES)  # 54
N_PLAYERS: int = 20


def _make_unit_vector(seed: int = 0) -> np.ndarray:
    """Return a deterministic unit vector of length 54."""
    rng = np.random.default_rng(seed)
    v = np.abs(rng.uniform(0.1, 1.0, N_FEATURES))
    return v / np.linalg.norm(v)


def make_features_df(n_players: int = N_PLAYERS, seed: int = 42) -> pl.DataFrame:
    """Synthetic player × 54 feature DataFrame."""
    rng = np.random.default_rng(seed)
    data: dict = {"player_id": [f"p{i:03d}" for i in range(n_players)]}
    data["player_name"] = [f"Player {i}" for i in range(n_players)]
    for name in FEATURE_NAMES:
        field = FeatureVector.model_fields[name]
        low, high = 0.0, 1.0
        for meta in field.metadata:
            if hasattr(meta, "ge"):
                low = float(meta.ge)
            if hasattr(meta, "le"):
                high = float(meta.le)
        data[name] = rng.uniform(max(0.0, low), max(1.0, high), n_players).tolist()
    data["confidence_weight"] = [1.0] * n_players
    data["innings_count"] = [20] * n_players
    return pl.DataFrame(data)


def make_archetypes_df(n_players: int = N_PLAYERS) -> pl.DataFrame:
    """Synthetic player → archetype mapping DataFrame."""
    archetypes = ["ARC_001", "ARC_002", "ARC_003"]
    codes = [archetypes[i % 3] for i in range(n_players)]
    labels = [f"Label {c}" for c in codes]
    return pl.DataFrame(
        {
            "player_id": [f"p{i:03d}" for i in range(n_players)],
            "archetype_code": codes,
            "archetype_label": labels,
        }
    )


def make_archetype_objects() -> list[Archetype]:
    """Return a small list of Archetype domain objects."""
    return [
        Archetype(
            code="ARC_001",
            label="Aggressive Opener",
            description="High strike rate openers",
            centroid_features={n: 0.5 for n in FEATURE_NAMES},
            cluster_size=10,
            stability_ari=0.9,
        ),
        Archetype(
            code="ARC_002",
            label="Anchor Batter",
            description="Consistent middle-order anchors",
            centroid_features={n: 0.5 for n in FEATURE_NAMES},
            cluster_size=8,
            stability_ari=0.88,
        ),
        Archetype(
            code="ARC_003",
            label="Death Bowler",
            description="Specialist death overs bowler",
            centroid_features={n: 0.5 for n in FEATURE_NAMES},
            cluster_size=6,
            stability_ari=0.85,
        ),
    ]


def make_franchise_dna(seed: int = 0) -> FranchiseDNA:
    """Create a synthetic FranchiseDNA for testing."""
    vec = _make_unit_vector(seed)
    return FranchiseDNA(
        dna_id="test-dna-id",
        franchise_name="Test Franchise",
        dna_mode="slider",
        feature_vector=dict(zip(FEATURE_NAMES, vec.tolist())),
        target_archetypes=["ARC_001"],
    )


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def features_df() -> pl.DataFrame:
    """20-player × 54-feature synthetic DataFrame."""
    return make_features_df()


@pytest.fixture
def archetypes_df() -> pl.DataFrame:
    """20-player → archetype mapping."""
    return make_archetypes_df()


@pytest.fixture
def archetype_objects() -> list[Archetype]:
    """Three Archetype domain objects."""
    return make_archetype_objects()


@pytest.fixture
def franchise_dna() -> FranchiseDNA:
    """Synthetic FranchiseDNA targeting ARC_001."""
    return make_franchise_dna()
