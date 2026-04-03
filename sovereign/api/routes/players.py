"""Player information endpoints."""

from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, Query

from sovereign.api.schemas import (
    PlayerCardResponse,
    PlayerListResponse,
    PlayerSearchResponse,
    PlayerSearchResult,
    PlayerSummary,
    PressureCurveResponse,
    PressureTierEntry,
)
from sovereign.features.models import FeatureVector

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/players", tags=["players"])

# Stub player registry (populated from DB in production)
_PLAYERS: list[dict] = [
    {
        "player_id": "p001",
        "player_name": "Rohit Sharma",
        "archetype_code": "ARC_001",
        "archetype_label": "Aggressive Opener",
        "confidence_weight": 1.0,
        "innings_count": 45,
        "age": 36,
        "format_type": "T20I",
        "season": "2024",
    },
    {
        "player_id": "p002",
        "player_name": "Virat Kohli",
        "archetype_code": "ARC_002",
        "archetype_label": "Anchor Batter",
        "confidence_weight": 0.95,
        "innings_count": 38,
        "age": 35,
        "format_type": "T20I",
        "season": "2024",
    },
    {
        "player_id": "p003",
        "player_name": "Suryakumar Yadav",
        "archetype_code": "ARC_001",
        "archetype_label": "Aggressive Opener",
        "confidence_weight": 0.92,
        "innings_count": 35,
        "age": 33,
        "format_type": "T20I",
        "season": "2024",
    },
]

_FEATURE_NAMES = list(FeatureVector.model_fields.keys())


def _stub_features() -> dict[str, float]:
    """Return zeroed feature dict for stub responses."""
    return {name: 0.0 for name in _FEATURE_NAMES}


@router.get("", response_model=PlayerListResponse, summary="List players")
async def list_players(
    format: Optional[str] = Query(None, description="Filter by format (T20I/ODI/TEST)"),
    season: Optional[str] = Query(None, description="Filter by season (e.g. 2024)"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    archetype: Optional[str] = Query(None, description="Filter by archetype code"),
) -> PlayerListResponse:
    """Return a paginated list of players with basic info."""
    players = list(_PLAYERS)
    if format:
        players = [p for p in players if p.get("format_type") == format]
    if season:
        players = [p for p in players if p.get("season") == season]
    if archetype:
        players = [p for p in players if p.get("archetype_code") == archetype]

    total = len(players)
    page = players[offset : offset + limit]
    return PlayerListResponse(
        players=[
            PlayerSummary(
                player_id=p["player_id"],
                player_name=p["player_name"],
                archetype_code=p.get("archetype_code", ""),
                archetype_label=p.get("archetype_label", ""),
                confidence_weight=p.get("confidence_weight", 0.0),
            )
            for p in page
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/search", response_model=PlayerSearchResponse, summary="Search players")
async def search_players(
    q: str = Query(..., description="Search query (player name)"),
) -> PlayerSearchResponse:
    """Fuzzy search for players by name."""
    q_lower = q.lower()
    results = []
    for p in _PLAYERS:
        name_lower = p["player_name"].lower()
        if q_lower in name_lower:
            # Similarity: ratio of matched characters relative to longer string,
            # clamped to [0, 1] to avoid scores exceeding 1.
            score = min(len(q_lower) / max(len(name_lower), 1), 1.0)
            results.append(
                PlayerSearchResult(
                    player_id=p["player_id"],
                    player_name=p["player_name"],
                    similarity_score=round(score, 3),
                )
            )
    results.sort(key=lambda r: r.similarity_score, reverse=True)
    return PlayerSearchResponse(results=results)


@router.get(
    "/{player_id}",
    response_model=PlayerCardResponse,
    summary="Get full player card",
)
async def get_player(player_id: str) -> PlayerCardResponse:
    """Return the full player profile including all 54 features."""
    from sovereign.api.errors import InvalidPlayerError

    player = next((p for p in _PLAYERS if p["player_id"] == player_id), None)
    if player is None:
        raise InvalidPlayerError(player_id)

    return PlayerCardResponse(
        player_id=player["player_id"],
        player_name=player["player_name"],
        age=player.get("age"),
        format_type=player.get("format_type", ""),
        season=player.get("season", ""),
        features=_stub_features(),
        archetype_code=player.get("archetype_code", ""),
        archetype_label=player.get("archetype_label", ""),
        confidence_weight=player.get("confidence_weight", 0.0),
        innings_count=player.get("innings_count", 0),
    )


@router.get(
    "/{player_id}/pressure-curve",
    response_model=PressureCurveResponse,
    summary="Player pressure curve",
)
async def get_pressure_curve(player_id: str) -> PressureCurveResponse:
    """Return strike-rate profile across SPI tiers for visualization."""
    from sovereign.api.errors import InvalidPlayerError

    player = next((p for p in _PLAYERS if p["player_id"] == player_id), None)
    if player is None:
        raise InvalidPlayerError(player_id)

    tiers = [
        PressureTierEntry(tier="low", sr=135.0, dot_pct=25.0, boundary_pct=45.0, sample_size=50),
        PressureTierEntry(tier="medium", sr=128.0, dot_pct=30.0, boundary_pct=42.0, sample_size=40),
        PressureTierEntry(tier="high", sr=120.0, dot_pct=35.0, boundary_pct=38.0, sample_size=30),
        PressureTierEntry(tier="extreme", sr=145.0, dot_pct=20.0, boundary_pct=55.0, sample_size=15),
    ]
    return PressureCurveResponse(player_id=player_id, spi_tiers=tiers)
