"""Tests for WebSocket live auction endpoints (4 tests)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def session_id(client: TestClient) -> str:
    """Create a DNA + session and return session_id."""
    dna_resp = client.post(
        "/api/v1/dna/slider",
        json={"franchise_name": "MI", "feature_weights": {"sr_spi_low": 80.0}, "target_archetypes": []},
    )
    dna_id = dna_resp.json()["dna_id"]
    sess_resp = client.post(
        "/api/v1/auction/session",
        json={"franchise_name": "Mumbai Indians", "budget_crores": 100.0, "dna_id": dna_id, "format_type": "T20I"},
    )
    return sess_resp.json()["session_id"]


class TestWebSocketConnect:
    """WebSocket /ws/{session_id} - connect and disconnect."""

    def test_connect_disconnect(self, client: TestClient, session_id: str) -> None:
        """Client connects and receives a ``connected`` message."""
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connected"
            assert msg["session_id"] == session_id

    def test_connect_unknown_session(self, client: TestClient) -> None:
        """Client connecting to unknown session still gets connected message."""
        with client.websocket_connect("/ws/unknown-session-id") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "connected"


class TestWebSocketMessages:
    """WebSocket message routing."""

    def test_lot_called_broadcasts_player_card(
        self, client: TestClient, session_id: str
    ) -> None:
        """Sending lot_called results in a player_card broadcast."""
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            ws.receive_json()  # consume "connected"
            ws.send_json({"type": "lot_called", "player_id": "p001"})
            msg = ws.receive_json()
            assert msg["type"] == "player_card"
            assert msg["player"]["player_id"] == "p001"

    def test_invalid_json_returns_error(
        self, client: TestClient, session_id: str
    ) -> None:
        """Invalid JSON payload returns connection_error."""
        with client.websocket_connect(f"/ws/{session_id}") as ws:
            ws.receive_json()  # consume "connected"
            ws.send_text("not valid json{{{")
            msg = ws.receive_json()
            assert msg["type"] == "connection_error"
