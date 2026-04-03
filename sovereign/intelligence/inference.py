"""Model loading and inference for player archetype assignment.

Provides :class:`ArchetypeInferenceEngine` which:
- Loads trained UMAP models from pickle files or the ``umap_models`` DB table.
- Loads HDBSCAN cluster labels from pickle files or the ``hdbscan_clusters`` table.
- Maps new player feature vectors → 10D UMAP coordinates → cluster label → archetype.
- Exports player archetype assignments to the ``player_archetypes`` DB table.

Quick start::

    engine = ArchetypeInferenceEngine.from_files(
        models_dir="data/models",
        format_type="T20I",
    )
    archetype_codes = engine.predict(features_df)
"""

from __future__ import annotations

import logging
import pathlib
import pickle
from typing import Optional

import numpy as np
import polars as pl

from sovereign.intelligence.reducer import DimensionalityReducer
from sovereign.intelligence.utils import assign_to_nearest_centroid

logger = logging.getLogger(__name__)


class ArchetypeInferenceEngine:
    """Predict player archetypes from 54D feature vectors.

    After construction, call :meth:`predict` to obtain archetype codes for a
    batch of players.

    Args:
        reducer: A fitted :class:`DimensionalityReducer`.
        labels: 1-D array of cluster labels aligned to the training players.
        centroids: 2-D centroid array of shape ``(n_clusters, n_dims)``.
        format_type: Cricket format this engine was built for.
        archetype_map: Optional dict mapping cluster index → archetype code.
            Auto-generated as ``ARC_000``, ``ARC_001``, … when omitted.
    """

    def __init__(
        self,
        reducer: DimensionalityReducer,
        labels: np.ndarray,
        centroids: np.ndarray,
        format_type: str = "T20I",
        archetype_map: Optional[dict[int, str]] = None,
    ) -> None:
        self._reducer = reducer
        self._labels = labels
        self._centroids = centroids
        self._format_type = format_type

        unique_clusters = sorted(set(int(l) for l in labels))
        if archetype_map is not None:
            self._archetype_map = archetype_map
        else:
            self._archetype_map = {
                c: f"ARC_{i:03d}" for i, c in enumerate(unique_clusters)
            }

    # ------------------------------------------------------------------
    # Factory constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_files(
        cls,
        models_dir: str | pathlib.Path,
        format_type: str = "T20I",
    ) -> "ArchetypeInferenceEngine":
        """Load models from pickle files saved by the training scripts.

        Expected files in *models_dir*:

        - ``umap_scaler_{format_type}.joblib``
        - ``umap_10d_{format_type}.joblib``
        - ``umap_2d_{format_type}.joblib``
        - ``cluster_labels_{format_type}.pkl``

        Args:
            models_dir: Directory containing the saved model files.
            format_type: Cricket format (e.g. ``"T20I"``).

        Returns:
            A ready-to-use :class:`ArchetypeInferenceEngine`.

        Raises:
            FileNotFoundError: If any expected model file is missing.
            RuntimeError: If the UMAP model files cannot be loaded.
        """
        models_dir = pathlib.Path(models_dir)

        # Load UMAP reducer (format-specific paths set by train_umap.py)
        reducer = DimensionalityReducer(models_dir=models_dir)
        reducer._SCALER_PATH = f"umap_scaler_{format_type}.joblib"
        reducer._UMAP_CLUSTER_PATH = f"umap_10d_{format_type}.joblib"
        reducer._UMAP_VIZ_PATH = f"umap_2d_{format_type}.joblib"

        if not reducer.load_models():
            raise FileNotFoundError(
                f"Could not load UMAP models for format '{format_type}' "
                f"from directory '{models_dir}'.  "
                f"Run train_umap.py first."
            )
        logger.info("Loaded UMAP models for %s from %s", format_type, models_dir)

        # Load cluster labels
        labels_path = models_dir / f"cluster_labels_{format_type}.pkl"
        if not labels_path.exists():
            raise FileNotFoundError(
                f"Cluster labels file not found: {labels_path}.  "
                f"Run train_hdbscan.py first."
            )
        with labels_path.open("rb") as fh:
            cluster_data = pickle.load(fh)

        labels = cluster_data["labels"]
        centroids = cluster_data["centroids"]
        logger.info(
            "Loaded cluster labels (%d players, %d clusters) for %s",
            len(labels),
            cluster_data.get("n_clusters", len(np.unique(labels))),
            format_type,
        )

        return cls(
            reducer=reducer,
            labels=labels,
            centroids=centroids,
            format_type=format_type,
        )

    @classmethod
    def from_db(
        cls,
        format_type: str = "T20I",
        models_dir: Optional[str | pathlib.Path] = None,
    ) -> "ArchetypeInferenceEngine":
        """Load UMAP and cluster data from the PostgreSQL database.

        Falls back to :meth:`from_files` if *models_dir* is provided and the
        DB is unavailable.

        Args:
            format_type: Cricket format to load.
            models_dir: Optional fallback directory for pickle files.

        Returns:
            A ready-to-use :class:`ArchetypeInferenceEngine`.
        """
        import io
        import joblib
        import sqlalchemy as sa

        try:
            from sovereign.config.settings import get_settings

            settings = get_settings()
            engine_db = sa.create_engine(settings.database_url)

            with engine_db.connect() as conn:
                # Load UMAP model blob
                row_umap = conn.execute(
                    sa.text(
                        "SELECT model_data FROM umap_models WHERE format_type = :fmt"
                    ),
                    {"fmt": format_type},
                ).fetchone()

                row_hdbscan = conn.execute(
                    sa.text(
                        "SELECT labels, centroids FROM hdbscan_clusters "
                        "WHERE format_type = :fmt"
                    ),
                    {"fmt": format_type},
                ).fetchone()

            if row_umap is None or row_hdbscan is None:
                raise RuntimeError(
                    f"No DB records found for format '{format_type}'.  "
                    "Run the training pipeline with --save-db first."
                )

            reducer = joblib.load(io.BytesIO(row_umap[0]))
            # Labels are stored as a JSON-encoded list of ints (not pickle)
            # to avoid unsafe deserialisation of arbitrary bytes.
            import json as _json
            labels = np.array(_json.loads(row_hdbscan[0].decode("utf-8")))
            centroids = np.array(_json.loads(row_hdbscan[1]))

            logger.info("Loaded inference models from DB for format %s", format_type)
            return cls(
                reducer=reducer,
                labels=labels,
                centroids=centroids,
                format_type=format_type,
            )

        except Exception as exc:
            if models_dir is not None:
                logger.warning(
                    "DB load failed (%s); falling back to files in %s",
                    exc,
                    models_dir,
                )
                return cls.from_files(models_dir=models_dir, format_type=format_type)
            raise

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(
        self,
        features_df: pl.DataFrame,
    ) -> list[str]:
        """Predict archetype codes for a batch of players.

        Args:
            features_df: Polars DataFrame with 54 feature columns (same schema
                used during training).  May also include metadata columns such
                as ``player_id``, ``format_type``, ``season``.

        Returns:
            List of archetype code strings (e.g. ``["ARC_002", "ARC_000", …]``),
            one per row of *features_df*.
        """
        # 54D → 10D via UMAP
        coords_10d = self._reducer.transform_clustering(features_df)

        archetype_codes: list[str] = []
        for point in coords_10d:
            cluster_idx = assign_to_nearest_centroid(point, self._centroids)
            # Map raw cluster index to archetype code
            code = self._archetype_map.get(cluster_idx, f"ARC_{cluster_idx:03d}")
            archetype_codes.append(code)

        return archetype_codes

    def predict_with_confidence(
        self,
        features_df: pl.DataFrame,
    ) -> list[dict]:
        """Predict archetypes and return confidence scores.

        Confidence is the inverse of the normalised Euclidean distance to the
        nearest centroid in 10D space (1.0 = exactly on centroid).

        Args:
            features_df: Polars DataFrame with 54 feature columns.

        Returns:
            List of dicts with keys:
            - ``archetype_code``: str
            - ``cluster_index``: int
            - ``confidence``: float in [0, 1]
            - ``coords_10d``: list[float]
        """
        coords_10d = self._reducer.transform_clustering(features_df)
        results: list[dict] = []
        # Pre-compute max distance for normalisation
        all_dists = np.linalg.norm(
            self._centroids[:, None, :] - coords_10d[None, :, :], axis=2
        )
        max_dist = float(all_dists.max()) if all_dists.size > 0 else 1.0

        for point in coords_10d:
            distances = np.linalg.norm(self._centroids - point, axis=1)
            cluster_idx = int(np.argmin(distances))
            min_dist = float(distances[cluster_idx])
            confidence = max(0.0, 1.0 - min_dist / (max_dist + 1e-9))
            code = self._archetype_map.get(cluster_idx, f"ARC_{cluster_idx:03d}")
            results.append(
                {
                    "archetype_code": code,
                    "cluster_index": cluster_idx,
                    "confidence": round(confidence, 4),
                    "coords_10d": point.tolist(),
                }
            )
        return results

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_assignments(
        self,
        features_df: pl.DataFrame,
        season: str = "2024",
    ) -> pl.DataFrame:
        """Return a DataFrame of player → archetype assignments.

        Args:
            features_df: Polars DataFrame with at least ``player_id`` and the
                54 feature columns.
            season: Season identifier to include in the output.

        Returns:
            Polars DataFrame with columns:
            ``player_id``, ``format``, ``season``, ``archetype_code``,
            ``confidence``.
        """
        player_ids: list = (
            features_df["player_id"].to_list()
            if "player_id" in features_df.columns
            else list(range(len(features_df)))
        )

        preds = self.predict_with_confidence(features_df)

        rows = [
            {
                "player_id": str(pid),
                "format": self._format_type,
                "season": season,
                "archetype_code": p["archetype_code"],
                "confidence": p["confidence"],
            }
            for pid, p in zip(player_ids, preds)
        ]
        return pl.DataFrame(rows)

    def save_assignments_to_db(
        self,
        features_df: pl.DataFrame,
        season: str = "2024",
    ) -> int:
        """Compute archetype assignments and upsert them into ``player_archetypes``.

        Args:
            features_df: Feature DataFrame with ``player_id`` column.
            season: Season identifier.

        Returns:
            Number of rows upserted.
        """
        import sqlalchemy as sa

        from sovereign.config.settings import get_settings

        assignments_df = self.export_assignments(features_df, season=season)
        rows = assignments_df.to_dicts()

        settings = get_settings()
        db_engine = sa.create_engine(settings.database_url)
        with db_engine.begin() as conn:
            for row in rows:
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO player_archetypes
                            (player_id, format, season, archetype_code, confidence)
                        VALUES (:player_id, :format, :season, :archetype_code, :confidence)
                        ON CONFLICT (player_id, format, season)
                        DO UPDATE SET archetype_code = EXCLUDED.archetype_code,
                                      confidence     = EXCLUDED.confidence
                        """
                    ),
                    row,
                )

        logger.info(
            "Upserted %d archetype assignments for format=%s season=%s",
            len(rows),
            self._format_type,
            season,
        )
        return len(rows)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def format_type(self) -> str:
        """Cricket format this engine was built for."""
        return self._format_type

    @property
    def n_archetypes(self) -> int:
        """Number of distinct archetypes in this engine."""
        return len(self._centroids)

    @property
    def archetype_codes(self) -> list[str]:
        """Sorted list of all archetype codes."""
        return sorted(self._archetype_map.values())
