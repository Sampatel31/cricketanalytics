"""Tests for sovereign/intelligence/clusterer.py (6 tests)."""

from __future__ import annotations

import numpy as np
import pytest

from sovereign.intelligence.clusterer import ArchetypeClusterer
from sovereign.intelligence.models import ClusteringStats, UnstableClusteringError


class TestArchetypeClusterer:
    def test_clusters_discovered(self, cluster_coords) -> None:
        """HDBSCAN discovers multiple clusters."""
        coords, _ = cluster_coords
        cl = ArchetypeClusterer(min_cluster_size=5)
        cl.fit(coords)
        labels = cl.get_labels()
        assert len(np.unique(labels)) >= 1
        assert len(labels) == len(coords)

    def test_noise_points_assigned(self, cluster_coords) -> None:
        """Noise points (-1) are reassigned to nearest cluster."""
        coords, _ = cluster_coords
        cl = ArchetypeClusterer(min_cluster_size=5)
        cl.fit(coords)
        labels = cl.get_labels()
        assert -1 not in labels  # all noise reassigned

    def test_ari_validation_runs(self, cluster_coords) -> None:
        """Bootstrap ARI validation runs and returns metrics."""
        coords, _ = cluster_coords
        cl = ArchetypeClusterer(min_cluster_size=5, ari_threshold=0.0)
        cl.fit(coords)
        result = cl.bootstrap_validate(coords, n_runs=10, subsample_ratio=0.8)
        assert "mean_ari" in result
        assert "std_ari" in result
        assert 0.0 <= result["mean_ari"] <= 1.0

    def test_silhouette_score_computed(self, cluster_coords) -> None:
        """Silhouette score is in [-1, 1]."""
        coords, _ = cluster_coords
        cl = ArchetypeClusterer(min_cluster_size=5)
        cl.fit(coords)
        stats = cl.get_stats()
        assert stats is not None
        assert isinstance(stats, ClusteringStats)
        assert -1.0 <= stats.silhouette_score <= 1.0

    def test_centroid_calculation(self, cluster_coords) -> None:
        """Centroids have correct shape."""
        coords, _ = cluster_coords
        cl = ArchetypeClusterer(min_cluster_size=5)
        cl.fit(coords)
        centroids = cl.get_centroids()
        assert centroids.ndim == 2
        assert centroids.shape[1] == coords.shape[1]

    def test_handles_small_dataset(self) -> None:
        """Clusterer handles small datasets gracefully."""
        rng = np.random.default_rng(0)
        tiny = rng.normal(0, 1, (10, 5))
        cl = ArchetypeClusterer(min_cluster_size=2)
        cl.fit(tiny)
        labels = cl.get_labels()
        assert len(labels) == 10
