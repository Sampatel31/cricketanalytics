"""Pydantic models for the feature engineering layer.

This module defines the type-safe data models that represent the 54-dimensional
behavioral fingerprint computed for each player, plus supporting containers for
logging, error handling, and metadata.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class FeatureComputationError(Exception):
    """Raised when a feature module fails to compute a value for a player.

    Attributes:
        player_id: The player whose features could not be computed.
        feature_group: The feature group that raised the error.
        reason: Human-readable explanation.
    """

    def __init__(
        self,
        player_id: str,
        feature_group: str,
        reason: str,
    ) -> None:
        self.player_id = player_id
        self.feature_group = feature_group
        self.reason = reason
        super().__init__(
            f"[{feature_group}] Failed to compute features for player "
            f"'{player_id}': {reason}"
        )


class InsufficientDataError(FeatureComputationError):
    """Raised when there are not enough deliveries/innings for a reliable feature.

    Attributes:
        required: Minimum sample size required.
        actual: Actual sample size available.
    """

    def __init__(
        self,
        player_id: str,
        feature_group: str,
        required: int,
        actual: int,
    ) -> None:
        self.required = required
        self.actual = actual
        super().__init__(
            player_id=player_id,
            feature_group=feature_group,
            reason=f"Need {required} samples, got {actual}",
        )


# ---------------------------------------------------------------------------
# FeatureVector — the 54-dimensional fingerprint
# ---------------------------------------------------------------------------


class FeatureVector(BaseModel):
    """54-dimensional behavioral fingerprint for a single player.

    Fields are grouped into five blocks that mirror the feature modules:
    - **Pressure Response** (12): SR / dot% / boundary% per SPI tier
    - **Phase Performance** (12): Phase-split batting and bowling metrics
    - **Tactical** (15): Behavioral patterns and decision-making
    - **Stability** (9): Form trajectory and career consistency
    - **Opposition Quality** (6): Context-adjusted metrics

    All fields are ``float`` and are bounded by their stated ``[min, max]``
    range validators.  Use ``None`` only before the vector is fully populated;
    the builder replaces every ``None`` with the column mean before output.
    """

    # -- Pressure Response (1–12) ------------------------------------------
    sr_spi_low: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="Strike rate when SPI ∈ [0, 3)"
    )
    sr_spi_medium: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="Strike rate when SPI ∈ [3, 6)"
    )
    sr_spi_high: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="Strike rate when SPI ∈ [6, 8)"
    )
    sr_spi_extreme: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="Strike rate when SPI ∈ [8, 10]"
    )
    dot_pct_spi_low: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Dot ball % when SPI ∈ [0, 3)"
    )
    dot_pct_spi_medium: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Dot ball % when SPI ∈ [3, 6)"
    )
    dot_pct_spi_high: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Dot ball % when SPI ∈ [6, 8)"
    )
    dot_pct_spi_extreme: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Dot ball % when SPI ∈ [8, 10]"
    )
    boundary_pct_spi_low: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Boundary % when SPI ∈ [0, 3)"
    )
    boundary_pct_spi_medium: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Boundary % when SPI ∈ [3, 6)"
    )
    boundary_pct_spi_high: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Boundary % when SPI ∈ [6, 8)"
    )
    boundary_pct_spi_extreme: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Boundary % when SPI ∈ [8, 10]"
    )

    # -- Phase Performance (13–24) -----------------------------------------
    sr_powerplay: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="Strike rate in powerplay overs"
    )
    sr_middle: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="Strike rate in middle overs"
    )
    sr_death: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="Strike rate in death overs"
    )
    dot_pct_powerplay: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Dot ball % in powerplay overs"
    )
    dot_pct_middle: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Dot ball % in middle overs"
    )
    dot_pct_death: Optional[float] = Field(
        default=None, ge=0.0, le=100.0,
        description="Dot ball % in death overs"
    )
    economy_powerplay: Optional[float] = Field(
        default=None, ge=0.0, le=50.0,
        description="Economy rate in powerplay overs"
    )
    economy_middle: Optional[float] = Field(
        default=None, ge=0.0, le=50.0,
        description="Economy rate in middle overs"
    )
    economy_death: Optional[float] = Field(
        default=None, ge=0.0, le=50.0,
        description="Economy rate in death overs"
    )
    wicket_prob_powerplay: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="P(wicket) per delivery in powerplay"
    )
    wicket_prob_middle: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="P(wicket) per delivery in middle overs"
    )
    wicket_prob_death: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="P(wicket) per delivery in death overs"
    )

    # -- Tactical (25–39) --------------------------------------------------
    clutch_delta: Optional[float] = Field(
        default=None, ge=-200.0, le=200.0,
        description="SR in death overs minus SR in powerplay"
    )
    recovery_rate: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Ability to score after dot balls (rolling avg proxy)"
    )
    running_score_avg: Optional[float] = Field(
        default=None, ge=-5.0, le=50.0,
        description="Average runs per 5-ball window"
    )
    partnership_acceleration: Optional[float] = Field(
        default=None, ge=-50.0, le=50.0,
        description="Scoring rate change as partnership matures"
    )
    cold_start_sr: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="Strike rate in first 10 balls of innings"
    )
    pace_vs_spin_delta: Optional[float] = Field(
        default=None, ge=-100.0, le=100.0,
        description="SR vs pace minus SR vs spin"
    )
    home_away_delta: Optional[float] = Field(
        default=None, ge=-100.0, le=100.0,
        description="SR at home minus SR away"
    )
    innings_type_delta: Optional[float] = Field(
        default=None, ge=-100.0, le=100.0,
        description="SR when chasing minus SR when defending"
    )
    consistency_index: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Inverse coefficient of variation (1 = very consistent)"
    )
    momentum_riding_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Correlation of performance with recent form"
    )
    momentum_reset_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Ability to bounce back after a poor streak"
    )
    aggression_escalation: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Rate of SR increase within a single innings"
    )
    boundary_dependency: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Fraction of runs coming from boundaries"
    )
    dot_ball_anxiety: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Degree of aggression surge after consecutive dots"
    )
    big_match_index: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Performance in high-SPI moments relative to average"
    )

    # -- Stability (40–48) -------------------------------------------------
    hmm_form_regime: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="HMM-derived form stability score"
    )
    archetype_consistency: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Consistency of archetype assignment across seasons"
    )
    sample_confidence_weight: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Confidence weight based on innings count"
    )
    age_trajectory: Optional[float] = Field(
        default=None, ge=-1.0, le=1.0,
        description="Career trajectory (−1=rising, 0=peak, +1=declining)"
    )
    format_adaptability_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Consistency of performance across T20/ODI/Test"
    )
    big_match_performance_idx: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Performance in high-stakes tournament stages"
    )
    debut_vs_current_delta: Optional[float] = Field(
        default=None, ge=-100.0, le=100.0,
        description="SR now minus SR at debut"
    )
    career_peak_proximity: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Proximity to career peak SR (1.0 = at peak)"
    )
    injury_absence_shift: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Performance change after gaps > 6 months"
    )

    # -- Opposition Quality (49–54) ----------------------------------------
    sr_vs_top10_attacks: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="SR against top-10 ranked bowling attacks"
    )
    sr_vs_bottom10_attacks: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="SR against bottom-10 ranked bowling attacks"
    )
    quality_adjusted_avg: Optional[float] = Field(
        default=None, ge=0.0, le=200.0,
        description="Batting average weighted by opposition bowling ELO"
    )
    quality_adjusted_economy: Optional[float] = Field(
        default=None, ge=0.0, le=50.0,
        description="Economy rate weighted by opposition batting ELO"
    )
    upset_performance_index: Optional[float] = Field(
        default=None, ge=0.0, le=1.0,
        description="Frequency of strong performances vs stronger opposition"
    )
    high_elo_match_sr: Optional[float] = Field(
        default=None, ge=0.0, le=400.0,
        description="SR in matches vs high-ELO (>1600) teams"
    )

    def to_feature_list(self) -> list[Optional[float]]:
        """Return all 54 feature values in canonical field order."""
        return list(self.model_dump().values())

    def feature_names(self) -> list[str]:
        """Return the canonical list of 54 feature field names."""
        return list(self.model_fields.keys())


# ---------------------------------------------------------------------------
# PlayerFeatures — container with metadata
# ---------------------------------------------------------------------------


class PlayerFeatures(BaseModel):
    """Feature record for a single player, format, and season.

    Attributes:
        player_id: Unique player identifier (matches the registry).
        format_type: Cricket format (T20I, ODI, TEST).
        season: Season identifier, e.g. ``"2024"``.
        features: The 54-dimensional feature vector.
        confidence_weight: Reliability weight in [0, 1].  Scales from
            ``~0.1`` at 5 innings up to ``1.0`` at 30+ innings.
        innings_count: Total innings for this player × format × season.
        matches_count: Total matches played.
        last_updated: Timestamp when features were last computed.
    """

    player_id: str = Field(description="Unique player identifier")
    format_type: str = Field(description="Cricket format: T20I, ODI, or TEST")
    season: str = Field(description="Season identifier, e.g. '2024'")
    features: FeatureVector = Field(
        default_factory=FeatureVector,
        description="54-dimensional feature vector",
    )
    confidence_weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Reliability weight based on innings count",
    )
    innings_count: int = Field(
        default=0, ge=0, description="Total innings played"
    )
    matches_count: int = Field(
        default=0, ge=0, description="Total matches played"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of last feature computation",
    )

    @model_validator(mode="after")
    def validate_confidence_weight(self) -> "PlayerFeatures":
        """Confidence weight must be consistent with innings_count."""
        # Allow callers to set confidence_weight explicitly; the builder
        # calls ``compute_confidence_weight`` to set the correct value.
        return self


def compute_confidence_weight(
    innings_count: int,
    min_innings: int = 5,
    full_innings: int = 30,
) -> float:
    """Linearly scale confidence from 0.1 at *min_innings* to 1.0 at *full_innings*.

    Args:
        innings_count: Number of innings played.
        min_innings: Minimum innings required (below this → 0.1).
        full_innings: Innings count at which confidence reaches 1.0.

    Returns:
        Confidence weight in [0.1, 1.0].
    """
    if innings_count <= min_innings:
        return 0.1
    if innings_count >= full_innings:
        return 1.0
    slope = (1.0 - 0.1) / (full_innings - min_innings)
    return 0.1 + slope * (innings_count - min_innings)


# ---------------------------------------------------------------------------
# FeatureStats — for logging / quality checks
# ---------------------------------------------------------------------------


class FeatureStats(BaseModel):
    """Per-feature descriptive statistics for logging and QC.

    Attributes:
        feature_name: The name of the feature (e.g. ``sr_spi_low``).
        mean: Population mean across all players.
        std: Population standard deviation.
        min: Minimum observed value.
        max: Maximum observed value.
        null_count: Number of players with ``None`` (before imputation).
        invalid_count: Number of out-of-range values found.
    """

    feature_name: str
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    null_count: int = 0
    invalid_count: int = 0
