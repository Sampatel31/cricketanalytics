"""Pressure Response Features (12 features).

Behavioural interpretation
--------------------------
High-pressure deliveries (SPI ≥ 8) separate elite players from average ones.
A player whose SR *increases* under extreme pressure is a rare "pressure
accumulator".  Dot-ball % and boundary % at each tier capture risk appetite
and composure.

SPI tier boundaries
-------------------
- low     : SPI ∈ [0, 3)
- medium  : SPI ∈ [3, 6)
- high    : SPI ∈ [6, 8)
- extreme : SPI ∈ [8, 10]

Features returned (12)
----------------------
sr_spi_low, sr_spi_medium, sr_spi_high, sr_spi_extreme
dot_pct_spi_low, dot_pct_spi_medium, dot_pct_spi_high, dot_pct_spi_extreme
boundary_pct_spi_low, boundary_pct_spi_medium, boundary_pct_spi_high,
boundary_pct_spi_extreme

Bonus metric (not a separate feature, but logged)
-------------------------------------------------
clutch_delta = sr_spi_extreme - sr_spi_low
"""

from __future__ import annotations

import logging
from typing import Optional

import polars as pl

from sovereign.features.utils import (
    compute_boundary_pct,
    compute_dot_pct,
    compute_sr,
)

logger = logging.getLogger(__name__)

# SPI tier definitions: (tier_name, low_inclusive, high_exclusive)
# The last tier uses high_inclusive = 10.
_TIERS: list[tuple[str, float, float]] = [
    ("low", 0.0, 3.0),
    ("medium", 3.0, 6.0),
    ("high", 6.0, 8.0),
    ("extreme", 8.0, 10.001),  # 10.001 so that spi == 10 is included
]

_MIN_DELIVERIES = 10  # minimum per tier for reliable estimates


class PressureResponseFeatures:
    """Compute 12 pressure-response features for a single batter.

    Usage::

        prf = PressureResponseFeatures(min_deliveries=10)
        result = prf.compute("player_123", df)

    The returned dict has exactly 12 keys (one per feature).  A feature value
    is ``None`` when fewer than *min_deliveries* legal deliveries exist for
    that SPI tier.
    """

    def __init__(self, min_deliveries: int = _MIN_DELIVERIES) -> None:
        """Initialise with the minimum-deliveries-per-tier threshold.

        Args:
            min_deliveries: Number of legal deliveries required per SPI tier
                before a metric is computed.  Tiers with fewer deliveries
                return ``None`` to avoid unreliable small-sample estimates.
        """
        self.min_deliveries = min_deliveries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        player_id: str,
        deliveries_df: pl.DataFrame,
    ) -> dict[str, Optional[float]]:
        """Compute 12 pressure-response features for *player_id*.

        Args:
            player_id: Player identifier used only for logging.
            deliveries_df: Polars DataFrame with at least the following columns:

                - ``spi_total``     (float): Sovereign Pressure Index [0, 10]
                - ``runs_batter``   (int):   Runs scored by the batter
                - ``is_legal_ball`` (bool):  True for legal deliveries
                - ``wicket``        (bool):  True if the delivery took a wicket

                An optional ``is_boundary`` (bool) column is used when present;
                otherwise boundaries are inferred as ``runs_batter >= 4``.

        Returns:
            Dictionary with 12 keys → ``float | None``.  A ``None`` value
            means insufficient deliveries were available for that tier/metric.
        """
        required_cols = {"spi_total", "runs_batter", "is_legal_ball"}
        missing = required_cols - set(deliveries_df.columns)
        if missing:
            logger.warning(
                "PressureResponseFeatures: missing columns %s for player %s",
                missing,
                player_id,
            )
            return self._null_result()

        # Ensure boundary column is present
        if "is_boundary" not in deliveries_df.columns:
            deliveries_df = deliveries_df.with_columns(
                (pl.col("runs_batter") >= 4).alias("is_boundary")
            )

        result: dict[str, Optional[float]] = {}

        for tier_name, spi_low, spi_high in _TIERS:
            tier_df = (
                deliveries_df.lazy()
                .filter(
                    pl.col("spi_total").is_not_null()
                    & (pl.col("spi_total") >= spi_low)
                    & (pl.col("spi_total") < spi_high)
                    & pl.col("is_legal_ball")
                )
                .collect()
            )

            n = len(tier_df)
            if n < self.min_deliveries:
                result[f"sr_spi_{tier_name}"] = None
                result[f"dot_pct_spi_{tier_name}"] = None
                result[f"boundary_pct_spi_{tier_name}"] = None
                continue

            runs = float(tier_df["runs_batter"].sum())
            legal = float(n)
            dots = float((tier_df["runs_batter"] == 0).sum())
            boundaries = float(tier_df["is_boundary"].sum())

            result[f"sr_spi_{tier_name}"] = compute_sr(runs, legal)
            result[f"dot_pct_spi_{tier_name}"] = compute_dot_pct(dots, legal)
            result[f"boundary_pct_spi_{tier_name}"] = compute_boundary_pct(
                boundaries, legal
            )

        # Bonus: log clutch_delta (not a standalone feature, embedded in
        # the FeatureVector as the ``clutch_delta`` tactical field)
        sr_low = result.get("sr_spi_low")
        sr_ext = result.get("sr_spi_extreme")
        if sr_low is not None and sr_ext is not None:
            logger.debug(
                "Player %s clutch_delta=%.1f", player_id, sr_ext - sr_low
            )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _null_result(self) -> dict[str, None]:
        """Return a dict with all 12 keys set to ``None``."""
        keys = []
        for tier_name, _, _ in _TIERS:
            keys += [
                f"sr_spi_{tier_name}",
                f"dot_pct_spi_{tier_name}",
                f"boundary_pct_spi_{tier_name}",
            ]
        return {k: None for k in keys}
