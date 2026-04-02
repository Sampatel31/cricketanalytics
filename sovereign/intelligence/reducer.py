"""UMAP dimensionality reduction for the intelligence layer.

Reduces 54D player fingerprints to:
- 10D for HDBSCAN clustering
- 2D for galaxy-view visualisation
"""

from __future__ import annotations

import logging
import pathlib
from typing import Optional

import joblib
import numpy as np
import polars as pl
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

_MODELS_DIR = pathlib.Path("data/models")


class DimensionalityReducer:
    """Reduce player feature vectors using UMAP.

    Fits a ``StandardScaler`` and two UMAP models:
    - ``umap_cluster``: 54D → *n_components_cluster* (default 10) for clustering
    - ``umap_viz``:    54D → *n_components_viz* (default 2) for visualisation

    Fitted models are persisted to ``data/models/`` via joblib so that
    subsequent calls reload rather than refit.

    Args:
        models_dir: Directory to store / load joblib model files.
        random_state: Random seed for reproducibility.
    """

    _SCALER_PATH = "umap_scaler.joblib"
    _UMAP_CLUSTER_PATH = "umap_10d.joblib"
    _UMAP_VIZ_PATH = "umap_2d.joblib"

    def __init__(
        self,
        models_dir: str | pathlib.Path = _MODELS_DIR,
        random_state: int = 42,
    ) -> None:
        self._models_dir = pathlib.Path(models_dir)
        self._random_state = random_state
        self._scaler: Optional[StandardScaler] = None
        self._umap_cluster = None
        self._umap_viz = None
        self._fitted = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(
        self,
        features_df: pl.DataFrame,
        n_components_cluster: int = 10,
        n_components_viz: int = 2,
        force: bool = False,
    ) -> "DimensionalityReducer":
        """Fit scaler + UMAP models on *features_df*.

        Loads cached models if they exist unless *force=True*.

        Args:
            features_df: Polars DataFrame with 54 numeric feature columns.
            n_components_cluster: UMAP output dimensions for clustering.
            n_components_viz: UMAP output dimensions for visualisation.
            force: If True, always refit even if cached models exist.

        Returns:
            self (for chaining).
        """
        if not force and self._try_load_models():
            logger.info("Loaded cached UMAP models from %s", self._models_dir)
            return self

        import umap as umap_lib

        X = self._to_numpy(features_df)
        logger.info("Fitting StandardScaler on %d×%d matrix", X.shape[0], X.shape[1])
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        logger.info(
            "Fitting UMAP %dD→%dD (cluster)", X.shape[1], n_components_cluster
        )
        self._umap_cluster = umap_lib.UMAP(
            n_components=n_components_cluster,
            n_neighbors=15,
            min_dist=0.1,
            random_state=self._random_state,
            verbose=False,
        )
        self._umap_cluster.fit(X_scaled)

        logger.info(
            "Fitting UMAP %dD→%dD (viz)", X.shape[1], n_components_viz
        )
        self._umap_viz = umap_lib.UMAP(
            n_components=n_components_viz,
            n_neighbors=50,
            min_dist=0.05,
            random_state=self._random_state,
            verbose=False,
        )
        self._umap_viz.fit(X_scaled)

        self._fitted = True
        self._save_models()
        return self

    def transform_clustering(self, features_df: pl.DataFrame) -> np.ndarray:
        """Transform *features_df* using the clustering UMAP.

        Args:
            features_df: Polars DataFrame with 54 feature columns.

        Returns:
            np.ndarray of shape (n_players, n_components_cluster).
        """
        self._assert_fitted()
        X = self._to_numpy(features_df)
        X_scaled = self._scaler.transform(X)  # type: ignore[union-attr]
        return self._umap_cluster.transform(X_scaled)  # type: ignore[union-attr]

    def transform_viz(self, features_df: pl.DataFrame) -> np.ndarray:
        """Transform *features_df* using the visualisation UMAP.

        Args:
            features_df: Polars DataFrame with 54 feature columns.

        Returns:
            np.ndarray of shape (n_players, n_components_viz).
        """
        self._assert_fitted()
        X = self._to_numpy(features_df)
        X_scaled = self._scaler.transform(X)  # type: ignore[union-attr]
        return self._umap_viz.transform(X_scaled)  # type: ignore[union-attr]

    @property
    def is_fitted(self) -> bool:
        """True after :meth:`fit` has been called successfully."""
        return self._fitted

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _feature_columns(df: pl.DataFrame) -> list[str]:
        """Return numeric columns excluding metadata."""
        _META = {"player_id", "format_type", "season", "confidence_weight", "innings_count"}
        return [c for c in df.columns if c not in _META and df[c].dtype in (pl.Float64, pl.Float32, pl.Int32, pl.Int64)]

    def _to_numpy(self, features_df: pl.DataFrame) -> np.ndarray:
        """Extract numeric feature columns as a float64 numpy array."""
        cols = self._feature_columns(features_df)
        if not cols:
            raise ValueError("features_df contains no numeric feature columns")
        return features_df.select(cols).to_numpy().astype(np.float64)

    def _assert_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError(
                "DimensionalityReducer is not fitted. Call fit() first."
            )

    def _save_models(self) -> None:
        self._models_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._scaler, self._models_dir / self._SCALER_PATH)
        joblib.dump(self._umap_cluster, self._models_dir / self._UMAP_CLUSTER_PATH)
        joblib.dump(self._umap_viz, self._models_dir / self._UMAP_VIZ_PATH)
        logger.info("Saved UMAP models to %s", self._models_dir)

    def _try_load_models(self) -> bool:
        """Load persisted models if all three files exist. Returns True on success."""
        paths = [
            self._models_dir / self._SCALER_PATH,
            self._models_dir / self._UMAP_CLUSTER_PATH,
            self._models_dir / self._UMAP_VIZ_PATH,
        ]
        if not all(p.exists() for p in paths):
            return False
        try:
            self._scaler = joblib.load(paths[0])
            self._umap_cluster = joblib.load(paths[1])
            self._umap_viz = joblib.load(paths[2])
            self._fitted = True
            return True
        except Exception as exc:
            logger.warning("Failed to load cached models: %s", exc)
            return False
