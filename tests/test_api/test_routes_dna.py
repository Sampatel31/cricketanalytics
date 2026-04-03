"""Tests for DNA builder endpoints (5 tests)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from sovereign.api.dependencies import _dna_store, _session_store
from sovereign.api.main import app


@pytest.fixture(autouse=True)
def clear_stores() -> None:
    _dna_store.clear()
    _session_store.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestDNASlider:
    """POST /api/v1/dna/slider"""

    def test_build_slider_dna(self, client: TestClient) -> None:
        """Slider DNA is built and returned with correct structure."""
        resp = client.post(
            "/api/v1/dna/slider",
            json={
                "franchise_name": "Chennai Super Kings",
                "feature_weights": {"sr_spi_low": 80.0, "sr_spi_medium": 60.0},
                "target_archetypes": ["ARC_001"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "dna_id" in data
        assert data["franchise_name"] == "Chennai Super Kings"
        assert data["mode"] == "slider"
        assert "feature_vector" in data


class TestDNAExemplar:
    """POST /api/v1/dna/exemplar"""

    def test_build_exemplar_dna(self, client: TestClient) -> None:
        """Exemplar DNA is built from player IDs."""
        resp = client.post(
            "/api/v1/dna/exemplar",
            json={
                "franchise_name": "Royal Challengers Bangalore",
                "player_ids": ["p001", "p002"],
                "target_archetypes": [],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "exemplar"
        assert "feature_vector" in data


class TestDNAHistorical:
    """POST /api/v1/dna/historical"""

    def test_build_historical_dna(self, client: TestClient) -> None:
        """Historical DNA is built from past pick player IDs."""
        resp = client.post(
            "/api/v1/dna/historical",
            json={
                "franchise_name": "Kolkata Knight Riders",
                "player_ids": ["p001", "p002", "p003"],
                "target_archetypes": ["ARC_002"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "historical"


class TestGetDNA:
    """GET /api/v1/dna/{dna_id}"""

    def test_get_existing_dna(self, client: TestClient) -> None:
        """Retrieve a previously created DNA profile."""
        build_resp = client.post(
            "/api/v1/dna/slider",
            json={"franchise_name": "MI", "feature_weights": {"sr_spi_low": 50.0}, "target_archetypes": []},
        )
        dna_id = build_resp.json()["dna_id"]

        resp = client.get(f"/api/v1/dna/{dna_id}")
        assert resp.status_code == 200
        assert resp.json()["dna_id"] == dna_id

    def test_get_nonexistent_dna(self, client: TestClient) -> None:
        """Unknown DNA ID returns 404."""
        resp = client.get("/api/v1/dna/nonexistent-id")
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "INVALID_DNA"


class TestScorePlayers:
    """POST /api/v1/dna/{dna_id}/score"""

    def test_score_players_against_dna(self, client: TestClient) -> None:
        """Players are scored against a DNA profile."""
        build_resp = client.post(
            "/api/v1/dna/slider",
            json={"franchise_name": "MI", "feature_weights": {"sr_spi_low": 80.0}, "target_archetypes": []},
        )
        dna_id = build_resp.json()["dna_id"]

        resp = client.post(
            f"/api/v1/dna/{dna_id}/score",
            json={"player_ids": ["p001", "p002"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dna_id"] == dna_id
        assert len(data["scores"]) == 2
        for score in data["scores"]:
            assert "homology" in score
            assert 0.0 <= score["homology"] <= 1.0
