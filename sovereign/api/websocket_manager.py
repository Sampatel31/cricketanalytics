"""WebSocket connection pool manager for auction sessions."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manage multiple WebSocket connections per auction session.

    Supports broadcasting to all clients in a session and sending
    targeted messages to individual clients.  All operations are
    protected by a per-session asyncio lock for thread safety.
    """

    def __init__(self) -> None:
        # session_id → {client_id: WebSocket}
        self._connections: dict[str, dict[str, WebSocket]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def connect(self, session_id: str, websocket: WebSocket) -> str:
        """Accept a WebSocket connection and register it.

        Args:
            session_id: Auction session identifier.
            websocket: The connected WebSocket instance.

        Returns:
            A unique client ID assigned to this connection.
        """
        await websocket.accept()
        client_id = str(uuid.uuid4())
        async with self._get_lock(session_id):
            if session_id not in self._connections:
                self._connections[session_id] = {}
            self._connections[session_id][client_id] = websocket
        logger.info(
            "websocket_connected",
            session_id=session_id,
            client_id=client_id,
            total=len(self._connections[session_id]),
        )
        return client_id

    async def disconnect(self, session_id: str, client_id: str) -> None:
        """Remove a client connection from the session pool.

        Args:
            session_id: Auction session identifier.
            client_id: Client identifier returned by :meth:`connect`.
        """
        async with self._get_lock(session_id):
            session_conns = self._connections.get(session_id, {})
            session_conns.pop(client_id, None)
            if not session_conns:
                self._connections.pop(session_id, None)
                self._locks.pop(session_id, None)
        logger.info(
            "websocket_disconnected",
            session_id=session_id,
            client_id=client_id,
        )

    async def broadcast(self, session_id: str, message: dict[str, Any]) -> None:
        """Send *message* to every client in the session.

        Connections that fail to receive the message are silently removed.

        Args:
            session_id: Auction session identifier.
            message: JSON-serialisable message dict.
        """
        async with self._get_lock(session_id):
            session_conns = dict(self._connections.get(session_id, {}))

        dead_clients: list[str] = []
        for client_id, ws in session_conns.items():
            try:
                await ws.send_json(message)
            except Exception as exc:
                dead_clients.append(client_id)
                logger.warning(
                    "websocket_send_failed",
                    session_id=session_id,
                    client_id=client_id,
                    exc_type=type(exc).__name__,
                    exc_msg=str(exc),
                )

        for client_id in dead_clients:
            await self.disconnect(session_id, client_id)

    async def send_personal(
        self, session_id: str, client_id: str, message: dict[str, Any]
    ) -> None:
        """Send *message* to a single client.

        Args:
            session_id: Auction session identifier.
            client_id: Target client identifier.
            message: JSON-serialisable message dict.
        """
        async with self._get_lock(session_id):
            ws = self._connections.get(session_id, {}).get(client_id)

        if ws is None:
            logger.warning(
                "websocket_client_not_found",
                session_id=session_id,
                client_id=client_id,
            )
            return

        try:
            await ws.send_json(message)
        except Exception as exc:
            logger.warning(
                "websocket_personal_send_failed",
                session_id=session_id,
                client_id=client_id,
                exc_type=type(exc).__name__,
                exc_msg=str(exc),
            )
            await self.disconnect(session_id, client_id)

    def active_connections(self, session_id: str) -> int:
        """Return the number of active connections for a session."""
        return len(self._connections.get(session_id, {}))

    def total_connections(self) -> int:
        """Return the total number of active connections across all sessions."""
        return sum(len(v) for v in self._connections.values())


# Module-level singleton
manager = ConnectionManager()
