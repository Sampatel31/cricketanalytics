"""Pydantic models for the intelligence layer.

This module defines type-safe data models for archetypes, transitions,
clustering statistics, and sovereign alerts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class ClusteringError(Exception):
    """Raised when HDBSCAN clustering fails to produce valid results."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Clustering error: {reason}")


class UnstableClusteringError(ClusteringError):
    """Raised when bootstrap ARI is below the stability threshold."""

    def __init__(self, mean_ari: float, threshold: float) -> None:
        self.mean_ari = mean_ari
        self.threshold = threshold
        super().__init__(
            f"Clustering unstable: mean ARI {mean_ari:.3f} < threshold {threshold:.3f}"
        )


class InsufficientDataError(Exception):
    """Raised when there are not enough players/data points for clustering."""

    def __init__(self, required: int, actual: int) -> None:
        self.required = required
        self.actual = actual
        super().__init__(f"Need {required} data points, got {actual}")


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class Archetype(BaseModel):
    """Discovered behavioural archetype from HDBSCAN clustering."""

    code: str = Field(description="Unique archetype code, e.g. 'ARC_001'")
    label: str = Field(description="Auto-generated human-readable label")
    description: str = Field(description="Behavioural summary")
    centroid_features: dict[str, float] = Field(
        description="54-dimensional feature vector centroid"
    )
    cluster_size: int = Field(ge=0, description="Number of players in this archetype")
    stability_ari: float = Field(
        ge=0.0, le=1.0, description="Adjusted Rand Index from bootstrap validation"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when archetype was created",
    )


class ArchetypeTransition(BaseModel):
    """Records a player's movement between archetypes across seasons."""

    player_id: str = Field(description="Unique player identifier")
    season_from: str = Field(description="Source season, e.g. '2023'")
    season_to: str = Field(description="Target season, e.g. '2024'")
    archetype_from: str = Field(description="Source archetype code")
    archetype_to: str = Field(description="Target archetype code")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score for the transition"
    )


class ClusteringStats(BaseModel):
    """Diagnostic statistics from a single HDBSCAN clustering run."""

    n_clusters: int = Field(ge=0, description="Number of clusters found (excl. noise)")
    n_noise_points: int = Field(ge=0, description="Number of noise points (-1 label)")
    silhouette_score: float = Field(description="Silhouette coefficient [-1, 1]")
    davies_bouldin_index: float = Field(
        ge=0.0, description="Davies–Bouldin index (lower is better)"
    )
    stability_ari_mean: float = Field(
        ge=0.0, le=1.0, description="Mean ARI across bootstrap runs"
    )
    stability_ari_std: float = Field(
        ge=0.0, description="Standard deviation of ARI across bootstrap runs"
    )


class SovereignAlert(BaseModel):
    """Alert generated for significant player archetype events."""

    alert_type: str = Field(
        description="One of: 'archetype_shift', 'emerging_player', 'decline'"
    )
    player_id: str = Field(description="Unique player identifier")
    archetype_code: str = Field(description="Relevant archetype code")
    message: str = Field(description="Human-readable alert message")
    severity: str = Field(description="One of: 'low', 'medium', 'high'")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when alert was generated",
    )
