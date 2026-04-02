"""Pydantic models for the matching engine layer.

Defines type-safe data models for franchise DNA, player scores,
valuations, squad state, and alert objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class DNABuildError(Exception):
    """Raised when franchise DNA cannot be built from provided inputs.

    Attributes:
        reason: Human-readable explanation of the failure.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"DNA build error: {reason}")


class ValuationError(Exception):
    """Raised when fair value estimation fails.

    Attributes:
        player_id: The player whose value could not be estimated.
        reason: Human-readable explanation.
    """

    def __init__(self, player_id: str, reason: str) -> None:
        self.player_id = player_id
        self.reason = reason
        super().__init__(f"Valuation error for player '{player_id}': {reason}")


class ArbitrageError(Exception):
    """Raised when arbitrage computation fails due to invalid inputs.

    Attributes:
        reason: Human-readable explanation.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Arbitrage error: {reason}")


# ---------------------------------------------------------------------------
# FranchiseDNA
# ---------------------------------------------------------------------------


class FranchiseDNA(BaseModel):
    """Franchise behavioral DNA vector.

    Represents the ideal player archetype profile a franchise is
    targeting in an auction.  Built in one of three modes:
    ``slider``, ``exemplar``, or ``historical``.

    Attributes:
        dna_id: UUID string uniquely identifying this DNA profile.
        franchise_name: Name of the franchise (e.g. "Mumbai Indians").
        dna_mode: Build mode — "slider", "exemplar", or "historical".
        feature_vector: Dict mapping each of the 54 feature names to
            its normalized value.
        target_archetypes: Optional list of archetype codes the franchise
            prefers (e.g. ["ARC_001", "ARC_003"]).
        created_at: UTC timestamp when the DNA was created.
        description: Mode-specific explanation of how the DNA was built.
    """

    dna_id: str = Field(description="UUID identifying this DNA profile")
    franchise_name: str = Field(description="Name of the franchise")
    dna_mode: str = Field(description="Build mode: slider, exemplar, or historical")
    feature_vector: dict[str, float] = Field(
        description="54-dimensional normalized feature vector"
    )
    target_archetypes: list[str] = Field(
        default_factory=list,
        description="Preferred archetype codes (e.g. ARC_001)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of DNA creation",
    )
    description: str = Field(
        default="",
        description="Mode-specific explanation of how the DNA was built",
    )


# ---------------------------------------------------------------------------
# PlayerScore
# ---------------------------------------------------------------------------


class PlayerScore(BaseModel):
    """Homology-based score for a single player against franchise DNA.

    Attributes:
        player_id: Unique player identifier.
        player_name: Human-readable player name.
        archetype_code: Player's assigned archetype (e.g. "ARC_002").
        archetype_label: Human-readable archetype label.
        homology_score: Cosine similarity to franchise DNA vector in [0, 1].
        archetype_bonus: Bonus applied when archetype matches a target in [0, 0.05].
        confidence_weight: Reliability weight from feature engineering in [0, 1].
        fair_value: Estimated fair market value in crores.
        market_price: Current bid estimate in crores.
        arbitrage_gap: fair_value − market_price (can be negative).
        arbitrage_pct: (arbitrage_gap / market_price) × 100.
        recommendation: One of "BID", "WAIT", "NEUTRAL", or "AVOID".
    """

    player_id: str = Field(description="Unique player identifier")
    player_name: str = Field(description="Human-readable player name")
    archetype_code: str = Field(description="Player's archetype code")
    archetype_label: str = Field(description="Human-readable archetype label")
    homology_score: float = Field(
        ge=0.0, le=1.0, description="Cosine similarity to franchise DNA"
    )
    archetype_bonus: float = Field(
        ge=0.0, le=0.05, description="Bonus for matching a target archetype"
    )
    confidence_weight: float = Field(
        ge=0.0, le=1.0, description="Feature reliability weight"
    )
    fair_value: float = Field(ge=0.0, description="Estimated fair value in crores")
    market_price: float = Field(ge=0.0, description="Current market price in crores")
    arbitrage_gap: float = Field(description="fair_value − market_price")
    arbitrage_pct: float = Field(
        description="(arbitrage_gap / market_price) × 100"
    )
    recommendation: str = Field(
        description="One of: BID, WAIT, NEUTRAL, AVOID"
    )


# ---------------------------------------------------------------------------
# SquadState
# ---------------------------------------------------------------------------


class SquadState(BaseModel):
    """Real-time state of a franchise's squad during an auction.

    Attributes:
        squad_id: UUID identifying this squad snapshot.
        franchise_name: Name of the franchise.
        players_locked_in: List of player_ids confirmed into the squad.
        budget_total: Total available budget in crores.
        budget_spent: Amount spent so far in crores.
        archetype_balance: Maps archetype_code → count of players locked in.
        squad_dna_score: Average homology score of all confirmed picks.
        last_updated: UTC timestamp of last update.
        upcoming_lot_player_id: Optional player_id for the next auction lot.
    """

    squad_id: str = Field(description="UUID identifying this squad snapshot")
    franchise_name: str = Field(description="Name of the franchise")
    players_locked_in: list[str] = Field(
        default_factory=list, description="Player IDs confirmed in the squad"
    )
    budget_total: float = Field(ge=0.0, description="Total budget in crores")
    budget_spent: float = Field(
        ge=0.0, description="Budget spent so far in crores"
    )
    archetype_balance: dict[str, int] = Field(
        default_factory=dict, description="Archetype code → player count"
    )
    squad_dna_score: float = Field(
        ge=0.0, le=1.0, description="Average homology score of confirmed picks"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last update",
    )
    upcoming_lot_player_id: Optional[str] = Field(
        default=None, description="Player ID of the next auction lot"
    )


# ---------------------------------------------------------------------------
# OverbidAlert
# ---------------------------------------------------------------------------


class OverbidAlert(BaseModel):
    """Alert generated when a bid exceeds the fair value ceiling.

    Attributes:
        player_id: Player being bid on.
        current_bid: Current bid in crores.
        max_bid_ceiling: Maximum recommended bid (fair_value × overbid_threshold).
        overpay_amount: current_bid − max_bid_ceiling.
        overpay_pct: (overpay_amount / max_bid_ceiling) × 100.
        alternatives: List of dicts describing cheaper same-archetype alternatives.
        severity: "warning" if overpay_pct < 30, else "critical".
    """

    player_id: str = Field(description="Player being bid on")
    current_bid: float = Field(ge=0.0, description="Current bid in crores")
    max_bid_ceiling: float = Field(
        ge=0.0, description="Maximum recommended bid in crores"
    )
    overpay_amount: float = Field(description="current_bid − max_bid_ceiling")
    overpay_pct: float = Field(
        description="(overpay_amount / max_bid_ceiling) × 100"
    )
    alternatives: list[dict] = Field(
        default_factory=list,
        description="Cheaper same-archetype alternatives from future lots",
    )
    severity: str = Field(description="One of: warning, critical")


# ---------------------------------------------------------------------------
# ArchetypeGapAlert
# ---------------------------------------------------------------------------


class ArchetypeGapAlert(BaseModel):
    """Alert triggered when a target archetype is underrepresented in the squad.

    Attributes:
        archetype_code: Affected archetype code.
        archetype_label: Human-readable label for the archetype.
        target_count: Desired number of players of this archetype.
        current_count: Current number of players of this archetype.
        auction_progress_pct: Fraction of auction lots already processed (0–1).
        message: Human-readable explanation of the gap.
    """

    archetype_code: str = Field(description="Affected archetype code")
    archetype_label: str = Field(description="Human-readable archetype label")
    target_count: int = Field(ge=0, description="Target player count")
    current_count: int = Field(ge=0, description="Current player count")
    auction_progress_pct: float = Field(
        ge=0.0, le=1.0, description="Fraction of auction completed"
    )
    message: str = Field(description="Human-readable gap description")
