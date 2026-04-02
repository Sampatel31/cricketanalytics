"""Shared utility functions for the feature engineering layer."""

from __future__ import annotations

from typing import Optional

import polars as pl


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp *value* to the closed interval [*min_val*, *max_val*].

    Args:
        value: The value to clamp.
        min_val: Lower bound (inclusive).
        max_val: Upper bound (inclusive).

    Returns:
        ``value`` clamped to [``min_val``, ``max_val``].
    """
    return max(min_val, min(max_val, value))


def safe_divide(num: float, denom: float, default: float = 0.0) -> float:
    """Divide *num* by *denom*, returning *default* when *denom* is zero.

    Args:
        num: Numerator.
        denom: Denominator.
        default: Value returned when *denom* is zero or very close to zero.

    Returns:
        ``num / denom`` or *default* when division is unsafe.
    """
    if abs(denom) < 1e-10:
        return default
    return num / denom


def compute_sr(runs: float, legal_balls: float) -> Optional[float]:
    """Compute batting strike rate (runs per 100 balls).

    Args:
        runs: Total runs scored.
        legal_balls: Number of legal balls faced.

    Returns:
        Strike rate in [0, ∞) or ``None`` when *legal_balls* is zero.
    """
    if legal_balls < 1e-10:
        return None
    return (runs / legal_balls) * 100.0


def compute_economy(runs: float, balls: float) -> Optional[float]:
    """Compute bowling economy rate (runs per over).

    Args:
        runs: Runs conceded.
        balls: Legal balls bowled (not overs).

    Returns:
        Economy rate or ``None`` when *balls* is zero.
    """
    if balls < 1e-10:
        return None
    overs = balls / 6.0
    return runs / overs


def compute_dot_pct(dot_balls: float, legal_balls: float) -> Optional[float]:
    """Compute dot ball percentage.

    Args:
        dot_balls: Deliveries where the batter scored 0 runs.
        legal_balls: Total legal balls faced.

    Returns:
        Dot ball percentage in [0, 100] or ``None`` when *legal_balls* is zero.
    """
    if legal_balls < 1e-10:
        return None
    return (dot_balls / legal_balls) * 100.0


def compute_boundary_pct(boundaries: float, legal_balls: float) -> Optional[float]:
    """Compute boundary ball percentage.

    Args:
        boundaries: Deliveries resulting in a 4 or 6.
        legal_balls: Total legal balls faced.

    Returns:
        Boundary percentage in [0, 100] or ``None`` when *legal_balls* is zero.
    """
    if legal_balls < 1e-10:
        return None
    return (boundaries / legal_balls) * 100.0


def rolling_mean(series: pl.Series, window: int) -> pl.Series:
    """Compute a centered rolling mean of *series* with the given *window* size.

    Uses Polars built-in ``rolling_mean`` with ``min_samples=1`` so boundary
    values are never ``null``.

    Args:
        series: A numeric Polars Series.
        window: Rolling window width.

    Returns:
        A new Series with the same length as *series*.
    """
    return series.rolling_mean(window_size=window, min_samples=1)


def coefficient_of_variation(series: pl.Series) -> Optional[float]:
    """Compute the coefficient of variation (std / mean) for *series*.

    Args:
        series: A numeric Polars Series.

    Returns:
        CV value or ``None`` when the mean is zero or *series* is empty.
    """
    if series.is_empty():
        return None
    mean = series.mean()
    if mean is None or abs(mean) < 1e-10:
        return None
    std = series.std()
    if std is None:
        return None
    return std / mean


def normalize_score(
    value: float,
    min_val: float,
    max_val: float,
    default: float = 0.5,
) -> float:
    """Linearly normalise *value* from [*min_val*, *max_val*] to [0, 1].

    Args:
        value: The raw value to normalise.
        min_val: Minimum of the expected range.
        max_val: Maximum of the expected range.
        default: Returned when ``min_val == max_val``.

    Returns:
        Normalised value in [0, 1].
    """
    if abs(max_val - min_val) < 1e-10:
        return default
    normalised = (value - min_val) / (max_val - min_val)
    return clamp(normalised, 0.0, 1.0)
