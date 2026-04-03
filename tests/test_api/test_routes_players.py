"""Tests for GET /api/v1/players endpoints (4 tests)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestPlayerList:
    """GET /api/v1/players"""

    def test_list_players_default(self, client: TestClient) -> None:
        """Default list returns all players with correct schema."""
        resp = client.get("/api/v1/players")
        assert resp.status_code == 200
        data = resp.json()
        assert "players" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert data["offset"] == 0
        assert len(data["players"]) <= data["limit"]

    def test_list_players_format_filter(self, client: TestClient) -> None:
        """Format filter returns only matching players."""
        resp = client.get("/api/v1/players?format=T20I")
        assert resp.status_code == 200
        data = resp.json()
        for p in data["players"]:
            assert "player_id" in p

    def test_list_players_pagination(self, client: TestClient) -> None:
        """Limit and offset are respected."""
        resp = client.get("/api/v1/players?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["players"]) <= 1
        assert data["limit"] == 1
        assert data["offset"] == 0


class TestPlayerCard:
    """GET /api/v1/players/{player_id}"""

    def test_get_existing_player(self, client: TestClient) -> None:
        """Existing player returns full card."""
        resp = client.get("/api/v1/players/p001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["player_id"] == "p001"
        assert "features" in data
        assert "archetype_code" in data

    def test_get_nonexistent_player(self, client: TestClient) -> None:
        """Unknown player returns 404."""
        resp = client.get("/api/v1/players/nonexistent")
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "INVALID_PLAYER"


class TestPressureCurve:
    """GET /api/v1/players/{player_id}/pressure-curve"""

    def test_pressure_curve_existing_player(self, client: TestClient) -> None:
        """Returns SPI tier data for known player."""
        resp = client.get("/api/v1/players/p001/pressure-curve")
        assert resp.status_code == 200
        data = resp.json()
        assert data["player_id"] == "p001"
        assert "spi_tiers" in data
        assert len(data["spi_tiers"]) == 4


class TestPlayerSearch:
    """GET /api/v1/players/search"""

    def test_search_by_name(self, client: TestClient) -> None:
        """Name search returns matching results."""
        resp = client.get("/api/v1/players/search?q=kohli")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert any("Kohli" in r["player_name"] for r in data["results"])

    def test_search_no_match(self, client: TestClient) -> None:
        """Search with no match returns empty results."""
        resp = client.get("/api/v1/players/search?q=xyznonexistent")
        assert resp.status_code == 200
        assert resp.json()["results"] == []
