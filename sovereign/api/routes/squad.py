"""Squad management endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends

from sovereign.api.dependencies import get_session_store
from sovereign.api.errors import SessionNotFoundError
from sovereign.api.schemas import (
    OverbidCheckRequest,
    OverbidCheckResponse,
    SquadBudgetResponse,
    SquadCompositionResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/squad", tags=["squad"])


@router.get(
    "/{session_id}/composition",
    response_model=SquadCompositionResponse,
    summary="Squad archetype breakdown",
)
async def squad_composition(
    session_id: str,
    session_store: dict = Depends(get_session_store),
) -> SquadCompositionResponse:
    """Return the current archetype breakdown of the squad."""
    state = session_store.get(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)

    balance = state.get("archetype_balance", {})
    return SquadCompositionResponse(
        session_id=session_id,
        archetype_balance=balance,
        gaps=[],
    )


@router.get(
    "/{session_id}/budget",
    response_model=SquadBudgetResponse,
    summary="Budget status",
)
async def squad_budget(
    session_id: str,
    session_store: dict = Depends(get_session_store),
) -> SquadBudgetResponse:
    """Return current budget status for the squad."""
    state = session_store.get(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)

    budget_total = state["budget_total"]
    budget_spent = state["budget_spent"]
    n_players = len(state.get("players_locked_in", []))
    per_player = budget_spent / n_players if n_players > 0 else 0.0

    return SquadBudgetResponse(
        session_id=session_id,
        budget_total=budget_total,
        budget_spent=budget_spent,
        budget_remaining=budget_total - budget_spent,
        per_player_avg=round(per_player, 2),
    )


@router.post(
    "/{session_id}/check-overbid",
    response_model=OverbidCheckResponse,
    summary="Check if a bid is overbid",
)
async def check_overbid(
    session_id: str,
    body: OverbidCheckRequest,
    session_store: dict = Depends(get_session_store),
) -> OverbidCheckResponse:
    """Check whether the current bid exceeds the player's fair value ceiling."""
    state = session_store.get(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)

    # Stub: fair value ceiling is 1.2× market estimate of 50 Cr
    max_ceiling = 50.0 * 1.2
    is_overbid = body.current_bid > max_ceiling

    return OverbidCheckResponse(
        is_overbid=is_overbid,
        player_id=body.player_id,
        current_bid=body.current_bid,
        max_ceiling=max_ceiling,
        alternatives=[],
    )
