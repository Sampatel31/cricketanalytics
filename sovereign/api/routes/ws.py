"""WebSocket handler for live auction sessions."""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from sovereign.api.dependencies import get_session_store
from sovereign.api.websocket_manager import manager

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
    """Handle WebSocket connections for a live auction session.

    Protocol:
    - Client connects; server sends ``connected`` message.
    - Client sends ``lot_called``, ``bid_update``, ``pick_confirmed``,
      or ``disconnect`` messages.
    - Server broadcasts ``player_card``, ``overbid_alert``,
      ``squad_update``, and ``archetype_gap_alert`` messages.
    """
    client_id = await manager.connect(session_id, websocket)
    session_store = get_session_store()
    state = session_store.get(session_id, {})

    try:
        await manager.send_personal(
            session_id,
            client_id,
            {
                "type": "connected",
                "session_id": session_id,
                "franchise_name": state.get("franchise_name", ""),
                "budget": state.get("budget_total", 0.0) - state.get("budget_spent", 0.0),
            },
        )

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_personal(
                    session_id,
                    client_id,
                    {"type": "connection_error", "message": "Invalid JSON payload."},
                )
                continue

            msg_type = msg.get("type", "")
            await _handle_message(session_id, client_id, msg_type, msg, state)

    except WebSocketDisconnect:
        await manager.disconnect(session_id, client_id)
        logger.info("websocket_client_disconnected", session_id=session_id, client_id=client_id)


async def _handle_message(
    session_id: str,
    client_id: str,
    msg_type: str,
    msg: dict[str, Any],
    state: dict[str, Any],
) -> None:
    """Route incoming WebSocket messages to appropriate handlers."""
    if msg_type == "lot_called":
        player_id = msg.get("player_id", "")
        await manager.broadcast(
            session_id,
            {
                "type": "player_card",
                "player": {"player_id": player_id, "player_name": player_id},
                "fair_value": 50.0,
                "recommendation": "NEUTRAL",
            },
        )

    elif msg_type == "bid_update":
        try:
            current_bid = float(msg.get("current_bid", 0))
        except (TypeError, ValueError):
            await manager.send_personal(
                session_id, client_id, {"type": "connection_error", "message": "Invalid current_bid value."}
            )
            return
        max_ceiling = 60.0  # stub
        if current_bid > max_ceiling:
            await manager.broadcast(
                session_id,
                {
                    "type": "overbid_alert",
                    "player_id": msg.get("player_id", ""),
                    "current_bid": current_bid,
                    "max_bid": max_ceiling,
                },
            )

    elif msg_type == "pick_confirmed":
        player_id = msg.get("player_id", "")
        try:
            price = float(msg.get("price", 0))
        except (TypeError, ValueError):
            await manager.send_personal(
                session_id, client_id, {"type": "connection_error", "message": "Invalid price value."}
            )
            return
        budget_remaining = (
            state.get("budget_total", 0.0)
            - state.get("budget_spent", 0.0)
            - price
        )
        await manager.broadcast(
            session_id,
            {
                "type": "squad_update",
                "squad_state": {"players_locked_in": state.get("players_locked_in", [])},
                "budget_remaining": max(budget_remaining, 0.0),
            },
        )

    elif msg_type == "disconnect":
        await manager.disconnect(session_id, client_id)
