"""Tests for sovereign/intelligence/reducer.py (5 tests)."""

from __future__ import annotations

import pathlib
import tempfile

import numpy as np
import pytest

from sovereign.intelligence.reducer import DimensionalityReducer


class TestDimensionalityReducer:
    def test_fit_and_transform_cluster(self, synthetic_features_df) -> None:
        """UMAP 54D→10D reduces correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reducer = DimensionalityReducer(models_dir=tmpdir)
            reducer.fit(synthetic_features_df, n_components_cluster=10, n_components_viz=2)
            result = reducer.transform_clustering(synthetic_features_df)
            assert result.shape == (len(synthetic_features_df), 10)

    def test_fit_and_transform_viz(self, synthetic_features_df) -> None:
        """UMAP 54D→2D reduces correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reducer = DimensionalityReducer(models_dir=tmpdir)
            reducer.fit(synthetic_features_df, n_components_cluster=5, n_components_viz=2)
            result = reducer.transform_viz(synthetic_features_df)
            assert result.shape == (len(synthetic_features_df), 2)

    def test_scaler_normalizes_features(self, synthetic_features_df) -> None:
        """Scaler normalizes features."""
        with tempfile.TemporaryDirectory() as tmpdir:
            reducer = DimensionalityReducer(models_dir=tmpdir)
            reducer.fit(synthetic_features_df)
            # Check scaler was fitted
            assert reducer._scaler is not None
            assert hasattr(reducer._scaler, "mean_")

    def test_model_caching(self, synthetic_features_df) -> None:
        """Loading cached models works without refit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            r1 = DimensionalityReducer(models_dir=tmpdir)
            r1.fit(synthetic_features_df)

            r2 = DimensionalityReducer(models_dir=tmpdir)
            # Should load from cache — no force
            loaded = r2._try_load_models()
            assert loaded
            assert r2.is_fitted

    def test_force_refit(self, synthetic_features_df) -> None:
        """Force refit ignores cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            r1 = DimensionalityReducer(models_dir=tmpdir)
            r1.fit(synthetic_features_df)

            r2 = DimensionalityReducer(models_dir=tmpdir)
            r2.fit(synthetic_features_df, force=True)
            assert r2.is_fitted
