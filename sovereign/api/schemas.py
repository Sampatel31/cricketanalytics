"""Pydantic request/response schemas for all API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Player schemas
# ---------------------------------------------------------------------------


class PlayerSummary(BaseModel):
    """Lightweight player summary returned in list endpoints."""

    player_id: str
    player_name: str
    archetype_code: str = ""
    archetype_label: str = ""
    confidence_weight: float = 0.0


class PlayerListResponse(BaseModel):
    """Paginated player list."""

    players: list[PlayerSummary]
    total: int
    limit: int
    offset: int


class PlayerCardResponse(BaseModel):
    """Full player profile including all 54 features."""

    player_id: str
    player_name: str
    age: Optional[int] = None
    format_type: str = ""
    season: str = ""
    features: dict[str, float] = Field(default_factory=dict)
    archetype_code: str = ""
    archetype_label: str = ""
    confidence_weight: float = 0.0
    innings_count: int = 0


class PressureTierEntry(BaseModel):
    """Strike-rate profile at a single SPI tier."""

    tier: str
    sr: float
    dot_pct: float
    boundary_pct: float
    sample_size: int = 0


class PressureCurveResponse(BaseModel):
    """Player pressure-curve data for visualization."""

    player_id: str
    spi_tiers: list[PressureTierEntry]


class PlayerSearchResult(BaseModel):
    """Single result from fuzzy player name search."""

    player_id: str
    player_name: str
    similarity_score: float


class PlayerSearchResponse(BaseModel):
    """Results of a fuzzy player name search."""

    results: list[PlayerSearchResult]


# ---------------------------------------------------------------------------
# DNA schemas
# ---------------------------------------------------------------------------


class DNASliderRequest(BaseModel):
    """Request body for POST /api/v1/dna/slider."""

    franchise_name: str = Field(..., description="Franchise name")
    feature_weights: dict[str, float] = Field(
        ..., description="Feature name → weight in [0, 100]"
    )
    target_archetypes: list[str] = Field(
        default_factory=list, description="Preferred archetype codes"
    )


class DNAExemplarRequest(BaseModel):
    """Request body for POST /api/v1/dna/exemplar."""

    franchise_name: str = Field(..., description="Franchise name")
    player_ids: list[str] = Field(..., description="Exemplar player IDs")
    target_archetypes: list[str] = Field(
        default_factory=list, description="Preferred archetype codes"
    )


class DNAHistoricalRequest(BaseModel):
    """Request body for POST /api/v1/dna/historical."""

    franchise_name: str = Field(..., description="Franchise name")
    player_ids: list[str] = Field(..., description="Historical pick player IDs")
    target_archetypes: list[str] = Field(
        default_factory=list, description="Preferred archetype codes"
    )


class DNAResponse(BaseModel):
    """DNA profile returned after creation or retrieval."""

    dna_id: str
    franchise_name: str
    mode: str
    description: str = ""
    feature_vector: dict[str, float]
    target_archetypes: list[str] = Field(default_factory=list)
    created_at: datetime


class DNAScoreRequest(BaseModel):
    """Request body for POST /api/v1/dna/{dna_id}/score."""

    player_ids: list[str] = Field(..., description="Player IDs to score")


class PlayerScoreEntry(BaseModel):
    """Per-player DNA score."""

    player_id: str
    homology: float
    archetype_bonus: float = 0.0
    confidence: float = 0.0
    recommendation: str = "NEUTRAL"


class DNAScoreResponse(BaseModel):
    """Scores of multiple players against a DNA profile."""

    dna_id: str
    scores: list[PlayerScoreEntry]


# ---------------------------------------------------------------------------
# Auction schemas
# ---------------------------------------------------------------------------


class AuctionSessionRequest(BaseModel):
    """Request body for POST /api/v1/auction/session."""

    franchise_name: str = Field(..., description="Franchise name")
    budget_crores: float = Field(..., gt=0, description="Total auction budget in crores")
    dna_id: str = Field(..., description="Franchise DNA profile ID")
    format_type: str = Field(..., description="Cricket format: T20I, ODI, or TEST")


class AuctionSessionResponse(BaseModel):
    """Auction session created/retrieved."""

    session_id: str
    franchise_name: str
    budget_total: float
    budget_spent: float = 0.0
    budget_remaining: float
    dna_id: str
    format_type: str
    players_locked_in: list[str] = Field(default_factory=list)
    archetype_balance: dict[str, int] = Field(default_factory=dict)
    squad_dna_score: float = 0.0
    created_at: datetime
    last_updated: datetime


class PickConfirmRequest(BaseModel):
    """Request body for POST /api/v1/auction/session/{session_id}/pick."""

    player_id: str = Field(..., description="Player ID to lock in")
    price_paid: float = Field(..., gt=0, description="Price paid in crores")


class PickConfirmResponse(BaseModel):
    """Result of confirming an auction pick."""

    success: bool
    session_id: str
    player_id: str
    price_paid: float
    budget_remaining: float
    squad_size: int
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class PlayerScoresRequest(BaseModel):
    """Request body / query for upcoming lots scoring."""

    upcoming_lots: list[str] = Field(..., description="Player IDs for upcoming lots")


class AuctionPlayerScore(BaseModel):
    """Score for a single player in the auction context."""

    player_id: str
    homology: float
    fair_value: float
    market_price: float
    arbitrage_gap: float
    recommendation: str


class AuctionScoresResponse(BaseModel):
    """Scores for all upcoming lots."""

    session_id: str
    scores: list[AuctionPlayerScore]


class AuctionReportResponse(BaseModel):
    """Post-auction full report."""

    session_id: str
    franchise_name: str
    final_squad: list[dict[str, Any]]
    budget_utilization: dict[str, float]
    archetype_coverage: dict[str, int]
    value_analysis: dict[str, Any]


# ---------------------------------------------------------------------------
# Squad schemas
# ---------------------------------------------------------------------------


class SquadCompositionResponse(BaseModel):
    """Squad archetype breakdown."""

    session_id: str
    archetype_balance: dict[str, int]
    gaps: list[str] = Field(default_factory=list)


class SquadBudgetResponse(BaseModel):
    """Budget status for a squad."""

    session_id: str
    budget_total: float
    budget_spent: float
    budget_remaining: float
    per_player_avg: float


class OverbidCheckRequest(BaseModel):
    """Request body for POST /api/v1/squad/{session_id}/check-overbid."""

    player_id: str
    current_bid: float = Field(..., gt=0)


class OverbidCheckResponse(BaseModel):
    """Result of an overbid check."""

    is_overbid: bool
    player_id: str
    current_bid: float
    max_ceiling: float
    alternatives: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Health schemas
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Service health check response."""

    status: str
    timestamp: datetime
    db: str = "unknown"
    redis: str = "unknown"
    version: str = "1.0"


class MetricsResponse(BaseModel):
    """Basic service metrics."""

    requests_total: int = 0
    errors_total: int = 0
    uptime_seconds: float = 0.0
    active_sessions: int = 0
    active_ws_connections: int = 0


# ---------------------------------------------------------------------------
# WebSocket message schemas
# ---------------------------------------------------------------------------


class WSMessageBase(BaseModel):
    """Base WebSocket message with a type discriminator."""

    type: str


class WSConnectMessage(WSMessageBase):
    """Client → Server: Initial connection."""

    type: Literal["connect"] = "connect"
    session_id: str


class WSLotCalledMessage(WSMessageBase):
    """Client → Server: A lot is being called."""

    type: Literal["lot_called"] = "lot_called"
    player_id: str


class WSBidUpdateMessage(WSMessageBase):
    """Client → Server: Bid amount updated."""

    type: Literal["bid_update"] = "bid_update"
    current_bid: float


class WSPickConfirmedMessage(WSMessageBase):
    """Client → Server: Pick confirmed."""

    type: Literal["pick_confirmed"] = "pick_confirmed"
    player_id: str
    price: float


class WSDisconnectMessage(WSMessageBase):
    """Client → Server: Graceful disconnect."""

    type: Literal["disconnect"] = "disconnect"


class WSPlayerCardMessage(WSMessageBase):
    """Server → Client: Full player card push."""

    type: Literal["player_card"] = "player_card"
    player: dict[str, Any]
    fair_value: float = 0.0
    recommendation: str = "NEUTRAL"


class WSOverbidAlertMessage(WSMessageBase):
    """Server → Client: Overbid alert."""

    type: Literal["overbid_alert"] = "overbid_alert"
    player_id: str
    current_bid: float
    max_bid: float


class WSSquadUpdateMessage(WSMessageBase):
    """Server → Client: Squad state update."""

    type: Literal["squad_update"] = "squad_update"
    squad_state: dict[str, Any]
    budget_remaining: float


class WSArchetypeGapAlertMessage(WSMessageBase):
    """Server → Client: Archetype gap alert."""

    type: Literal["archetype_gap_alert"] = "archetype_gap_alert"
    gap_archetypes: list[str]


class WSConnectionErrorMessage(WSMessageBase):
    """Server → Client: Connection error."""

    type: Literal["connection_error"] = "connection_error"
    message: str


class WSConnectedMessage(WSMessageBase):
    """Server → Client: Successful connection acknowledgement."""

    type: Literal["connected"] = "connected"
    session_id: str
    franchise_name: str = ""
    budget: float = 0.0


# ---------------------------------------------------------------------------
# Error response schema
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error_code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
