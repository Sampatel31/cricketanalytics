"""HDBSCAN density clustering for archetype discovery."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from sklearn.metrics import davies_bouldin_score, silhouette_score

from sovereign.intelligence.models import ClusteringStats, UnstableClusteringError
from sovereign.intelligence.utils import assign_to_nearest_centroid

logger = logging.getLogger(__name__)


class ArchetypeClusterer:
    """Cluster players using HDBSCAN on UMAP-reduced coordinates.

    Args:
        min_cluster_size: Minimum number of samples in a cluster.
        min_samples: HDBSCAN min_samples (defaults to min_cluster_size).
        ari_threshold: Minimum mean ARI for stable clustering.
    """

    def __init__(
        self,
        min_cluster_size: int = 15,
        min_samples: Optional[int] = None,
        ari_threshold: float = 0.85,
    ) -> None:
        self._min_cluster_size = min_cluster_size
        self._min_samples = min_samples or min_cluster_size
        self._ari_threshold = ari_threshold
        self._labels: Optional[np.ndarray] = None
        self._centroids: Optional[np.ndarray] = None
        self._noise_mask: Optional[np.ndarray] = None
        self._stats: Optional[ClusteringStats] = None
        self._fitted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(
        self,
        coords_10d: np.ndarray,
        min_cluster_size: Optional[int] = None,
    ) -> "ArchetypeClusterer":
        """Fit HDBSCAN on *coords_10d* and post-process noise points.

        Args:
            coords_10d: ndarray of shape (n_players, n_dims).
            min_cluster_size: Override the instance-level setting if provided.

        Returns:
            self (for chaining).
        """
        import hdbscan

        mcs = min_cluster_size or self._min_cluster_size
        logger.info(
            "Fitting HDBSCAN on %d×%d matrix (min_cluster_size=%d)",
            coords_10d.shape[0],
            coords_10d.shape[1],
            mcs,
        )
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=mcs,
            min_samples=self._min_samples,
            core_dist_n_jobs=-1,
        )
        raw_labels = clusterer.fit_predict(coords_10d)

        # Compute centroids of proper clusters
        unique_clusters = sorted(set(raw_labels) - {-1})
        if not unique_clusters:
            logger.warning("HDBSCAN found no clusters; all points labelled as noise")
            unique_clusters = [0]
            raw_labels = np.zeros(len(raw_labels), dtype=int)

        centroids = np.array(
            [coords_10d[raw_labels == c].mean(axis=0) for c in unique_clusters]
        )

        # Assign noise points to nearest centroid
        labels = raw_labels.copy()
        noise_mask = raw_labels == -1
        for i in np.where(noise_mask)[0]:
            labels[i] = unique_clusters[
                assign_to_nearest_centroid(coords_10d[i], centroids)
            ]

        self._labels = labels
        self._centroids = centroids
        self._noise_mask = noise_mask

        # Compute cluster quality metrics
        sil = self._compute_silhouette(coords_10d, labels)
        dbi = self._compute_davies_bouldin(coords_10d, labels)

        self._stats = ClusteringStats(
            n_clusters=len(unique_clusters),
            n_noise_points=int(noise_mask.sum()),
            silhouette_score=sil,
            davies_bouldin_index=dbi,
            stability_ari_mean=0.0,  # updated after bootstrap
            stability_ari_std=0.0,
        )
        self._fitted = True
        logger.info(
            "HDBSCAN found %d clusters, %d noise points",
            len(unique_clusters),
            int(noise_mask.sum()),
        )
        return self

    def bootstrap_validate(
        self,
        coords_10d: np.ndarray,
        n_runs: int = 1000,
        subsample_ratio: float = 0.8,
    ) -> dict[str, float]:
        """Validate clustering stability via bootstrap subsampling.

        Args:
            coords_10d: ndarray of shape (n_players, n_dims).
            n_runs: Number of bootstrap runs.
            subsample_ratio: Fraction of data to subsample each run.

        Returns:
            Dict with keys: ``mean_ari``, ``std_ari``, ``ari_distribution``.

        Raises:
            UnstableClusteringError: If mean ARI < ari_threshold.
        """
        import hdbscan
        from sklearn.metrics import adjusted_rand_score

        self._assert_fitted()
        rng = np.random.default_rng(42)
        n = len(coords_10d)
        k = max(2, int(n * subsample_ratio))

        base_labels = self._labels  # type: ignore[assignment]
        ari_scores: list[float] = []

        for _ in range(n_runs):
            idx = rng.choice(n, size=k, replace=False)
            sub = coords_10d[idx]
            sub_base = base_labels[idx]
            try:
                cl = hdbscan.HDBSCAN(
                    min_cluster_size=max(2, self._min_cluster_size // 2),
                    min_samples=max(2, self._min_samples // 2),
                    core_dist_n_jobs=1,
                )
                sub_labels = cl.fit_predict(sub)
                # Treat noise as its own cluster for ARI
                ari = adjusted_rand_score(sub_base, sub_labels)
                ari_scores.append(ari)
            except Exception:
                pass  # Skip degenerate runs

        if not ari_scores:
            ari_scores = [0.0]

        mean_ari = float(np.mean(ari_scores))
        std_ari = float(np.std(ari_scores))

        # Update stored stats
        if self._stats is not None:
            self._stats = ClusteringStats(
                n_clusters=self._stats.n_clusters,
                n_noise_points=self._stats.n_noise_points,
                silhouette_score=self._stats.silhouette_score,
                davies_bouldin_index=self._stats.davies_bouldin_index,
                stability_ari_mean=mean_ari,
                stability_ari_std=std_ari,
            )

        result = {
            "mean_ari": mean_ari,
            "std_ari": std_ari,
            "ari_distribution": ari_scores,
        }

        if mean_ari < self._ari_threshold:
            raise UnstableClusteringError(mean_ari, self._ari_threshold)

        return result

    def get_centroids(self) -> np.ndarray:
        """Return cluster centroids, shape (n_clusters, n_dims)."""
        self._assert_fitted()
        return self._centroids  # type: ignore[return-value]

    def get_labels(self) -> np.ndarray:
        """Return cluster label per player (noise reassigned)."""
        self._assert_fitted()
        return self._labels  # type: ignore[return-value]

    def get_noise_mask(self) -> np.ndarray:
        """Return boolean mask: True for points originally labelled noise."""
        self._assert_fitted()
        return self._noise_mask  # type: ignore[return-value]

    def get_stats(self) -> Optional[ClusteringStats]:
        """Return the most recently computed ClusteringStats."""
        return self._stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assert_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError(
                "ArchetypeClusterer is not fitted. Call fit() first."
            )

    @staticmethod
    def _compute_silhouette(coords: np.ndarray, labels: np.ndarray) -> float:
        unique = np.unique(labels)
        if len(unique) < 2:
            return 0.0
        try:
            return float(silhouette_score(coords, labels))
        except Exception:
            return 0.0

    @staticmethod
    def _compute_davies_bouldin(coords: np.ndarray, labels: np.ndarray) -> float:
        unique = np.unique(labels)
        if len(unique) < 2:
            return 0.0
        try:
            return float(davies_bouldin_score(coords, labels))
        except Exception:
            return 0.0
