"""Auction session management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends

from sovereign.api.dependencies import get_dna_store, get_session_store
from sovereign.api.errors import (
    BudgetExceededError,
    InvalidDNAError,
    SessionNotFoundError,
)
from sovereign.api.schemas import (
    AuctionPlayerScore,
    AuctionReportResponse,
    AuctionScoresResponse,
    AuctionSessionRequest,
    AuctionSessionResponse,
    PickConfirmRequest,
    PickConfirmResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/auction", tags=["auction"])


def _session_to_response(sid: str, state: dict[str, Any]) -> AuctionSessionResponse:
    budget_total = state["budget_total"]
    budget_spent = state["budget_spent"]
    return AuctionSessionResponse(
        session_id=sid,
        franchise_name=state["franchise_name"],
        budget_total=budget_total,
        budget_spent=budget_spent,
        budget_remaining=budget_total - budget_spent,
        dna_id=state["dna_id"],
        format_type=state["format_type"],
        players_locked_in=state.get("players_locked_in", []),
        archetype_balance=state.get("archetype_balance", {}),
        squad_dna_score=state.get("squad_dna_score", 0.0),
        created_at=state["created_at"],
        last_updated=state["last_updated"],
    )


@router.post("/session", response_model=AuctionSessionResponse, summary="Create auction session")
async def create_session(
    body: AuctionSessionRequest,
    session_store: dict = Depends(get_session_store),
    dna_store: dict = Depends(get_dna_store),
) -> AuctionSessionResponse:
    """Create a new auction session."""
    if body.dna_id not in dna_store:
        raise InvalidDNAError(body.dna_id)

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    state: dict[str, Any] = {
        "franchise_name": body.franchise_name,
        "budget_total": body.budget_crores,
        "budget_spent": 0.0,
        "dna_id": body.dna_id,
        "format_type": body.format_type,
        "players_locked_in": [],
        "archetype_balance": {},
        "squad_dna_score": 0.0,
        "created_at": now,
        "last_updated": now,
    }
    session_store[session_id] = state
    logger.info("auction_session_created", session_id=session_id, franchise=body.franchise_name)
    return _session_to_response(session_id, state)


@router.get(
    "/session/{session_id}",
    response_model=AuctionSessionResponse,
    summary="Get auction session state",
)
async def get_session(
    session_id: str,
    session_store: dict = Depends(get_session_store),
) -> AuctionSessionResponse:
    """Return the current state of an auction session."""
    state = session_store.get(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)
    return _session_to_response(session_id, state)


@router.post(
    "/session/{session_id}/pick",
    response_model=PickConfirmResponse,
    summary="Confirm a player pick",
)
async def confirm_pick(
    session_id: str,
    body: PickConfirmRequest,
    session_store: dict = Depends(get_session_store),
) -> PickConfirmResponse:
    """Lock a player into the squad and update the session budget."""
    state = session_store.get(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)

    budget_remaining = state["budget_total"] - state["budget_spent"]
    if body.price_paid > budget_remaining:
        raise BudgetExceededError(body.price_paid, budget_remaining)

    state["budget_spent"] += body.price_paid
    state["players_locked_in"].append(body.player_id)
    state["last_updated"] = datetime.now(timezone.utc)

    return PickConfirmResponse(
        success=True,
        session_id=session_id,
        player_id=body.player_id,
        price_paid=body.price_paid,
        budget_remaining=state["budget_total"] - state["budget_spent"],
        squad_size=len(state["players_locked_in"]),
        alerts=[],
    )


@router.get(
    "/{session_id}/scores",
    response_model=AuctionScoresResponse,
    summary="Get scores for upcoming lots",
)
async def get_scores(
    session_id: str,
    upcoming_lots: str = "",
    session_store: dict = Depends(get_session_store),
    dna_store: dict = Depends(get_dna_store),
) -> AuctionScoresResponse:
    """Return DNA-homology scores for upcoming auction lots."""
    state = session_store.get(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)

    player_ids = [p.strip() for p in upcoming_lots.split(",") if p.strip()]
    scores = [
        AuctionPlayerScore(
            player_id=pid,
            homology=0.75,
            fair_value=50.0,
            market_price=45.0,
            arbitrage_gap=5.0,
            recommendation="BID",
        )
        for pid in player_ids
    ]
    return AuctionScoresResponse(session_id=session_id, scores=scores)


@router.get(
    "/{session_id}/report",
    response_model=AuctionReportResponse,
    summary="Post-auction full report",
)
async def get_report(
    session_id: str,
    session_store: dict = Depends(get_session_store),
) -> AuctionReportResponse:
    """Return a comprehensive post-auction report."""
    state = session_store.get(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)

    budget_total = state["budget_total"]
    budget_spent = state["budget_spent"]
    return AuctionReportResponse(
        session_id=session_id,
        franchise_name=state["franchise_name"],
        final_squad=[{"player_id": p} for p in state["players_locked_in"]],
        budget_utilization={
            "total": budget_total,
            "spent": budget_spent,
            "remaining": budget_total - budget_spent,
            "utilization_pct": round(budget_spent / budget_total * 100, 1) if budget_total else 0.0,
        },
        archetype_coverage=state.get("archetype_balance", {}),
        value_analysis={"squad_dna_score": state.get("squad_dna_score", 0.0)},
    )
