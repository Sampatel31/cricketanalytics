"""Tests for sovereign/intelligence/utils.py (6 tests)."""

from __future__ import annotations

import numpy as np
import pytest

from sovereign.intelligence.utils import (
    assign_to_nearest_centroid,
    cosine_similarity,
    feature_extremes,
    feature_to_description,
    nearest_archetype,
)


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        v = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        v1 = np.array([1.0, 0.0])
        v2 = np.array([0.0, 1.0])
        assert cosine_similarity(v1, v2) == pytest.approx(0.0)

    def test_zero_vector_returns_zero(self) -> None:
        assert cosine_similarity(np.zeros(5), np.ones(5)) == 0.0


class TestNearestArchetype:
    def test_returns_correct_index(self) -> None:
        centroids = np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]])
        player = np.array([0.9, 0.1])
        idx, score = nearest_archetype(player, centroids)
        assert idx == 0
        assert 0.0 <= score <= 1.0

    def test_similarity_score_bounded(self) -> None:
        centroids = np.eye(4)
        player = np.array([0.1, 0.9, 0.0, 0.0])
        _, score = nearest_archetype(player, centroids)
        assert 0.0 <= score <= 1.0


class TestFeatureExtremes:
    def test_returns_top_k(self) -> None:
        fd = {"a": 0.1, "b": 5.0, "c": -3.0, "d": 0.5}
        result = feature_extremes(fd, top_k=2)
        assert len(result) == 2
        assert result[0][0] == "b"  # highest abs value

    def test_empty_dict(self) -> None:
        assert feature_extremes({}) == []


class TestFeatureToDescription:
    def test_known_feature(self) -> None:
        desc = feature_to_description("clutch_delta", 30.0)
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_unknown_feature(self) -> None:
        desc = feature_to_description("nonexistent_feature", 1.0)
        assert "nonexistent" in desc.lower() or "high" in desc.lower()


class TestAssignToNearestCentroid:
    def test_assigns_correctly(self) -> None:
        centroids = np.array([[0.0, 0.0], [10.0, 10.0]])
        point = np.array([0.5, 0.5])
        assert assign_to_nearest_centroid(point, centroids) == 0
