"""Tests for sovereign/matching/valuation.py (4 tests)."""

from __future__ import annotations

import pytest

from sovereign.matching.models import ArbitrageError, ValuationError
from sovereign.matching.valuation import ValuationModel


@pytest.fixture
def model() -> ValuationModel:
    """ValuationModel with default config."""
    return ValuationModel(
        base_value_t20i=50.0,
        base_value_odi=25.0,
        base_value_test=15.0,
        market_sentiment=1.0,
    )


class TestFairValueEstimation:
    """Tests for ValuationModel.estimate_fair_value."""

    def test_t20i_young_player(self, model: ValuationModel) -> None:
        """T20I young player (age ≤ 28) should apply multiplier 1.0 × 1.2."""
        # homology=0.95, T20I: 0.95 × 50 × 1.2 × 1.0 × 1.0 = 57.0
        fv = model.estimate_fair_value(
            player_id="p001",
            homology_score=0.95,
            player_features={"age": 25},
            archetype_info={},
            auction_context={"format_type": "T20I"},
        )
        assert fv == pytest.approx(0.95 * 50.0 * 1.2 * 1.0, rel=1e-6)

    def test_odi_veteran_player(self, model: ValuationModel) -> None:
        """ODI veteran (age > 32) should apply multiplier 0.85."""
        # homology=0.70, ODI: 0.70 × 25 × 0.9 × 0.85 = 13.3875
        fv = model.estimate_fair_value(
            player_id="p002",
            homology_score=0.70,
            player_features={"age": 35},
            archetype_info={},
            auction_context={"format_type": "ODI"},
        )
        assert fv == pytest.approx(0.70 * 25.0 * 0.9 * 0.85, rel=1e-6)

    def test_missing_format_raises(self, model: ValuationModel) -> None:
        """Missing format_type key in auction_context should raise ValuationError."""
        with pytest.raises(ValuationError, match="format_type"):
            model.estimate_fair_value(
                player_id="p003",
                homology_score=0.8,
                player_features={"age": 28},
                archetype_info={},
                auction_context={},
            )

    def test_invalid_homology_raises(self, model: ValuationModel) -> None:
        """homology_score outside [0, 1] should raise ValuationError."""
        with pytest.raises(ValuationError, match="homology_score"):
            model.estimate_fair_value(
                player_id="p004",
                homology_score=1.5,
                player_features={"age": 28},
                archetype_info={},
                auction_context={"format_type": "T20I"},
            )


class TestArbitrageGap:
    """Tests for ValuationModel.compute_arbitrage."""

    def test_arbitrage_gap_computed(self, model: ValuationModel) -> None:
        """Basic arbitrage gap and percentage computation."""
        result = model.compute_arbitrage(fair_value=60.0, market_price=50.0)
        assert result["arbitrage_gap"] == pytest.approx(10.0)
        assert result["arbitrage_pct"] == pytest.approx(20.0)

    def test_bid_recommendation_above_threshold(
        self, model: ValuationModel
    ) -> None:
        """When fair_value is > 20% above market_price, recommend BID."""
        result = model.compute_arbitrage(fair_value=65.0, market_price=50.0)
        assert result["recommendation"] == "BID"

    def test_avoid_recommendation_below_threshold(
        self, model: ValuationModel
    ) -> None:
        """When market_price exceeds fair_value by > 5%, recommend AVOID."""
        result = model.compute_arbitrage(fair_value=40.0, market_price=50.0)
        assert result["recommendation"] == "AVOID"
        assert result["arbitrage_gap"] == pytest.approx(-10.0)

    def test_zero_market_price_raises(self, model: ValuationModel) -> None:
        """Zero market_price must raise ArbitrageError."""
        with pytest.raises(ArbitrageError, match="market_price must be positive"):
            model.compute_arbitrage(fair_value=50.0, market_price=0.0)


class TestAgeFactor:
    """Verify age factor is applied correctly in fair value estimation."""

    @pytest.mark.parametrize("age,expected_factor", [
        (20, 1.0),
        (28, 1.0),
        (30, 0.95),
        (32, 0.95),
        (33, 0.85),
    ])
    def test_age_factor_applied(
        self, model: ValuationModel, age: int, expected_factor: float
    ) -> None:
        """Fair value should reflect the age factor for the given age."""
        fv = model.estimate_fair_value(
            player_id="px",
            homology_score=1.0,
            player_features={"age": age},
            archetype_info={},
            auction_context={"format_type": "T20I"},
        )
        # 1.0 × 50 × 1.2 × age_factor × 1.0
        expected = 50.0 * 1.2 * expected_factor
        assert fv == pytest.approx(expected, rel=1e-6)


class TestMarketSentiment:
    """Market sentiment multiplier is correctly incorporated."""

    def test_market_sentiment_incorporated(self) -> None:
        """A 1.5× sentiment multiplier should scale the fair value proportionally."""
        model_hot = ValuationModel(
            base_value_t20i=50.0,
            market_sentiment=1.5,
        )
        fv_hot = model_hot.estimate_fair_value(
            player_id="p1",
            homology_score=0.8,
            player_features={"age": 25},
            archetype_info={},
            auction_context={"format_type": "T20I"},
        )
        model_normal = ValuationModel(base_value_t20i=50.0, market_sentiment=1.0)
        fv_normal = model_normal.estimate_fair_value(
            player_id="p1",
            homology_score=0.8,
            player_features={"age": 25},
            archetype_info={},
            auction_context={"format_type": "T20I"},
        )
        assert fv_hot == pytest.approx(fv_normal * 1.5, rel=1e-6)
