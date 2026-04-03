"""Fixtures for API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from sovereign.api.dependencies import _dna_store, _session_store
from sovereign.api.main import app


@pytest.fixture(autouse=True)
def clear_stores() -> None:
    """Clear in-memory stores before each test."""
    _dna_store.clear()
    _session_store.clear()


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
async def async_client():
    """Async HTTP client for async tests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def dna_id(client: TestClient) -> str:
    """Build a slider DNA and return its ID."""
    resp = client.post(
        "/api/v1/dna/slider",
        json={
            "franchise_name": "Mumbai Indians",
            "feature_weights": {"sr_spi_low": 80.0, "sr_spi_medium": 60.0},
            "target_archetypes": ["ARC_001"],
        },
    )
    assert resp.status_code == 200
    return resp.json()["dna_id"]


@pytest.fixture
def session_id(client: TestClient, dna_id: str) -> str:
    """Create an auction session and return its ID."""
    resp = client.post(
        "/api/v1/auction/session",
        json={
            "franchise_name": "Mumbai Indians",
            "budget_crores": 100.0,
            "dna_id": dna_id,
            "format_type": "T20I",
        },
    )
    assert resp.status_code == 200
    return resp.json()["session_id"]
