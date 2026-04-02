"""Tests for sovereign/intelligence/archetype.py (5 tests)."""

from __future__ import annotations

import numpy as np
import pytest

from sovereign.intelligence.archetype import ArchetypeDiscoverer
from sovereign.intelligence.models import Archetype


class TestArchetypeDiscoverer:
    def test_auto_naming_works(self, synthetic_features_df, cluster_coords) -> None:
        """Auto-naming produces non-empty labels."""
        coords, labels = cluster_coords
        discoverer = ArchetypeDiscoverer()
        centroids = np.array(
            [coords[labels == c].mean(axis=0) for c in np.unique(labels)]
        )
        archetypes = discoverer.discover(
            coords, synthetic_features_df, labels, centroids
        )
        for a in archetypes:
            assert isinstance(a.label, str)
            assert len(a.label) > 0

    def test_descriptions_generated(self, synthetic_features_df, cluster_coords) -> None:
        """Descriptions are non-empty strings."""
        coords, labels = cluster_coords
        discoverer = ArchetypeDiscoverer()
        centroids = np.array(
            [coords[labels == c].mean(axis=0) for c in np.unique(labels)]
        )
        archetypes = discoverer.discover(
            coords, synthetic_features_df, labels, centroids
        )
        for a in archetypes:
            assert isinstance(a.description, str)
            assert len(a.description) > 0

    def test_feature_extremes_identified(self) -> None:
        """Feature extremes correctly identify top features."""
        from sovereign.intelligence.utils import feature_extremes

        fd = {f"feat_{i}": float(i) for i in range(10)}
        extremes = feature_extremes(fd, top_k=3)
        assert len(extremes) == 3
        assert extremes[0][1] == 9.0

    def test_archetype_codes_unique(self, synthetic_features_df, cluster_coords) -> None:
        """Archetype codes are unique."""
        coords, labels = cluster_coords
        discoverer = ArchetypeDiscoverer()
        centroids = np.array(
            [coords[labels == c].mean(axis=0) for c in np.unique(labels)]
        )
        archetypes = discoverer.discover(
            coords, synthetic_features_df, labels, centroids
        )
        codes = [a.code for a in archetypes]
        assert len(codes) == len(set(codes))

    def test_archetype_model_fields(self, synthetic_features_df, cluster_coords) -> None:
        """Each Archetype has required fields populated."""
        coords, labels = cluster_coords
        discoverer = ArchetypeDiscoverer()
        centroids = np.array(
            [coords[labels == c].mean(axis=0) for c in np.unique(labels)]
        )
        archetypes = discoverer.discover(
            coords, synthetic_features_df, labels, centroids
        )
        for a in archetypes:
            assert isinstance(a, Archetype)
            assert a.cluster_size > 0
            assert 0.0 <= a.stability_ari <= 1.0
            assert len(a.centroid_features) > 0
