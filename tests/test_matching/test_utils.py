"""Tests for sovereign/matching/utils.py (6 tests)."""

from __future__ import annotations

import numpy as np
import pytest

from sovereign.matching.utils import (
    cosine_similarity,
    get_age_factor,
    get_format_multiplier,
    get_recommendation,
    normalize_vector,
)


class TestCosineSimilarity:
    """Tests for cosine_similarity."""

    def test_identical_vectors_return_one(self) -> None:
        """Cosine similarity of a vector with itself should be 1.0."""
        vec = np.array([0.6, 0.8, 0.0])
        result = cosine_similarity(vec, vec)
        assert abs(result - 1.0) < 1e-9

    def test_orthogonal_vectors_return_zero(self) -> None:
        """Orthogonal vectors should yield 0.0 cosine similarity."""
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])
        result = cosine_similarity(vec1, vec2)
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_zero_norm_vector_returns_zero(self) -> None:
        """A zero vector should yield 0.0 similarity (guard against div/0)."""
        zero = np.zeros(5)
        other = np.ones(5)
        assert cosine_similarity(zero, other) == 0.0
        assert cosine_similarity(other, zero) == 0.0

    def test_result_clamped_to_unit_interval(self) -> None:
        """Result must always be in [0, 1] regardless of inputs."""
        rng = np.random.default_rng(99)
        for _ in range(50):
            v1 = rng.uniform(0, 10, 54)
            v2 = rng.uniform(0, 10, 54)
            result = cosine_similarity(v1, v2)
            assert 0.0 <= result <= 1.0


class TestNormalizeVector:
    """Tests for normalize_vector."""

    def test_unit_norm_after_normalization(self) -> None:
        """Normalized vector should have L2 norm ≈ 1.0."""
        vec = np.array([3.0, 4.0])
        normed = normalize_vector(vec)
        assert abs(float(np.linalg.norm(normed)) - 1.0) < 1e-9

    def test_zero_vector_returned_unchanged(self) -> None:
        """Zero vector should be returned unchanged (no div/0)."""
        zero = np.zeros(5)
        result = normalize_vector(zero)
        np.testing.assert_array_equal(result, zero)


class TestGetAgeFactor:
    """Tests for get_age_factor."""

    @pytest.mark.parametrize("age,expected", [
        (20, 1.0),
        (28, 1.0),
        (29, 0.95),
        (32, 0.95),
        (33, 0.85),
        (40, 0.85),
    ])
    def test_age_brackets(self, age: int, expected: float) -> None:
        """Verify each age bracket returns the correct multiplier."""
        assert get_age_factor(age) == pytest.approx(expected)


class TestGetFormatMultiplier:
    """Tests for get_format_multiplier."""

    @pytest.mark.parametrize("fmt,expected", [
        ("T20I", 1.2),
        ("ODI", 0.9),
        ("TEST", 0.6),
        ("t20i", 1.2),  # case-insensitive
    ])
    def test_known_formats(self, fmt: str, expected: float) -> None:
        """Known format codes return the correct multiplier."""
        assert get_format_multiplier(fmt) == pytest.approx(expected)

    def test_unknown_format_raises(self) -> None:
        """Unknown format code should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown format"):
            get_format_multiplier("IPL")


class TestGetRecommendation:
    """Tests for get_recommendation."""

    @pytest.mark.parametrize("pct,expected", [
        (25.0, "BID"),
        (21.0, "BID"),
        (20.0, "WAIT"),  # boundary — not strictly > 20
        (10.0, "WAIT"),
        (5.0, "NEUTRAL"),  # boundary — not strictly > 5
        (0.0, "NEUTRAL"),
        (-4.9, "NEUTRAL"),
        (-5.0, "NEUTRAL"),
        (-5.1, "AVOID"),
        (-30.0, "AVOID"),
    ])
    def test_recommendation_thresholds(
        self, pct: float, expected: str
    ) -> None:
        """Verify each arbitrage percentage maps to the correct recommendation."""
        assert get_recommendation(pct) == expected
