"""Fair value estimation and arbitrage detection for auction players.

Implements a configurable valuation model that combines homology scores,
format multipliers, age factors, and market sentiment to produce
realistic fair value estimates.
"""

from __future__ import annotations

from sovereign.matching.models import ArbitrageError, ValuationError
from sovereign.matching.utils import (
    get_age_factor,
    get_format_multiplier,
    get_recommendation,
)


class ValuationModel:
    """Estimate fair market value and detect arbitrage opportunities.

    Base currency units (crores) per format are configurable at
    construction time and default to the settings values.

    Attributes:
        base_value_t20i: Base value in crores for T20I format.
        base_value_odi: Base value in crores for ODI format.
        base_value_test: Base value in crores for TEST format.
        market_sentiment: Global sentiment multiplier applied after all
            other factors.  Values > 1 indicate an inflated market.
    """

    def __init__(
        self,
        base_value_t20i: float = 50.0,
        base_value_odi: float = 25.0,
        base_value_test: float = 15.0,
        market_sentiment: float = 1.0,
    ) -> None:
        """Initialise the valuation model.

        Args:
            base_value_t20i: Base crore value for a T20I player.
            base_value_odi: Base crore value for an ODI player.
            base_value_test: Base crore value for a TEST player.
            market_sentiment: Historical bid sentiment multiplier.
        """
        self.base_value_t20i = base_value_t20i
        self.base_value_odi = base_value_odi
        self.base_value_test = base_value_test
        self.market_sentiment = market_sentiment

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def estimate_fair_value(
        self,
        player_id: str,
        homology_score: float,
        player_features: dict,
        archetype_info: dict,
        auction_context: dict,
    ) -> float:
        """Estimate a player's fair auction value in crores.

        Formula::

            fair_value = homology_score
                         × base_value
                         × format_tier_multiplier
                         × age_factor
                         × market_sentiment

        where ``base_value`` is looked up from ``auction_context["format_type"]``.

        Args:
            player_id: Unique player identifier (used in error messages).
            homology_score: Cosine similarity score in [0, 1].
            player_features: Dict of player metadata.  Expected key:
                ``"age"`` (int, defaults to 28 if absent).
            archetype_info: Dict with optional archetype metadata.
                Currently unused but reserved for future weighting.
            auction_context: Dict with required key ``"format_type"``
                (str: "T20I", "ODI", or "TEST").  Optional key:
                ``"market_sentiment"`` (float) to override the instance
                default.

        Returns:
            Estimated fair value in crores (≥ 0).

        Raises:
            ValuationError: If required keys are missing or values invalid.
        """
        try:
            format_type: str = auction_context["format_type"]
        except KeyError as exc:
            raise ValuationError(
                player_id, "auction_context must contain 'format_type'"
            ) from exc

        if not 0.0 <= homology_score <= 1.0:
            raise ValuationError(
                player_id,
                f"homology_score must be in [0, 1], got {homology_score}",
            )

        # Base value per format (in crores, e.g. 50 = ₹50L)
        base_value = self._base_value(format_type, player_id)
        fmt_multiplier = get_format_multiplier(format_type)

        age: int = int(player_features.get("age", 28))
        age_mult = get_age_factor(age)

        sentiment = float(
            auction_context.get("market_sentiment", self.market_sentiment)
        )

        fair_value = (
            homology_score * base_value * fmt_multiplier * age_mult * sentiment
        )
        return max(0.0, fair_value)

    def compute_arbitrage(
        self,
        fair_value: float,
        market_price: float,
    ) -> dict[str, float]:
        """Compute arbitrage gap and recommendation.

        Args:
            fair_value: Estimated fair value in crores.
            market_price: Current bid / market estimate in crores.

        Returns:
            Dict with keys:
            - ``"arbitrage_gap"``: fair_value − market_price
            - ``"arbitrage_pct"``: gap / market_price × 100
            - ``"recommendation"``: one of "BID", "WAIT", "NEUTRAL", "AVOID"

        Raises:
            ArbitrageError: If market_price is zero or negative.
        """
        if market_price <= 0.0:
            raise ArbitrageError(
                f"market_price must be positive, got {market_price}"
            )
        if fair_value < 0.0:
            raise ArbitrageError(
                f"fair_value must be non-negative, got {fair_value}"
            )

        gap = fair_value - market_price
        pct = (gap / market_price) * 100.0
        recommendation = get_recommendation(pct)

        return {
            "arbitrage_gap": gap,
            "arbitrage_pct": pct,
            "recommendation": recommendation,
        }

    # ------------------------------------------------------------------ #
    # Private helpers                                                       #
    # ------------------------------------------------------------------ #

    def _base_value(self, format_type: str, player_id: str) -> float:
        """Return the base crore value for the given format.

        Args:
            format_type: "T20I", "ODI", or "TEST".
            player_id: Used in error messages only.

        Returns:
            Base value in crores.

        Raises:
            ValuationError: If format_type is not recognised.
        """
        upper = format_type.upper()
        mapping: dict[str, float] = {
            "T20I": self.base_value_t20i,
            "ODI": self.base_value_odi,
            "TEST": self.base_value_test,
        }
        if upper not in mapping:
            raise ValuationError(
                player_id,
                f"Unknown format_type '{format_type}'. Expected T20I, ODI, or TEST.",
            )
        return mapping[upper]
