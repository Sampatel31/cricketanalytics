"""Phase Performance Features (12 features).

Behavioural interpretation
--------------------------
Cricket is divided into three phases: powerplay (early, fielding restrictions),
middle overs (consolidation or acceleration), and death overs (maximise
scoring / take wickets).  A player's ability to shift gear across these phases
is a key differentiator.

Phase boundaries per format
---------------------------
- T20 / T20I : PP  = overs 1–6,   Middle = 7–15,  Death = 16–20
- ODI        : PP  = overs 1–10,  Middle = 11–40, Death = 41–50
- TEST       : PP  = overs 1–10,  Middle = 11–80, Death = 81–90
  (Test boundaries are approximate — powerplay rules differ but the logical
  split is useful for fingerprinting.)

Features returned (12)
----------------------
Batters  : sr_powerplay, sr_middle, sr_death
           dot_pct_powerplay, dot_pct_middle, dot_pct_death
Bowlers  : economy_powerplay, economy_middle, economy_death
           wicket_prob_powerplay, wicket_prob_middle, wicket_prob_death

For a batter the bowling metrics are set to ``None`` and vice-versa.  The
builder fills ``None`` values with the column mean before writing the
output matrix.
"""

from __future__ import annotations

import logging
from typing import Optional

import polars as pl

from sovereign.features.utils import (
    compute_dot_pct,
    compute_economy,
    compute_sr,
    safe_divide,
)

logger = logging.getLogger(__name__)

_MIN_DELIVERIES = 5  # minimum per phase for reliable estimates

# Phase boundaries: (pp_max, middle_max) — overs are 1-indexed (over_number)
_PHASE_BOUNDARIES: dict[str, tuple[int, int]] = {
    "T20I": (6, 15),
    "T20": (6, 15),
    "ODI": (10, 40),
    "TEST": (10, 80),
}
_DEFAULT_BOUNDARIES = (6, 15)  # fallback


def _get_boundaries(format_type: str) -> tuple[int, int]:
    """Return (pp_max, middle_max) for *format_type*."""
    return _PHASE_BOUNDARIES.get(format_type.upper(), _DEFAULT_BOUNDARIES)


def _phase_label(format_type: str, over_number: int) -> str:
    """Map *over_number* to ``'powerplay'``, ``'middle'``, or ``'death'``."""
    pp_max, mid_max = _get_boundaries(format_type)
    if over_number <= pp_max:
        return "powerplay"
    if over_number <= mid_max:
        return "middle"
    return "death"


class PhasePerformanceFeatures:
    """Compute 12 phase-performance features for a single player.

    Usage::

        ppf = PhasePerformanceFeatures(min_deliveries=5)
        result = ppf.compute("player_123", df, format_type="T20I", role="batter")

    The returned dict has exactly 12 keys.  Values are ``None`` when fewer
    than *min_deliveries* legal deliveries exist for that phase/role.
    """

    def __init__(self, min_deliveries: int = _MIN_DELIVERIES) -> None:
        """Initialise with the minimum-deliveries-per-phase threshold.

        Args:
            min_deliveries: Minimum legal deliveries required per phase.
        """
        self.min_deliveries = min_deliveries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        player_id: str,
        deliveries_df: pl.DataFrame,
        format_type: str = "T20I",
        role: str = "batter",
    ) -> dict[str, Optional[float]]:
        """Compute 12 phase-performance features.

        Args:
            player_id: Player identifier (used for logging only).
            deliveries_df: Polars DataFrame with columns:

                - ``over_number``   (int):   1-indexed over
                - ``runs_batter``   (int):   Batter runs on this delivery
                - ``runs_total``    (int):   Total runs on this delivery
                - ``is_legal_ball`` (bool):  True for legal deliveries
                - ``wicket``        (bool):  True when a wicket fell

            format_type: Cricket format string (``'T20I'``, ``'ODI'``,
                ``'TEST'``).  Controls phase boundaries.
            role: ``'batter'`` or ``'bowler'``.  Determines which metrics
                are computed (batting SR/dot vs bowling economy/wicket prob).

        Returns:
            Dictionary with 12 keys → ``float | None``.
        """
        required_cols = {"over_number", "runs_batter", "is_legal_ball"}
        if role == "bowler":
            required_cols |= {"runs_total", "wicket"}

        missing = required_cols - set(deliveries_df.columns)
        if missing:
            logger.warning(
                "PhasePerformanceFeatures: missing columns %s for player %s",
                missing,
                player_id,
            )
            return self._null_result()

        # Add wicket column default if missing (for batter role)
        if "wicket" not in deliveries_df.columns:
            deliveries_df = deliveries_df.with_columns(
                pl.lit(False).alias("wicket")
            )
        if "runs_total" not in deliveries_df.columns:
            deliveries_df = deliveries_df.with_columns(
                pl.col("runs_batter").alias("runs_total")
            )

        # Tag each delivery with its phase
        pp_max, mid_max = _get_boundaries(format_type)
        tagged = (
            deliveries_df.lazy()
            .with_columns(
                pl.when(pl.col("over_number") <= pp_max)
                .then(pl.lit("powerplay"))
                .when(pl.col("over_number") <= mid_max)
                .then(pl.lit("middle"))
                .otherwise(pl.lit("death"))
                .alias("phase")
            )
            .filter(pl.col("is_legal_ball"))
            .collect()
        )

        result: dict[str, Optional[float]] = {}

        for phase in ("powerplay", "middle", "death"):
            phase_df = tagged.filter(pl.col("phase") == phase)
            n = len(phase_df)

            if role == "batter":
                if n < self.min_deliveries:
                    result[f"sr_{phase}"] = None
                    result[f"dot_pct_{phase}"] = None
                else:
                    runs = float(phase_df["runs_batter"].sum())
                    legal = float(n)
                    dots = float((phase_df["runs_batter"] == 0).sum())
                    result[f"sr_{phase}"] = compute_sr(runs, legal)
                    result[f"dot_pct_{phase}"] = compute_dot_pct(dots, legal)

                # Bowler fields are None for batters
                result[f"economy_{phase}"] = None
                result[f"wicket_prob_{phase}"] = None

            else:  # bowler
                if n < self.min_deliveries:
                    result[f"economy_{phase}"] = None
                    result[f"wicket_prob_{phase}"] = None
                else:
                    runs_c = float(phase_df["runs_total"].sum())
                    legal = float(n)
                    wickets = float(phase_df["wicket"].sum())
                    result[f"economy_{phase}"] = compute_economy(runs_c, legal)
                    result[f"wicket_prob_{phase}"] = safe_divide(
                        wickets, legal, default=0.0
                    )

                # Batter fields are None for bowlers
                result[f"sr_{phase}"] = None
                result[f"dot_pct_{phase}"] = None

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _null_result(self) -> dict[str, None]:
        """Return a dict with all 12 keys set to ``None``."""
        keys: list[str] = []
        for phase in ("powerplay", "middle", "death"):
            keys += [
                f"sr_{phase}",
                f"dot_pct_{phase}",
                f"economy_{phase}",
                f"wicket_prob_{phase}",
            ]
        return {k: None for k in keys}
