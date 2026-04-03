"""Tests for auction session endpoints (6 tests)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def dna_id(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/dna/slider",
        json={"franchise_name": "MI", "feature_weights": {"sr_spi_low": 80.0}, "target_archetypes": []},
    )
    return resp.json()["dna_id"]


@pytest.fixture
def session_id(client: TestClient, dna_id: str) -> str:
    resp = client.post(
        "/api/v1/auction/session",
        json={"franchise_name": "Mumbai Indians", "budget_crores": 100.0, "dna_id": dna_id, "format_type": "T20I"},
    )
    return resp.json()["session_id"]


class TestCreateSession:
    """POST /api/v1/auction/session"""

    def test_create_session_success(self, client: TestClient, dna_id: str) -> None:
        """Session is created and returned with correct fields."""
        resp = client.post(
            "/api/v1/auction/session",
            json={"franchise_name": "Mumbai Indians", "budget_crores": 100.0, "dna_id": dna_id, "format_type": "T20I"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["franchise_name"] == "Mumbai Indians"
        assert data["budget_total"] == 100.0
        assert data["budget_spent"] == 0.0

    def test_create_session_invalid_dna(self, client: TestClient) -> None:
        """Invalid DNA ID returns 404."""
        resp = client.post(
            "/api/v1/auction/session",
            json={"franchise_name": "MI", "budget_crores": 100.0, "dna_id": "bad-dna-id", "format_type": "T20I"},
        )
        assert resp.status_code == 404


class TestGetSession:
    """GET /api/v1/auction/session/{session_id}"""

    def test_get_session_state(self, client: TestClient, session_id: str) -> None:
        """Session state is returned with correct structure."""
        resp = client.get(f"/api/v1/auction/session/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert "budget_remaining" in data

    def test_get_nonexistent_session(self, client: TestClient) -> None:
        """Unknown session ID returns 404."""
        resp = client.get("/api/v1/auction/session/nonexistent")
        assert resp.status_code == 404


class TestConfirmPick:
    """POST /api/v1/auction/session/{session_id}/pick"""

    def test_pick_within_budget(self, client: TestClient, session_id: str) -> None:
        """Picking within budget succeeds and updates state."""
        resp = client.post(
            f"/api/v1/auction/session/{session_id}/pick",
            json={"player_id": "p001", "price_paid": 20.0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["budget_remaining"] == pytest.approx(80.0)
        assert data["squad_size"] == 1

    def test_pick_exceeds_budget(self, client: TestClient, session_id: str) -> None:
        """Picking beyond budget returns 422."""
        resp = client.post(
            f"/api/v1/auction/session/{session_id}/pick",
            json={"player_id": "p001", "price_paid": 200.0},
        )
        assert resp.status_code == 422
        assert resp.json()["error_code"] == "BUDGET_EXCEEDED"


class TestAuctionScores:
    """GET /api/v1/auction/{session_id}/scores"""

    def test_get_scores_for_lots(self, client: TestClient, session_id: str) -> None:
        """Scores are returned for upcoming lots."""
        resp = client.get(
            f"/api/v1/auction/{session_id}/scores?upcoming_lots=p001,p002"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert len(data["scores"]) == 2


class TestAuctionReport:
    """GET /api/v1/auction/{session_id}/report"""

    def test_get_report(self, client: TestClient, session_id: str) -> None:
        """Post-auction report is returned."""
        resp = client.get(f"/api/v1/auction/{session_id}/report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == session_id
        assert "budget_utilization" in data
        assert "archetype_coverage" in data
