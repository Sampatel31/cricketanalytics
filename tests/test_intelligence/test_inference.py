"""Tests for sovereign/intelligence/inference.py."""

from __future__ import annotations

import pathlib
import pickle
import tempfile

import numpy as np
import polars as pl
import pytest

from sovereign.intelligence.inference import ArchetypeInferenceEngine
from sovereign.intelligence.reducer import DimensionalityReducer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_features(n_players: int = 10, seed: int = 42) -> pl.DataFrame:
    """Return a minimal synthetic features DataFrame."""
    from tests.test_intelligence.conftest import make_synthetic_features

    return make_synthetic_features(n_players=n_players, seed=seed)


def _build_engine_in_tmpdir(
    tmpdir: str,
    n_players: int = 30,
) -> ArchetypeInferenceEngine:
    """Train a tiny UMAP + HDBSCAN engine and return a ready-to-use inference engine."""
    features_df = _make_minimal_features(n_players=n_players)

    # Fit a small UMAP reducer
    reducer = DimensionalityReducer(models_dir=tmpdir, random_state=42)
    reducer._SCALER_PATH = "umap_scaler_T20I.joblib"
    reducer._UMAP_CLUSTER_PATH = "umap_10d_T20I.joblib"
    reducer._UMAP_VIZ_PATH = "umap_2d_T20I.joblib"
    reducer.fit(features_df, n_components_cluster=5, n_components_viz=2, force=True)

    coords_5d = reducer.transform_clustering(features_df)

    # Fake cluster labels (two clusters)
    labels = np.array([i % 2 for i in range(n_players)])
    centroids = np.stack(
        [
            coords_5d[labels == c].mean(axis=0)
            for c in sorted(set(labels.tolist()))
        ]
    )

    # Save labels pickle (same format as train_hdbscan.py produces)
    labels_path = pathlib.Path(tmpdir) / "cluster_labels_T20I.pkl"
    with labels_path.open("wb") as fh:
        pickle.dump(
            {
                "format_type": "T20I",
                "labels": labels,
                "centroids": centroids,
                "player_ids": features_df["player_id"].to_list(),
                "n_clusters": 2,
                "silhouette": 0.5,
                "mean_ari": 0.9,
            },
            fh,
        )

    return ArchetypeInferenceEngine.from_files(tmpdir, format_type="T20I")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestArchetypeInferenceEngine:
    def test_from_files_loads_successfully(self) -> None:
        """from_files() constructs an engine without error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _build_engine_in_tmpdir(tmpdir)
            assert engine is not None
            assert engine.format_type == "T20I"

    def test_n_archetypes_matches_clusters(self) -> None:
        """n_archetypes equals the number of distinct cluster labels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _build_engine_in_tmpdir(tmpdir)
            assert engine.n_archetypes == 2

    def test_archetype_codes_are_arc_formatted(self) -> None:
        """All archetype codes follow the ARC_NNN naming convention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _build_engine_in_tmpdir(tmpdir)
            for code in engine.archetype_codes:
                assert code.startswith("ARC_"), f"Unexpected code: {code}"

    def test_predict_returns_list_of_correct_length(self) -> None:
        """predict() returns one code per player."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _build_engine_in_tmpdir(tmpdir)
            features_df = _make_minimal_features(n_players=5)
            codes = engine.predict(features_df)
            assert len(codes) == 5
            assert all(isinstance(c, str) for c in codes)

    def test_predict_codes_are_known_archetypes(self) -> None:
        """Every predicted code belongs to the set of known archetype codes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _build_engine_in_tmpdir(tmpdir)
            features_df = _make_minimal_features(n_players=10)
            codes = engine.predict(features_df)
            known = set(engine.archetype_codes)
            for code in codes:
                assert code in known

    def test_predict_with_confidence_structure(self) -> None:
        """predict_with_confidence() returns dicts with required keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _build_engine_in_tmpdir(tmpdir)
            features_df = _make_minimal_features(n_players=4)
            results = engine.predict_with_confidence(features_df)
            assert len(results) == 4
            for r in results:
                assert "archetype_code" in r
                assert "cluster_index" in r
                assert "confidence" in r
                assert "coords_10d" in r
                assert 0.0 <= r["confidence"] <= 1.0

    def test_export_assignments_schema(self) -> None:
        """export_assignments() returns the expected column schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = _build_engine_in_tmpdir(tmpdir)
            features_df = _make_minimal_features(n_players=6)
            df = engine.export_assignments(features_df, season="2024")
            assert isinstance(df, pl.DataFrame)
            expected_cols = {"player_id", "format", "season", "archetype_code", "confidence"}
            assert expected_cols <= set(df.columns)
            assert len(df) == 6
            assert df["format"][0] == "T20I"
            assert df["season"][0] == "2024"

    def test_from_files_raises_for_missing_labels(self) -> None:
        """from_files() raises FileNotFoundError when cluster_labels file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            features_df = _make_minimal_features(n_players=20)
            reducer = DimensionalityReducer(models_dir=tmpdir, random_state=42)
            reducer._SCALER_PATH = "umap_scaler_T20I.joblib"
            reducer._UMAP_CLUSTER_PATH = "umap_10d_T20I.joblib"
            reducer._UMAP_VIZ_PATH = "umap_2d_T20I.joblib"
            reducer.fit(features_df, n_components_cluster=5, n_components_viz=2, force=True)
            # Do NOT write cluster_labels_T20I.pkl
            with pytest.raises(FileNotFoundError, match="cluster_labels"):
                ArchetypeInferenceEngine.from_files(tmpdir, format_type="T20I")

    def test_from_files_raises_for_missing_umap(self) -> None:
        """from_files() raises FileNotFoundError when UMAP files are absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError, match="UMAP models"):
                ArchetypeInferenceEngine.from_files(tmpdir, format_type="T20I")
