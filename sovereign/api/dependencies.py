"""FastAPI dependency injection utilities."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import Depends

from sovereign.api.errors import SessionNotFoundError

logger = structlog.get_logger(__name__)

# In-memory session store (replaces Redis for now; can swap later)
_session_store: dict[str, dict[str, Any]] = {}
# In-memory DNA store
_dna_store: dict[str, dict[str, Any]] = {}


def get_session_store() -> dict[str, dict[str, Any]]:
    """Return the in-memory session store.

    In production this would return a Redis connection/wrapper.
    """
    return _session_store


def get_dna_store() -> dict[str, dict[str, Any]]:
    """Return the in-memory DNA store."""
    return _dna_store


async def get_session_state(
    session_id: str,
    store: dict[str, dict[str, Any]] = Depends(get_session_store),
) -> dict[str, Any]:
    """Load and return the auction session state.

    Args:
        session_id: Auction session identifier.
        store: Injected session store.

    Returns:
        Session state dict.

    Raises:
        SessionNotFoundError: If the session does not exist.
    """
    state = store.get(session_id)
    if state is None:
        raise SessionNotFoundError(session_id)
    return state


async def verify_session_exists(
    session_id: str,
    store: dict[str, dict[str, Any]] = Depends(get_session_store),
) -> str:
    """Validate that a session exists and return its ID.

    Raises:
        SessionNotFoundError: If the session does not exist.
    """
    if session_id not in store:
        raise SessionNotFoundError(session_id)
    return session_id
