"""Shared utility functions for the matching engine.

Provides vectorized helpers for cosine similarity, L2 normalization,
age factors, format multipliers, and recommendation thresholds.
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Vector math
# ---------------------------------------------------------------------------


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute cosine similarity between two vectors, clamped to [0, 1].

    Handles zero-norm vectors by returning 0.0 (no similarity).

    Args:
        vec1: First vector (must be finite, same shape as vec2).
        vec2: Second vector.

    Returns:
        Cosine similarity in [0.0, 1.0].
    """
    epsilon: float = 1e-8
    norm1 = float(np.linalg.norm(vec1))
    norm2 = float(np.linalg.norm(vec2))
    if norm1 < epsilon or norm2 < epsilon:
        return 0.0
    raw = float(np.dot(vec1, vec2)) / (norm1 * norm2)
    # Clamp to [0, 1]: cricket DNA vectors are non-negative so we should
    # not get negative cosine similarity in practice, but guard against
    # floating-point noise.
    return float(np.clip(raw, 0.0, 1.0))


def normalize_vector(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a vector.

    Args:
        vec: Input array (any shape with at least one element).

    Returns:
        Unit vector with the same shape as *vec*.  If the input norm is
        below epsilon the input is returned unchanged to avoid division
        by zero.
    """
    epsilon: float = 1e-8
    norm = float(np.linalg.norm(vec))
    if norm < epsilon:
        return vec.copy()
    return vec / norm


# ---------------------------------------------------------------------------
# Age / format helpers
# ---------------------------------------------------------------------------


def get_age_factor(age: int) -> float:
    """Return the age-based valuation multiplier.

    - Young  (≤ 28): 1.00
    - Peaked (29–32): 0.95
    - Veteran (> 32): 0.85

    Args:
        age: Player age in years.

    Returns:
        Multiplier in {0.85, 0.95, 1.0}.
    """
    if age <= 28:
        return 1.0
    if age <= 32:
        return 0.95
    return 0.85


def get_format_multiplier(format_type: str) -> float:
    """Return the format-based valuation multiplier.

    - T20I: 1.2
    - ODI:  0.9
    - TEST: 0.6

    Args:
        format_type: One of "T20I", "ODI", "TEST" (case-insensitive).

    Returns:
        Multiplier from the table above.

    Raises:
        ValueError: If *format_type* is not recognised.
    """
    mapping: dict[str, float] = {
        "T20I": 1.2,
        "ODI": 0.9,
        "TEST": 0.6,
    }
    upper = format_type.upper()
    if upper not in mapping:
        raise ValueError(
            f"Unknown format '{format_type}'. Expected one of {list(mapping)}"
        )
    return mapping[upper]


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


def get_recommendation(arbitrage_pct: float) -> str:
    """Map an arbitrage percentage to a bid recommendation.

    Thresholds (from settings defaults):
    - > +20%  → "BID"    (strong value)
    - +5% to +20% → "WAIT"   (slight value, monitor)
    - −5% to +5%  → "NEUTRAL" (fair price)
    - < −5%  → "AVOID"  (overpriced)

    Args:
        arbitrage_pct: (fair_value − market_price) / market_price × 100.

    Returns:
        One of "BID", "WAIT", "NEUTRAL", "AVOID".
    """
    if arbitrage_pct > 20.0:
        return "BID"
    if arbitrage_pct > 5.0:
        return "WAIT"
    if arbitrage_pct >= -5.0:
        return "NEUTRAL"
    return "AVOID"
