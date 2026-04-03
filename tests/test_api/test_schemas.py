"""Tests for Pydantic request/response schema validation (2 tests)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sovereign.api.schemas import (
    AuctionSessionRequest,
    DNASliderRequest,
    ErrorResponse,
    OverbidCheckRequest,
    PickConfirmRequest,
)


class TestRequestValidation:
    """Request schema validation tests."""

    def test_auction_session_request_valid(self) -> None:
        """Valid auction session request passes validation."""
        req = AuctionSessionRequest(
            franchise_name="Mumbai Indians",
            budget_crores=100.0,
            dna_id="some-uuid",
            format_type="T20I",
        )
        assert req.budget_crores == 100.0
        assert req.format_type == "T20I"

    def test_auction_session_request_negative_budget(self) -> None:
        """Negative budget fails Pydantic validation."""
        with pytest.raises(ValidationError):
            AuctionSessionRequest(
                franchise_name="MI",
                budget_crores=-10.0,
                dna_id="some-uuid",
                format_type="T20I",
            )

    def test_pick_confirm_request_zero_price(self) -> None:
        """Zero price fails Pydantic validation (must be > 0)."""
        with pytest.raises(ValidationError):
            PickConfirmRequest(player_id="p001", price_paid=0.0)

    def test_dna_slider_request_valid(self) -> None:
        """DNA slider request accepts any feature weight dict."""
        req = DNASliderRequest(
            franchise_name="CSK",
            feature_weights={"sr_spi_low": 80.0},
            target_archetypes=["ARC_001"],
        )
        assert req.franchise_name == "CSK"
        assert req.feature_weights["sr_spi_low"] == 80.0


class TestResponseSerialization:
    """Response schema serialization tests."""

    def test_error_response_serialization(self) -> None:
        """ErrorResponse serializes to expected JSON shape."""
        err = ErrorResponse(
            error_code="SESSION_NOT_FOUND",
            message="Session not found.",
            details={"session_id": "abc"},
        )
        d = err.model_dump()
        assert d["error_code"] == "SESSION_NOT_FOUND"
        assert d["details"]["session_id"] == "abc"

    def test_overbid_check_request_zero_bid(self) -> None:
        """Zero bid fails validation."""
        with pytest.raises(ValidationError):
            OverbidCheckRequest(player_id="p001", current_bid=0.0)
