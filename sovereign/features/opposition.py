"""Opposition Quality Features (6 features).

Behavioural interpretation
--------------------------
Raw batting averages and strike rates don't account for the *strength* of the
bowling attack faced.  A batsman averaging 45 against weak attacks is less
impressive than 38 against top-ranked attacks.  These six features
context-adjust performance by opposition ELO / ranking tier.

ELO ranking system
------------------
Each team carries an ELO rating.  A rating above 1600 is "elite"; below 1400
is "weak".  Top-10 / bottom-10 attack labels are derived from the per-match
bowling attack ELO supplied in *match_info*.

Features returned (6)
---------------------
sr_vs_top10_attacks, sr_vs_bottom10_attacks, quality_adjusted_avg,
quality_adjusted_economy, upset_performance_index, high_elo_match_sr
"""

from __future__ import annotations

import logging
from typing import Optional

import polars as pl

from sovereign.features.utils import clamp, compute_sr, safe_divide

logger = logging.getLogger(__name__)

# ELO thresholds
_HIGH_ELO_THRESHOLD = 1600.0
_ELO_MIN = 1200.0
_ELO_MAX = 1800.0

# Percentile thresholds for top/bottom bucket assignment (fraction of matches)
_TOP_FRACTION = 0.3
_BOTTOM_FRACTION = 0.3

_MIN_DELIVERIES = 10  # per opposition bucket


class OppositionQualityFeatures:
    """Compute 6 opposition-quality-adjusted features for a single player.

    Usage::

        oqf = OppositionQualityFeatures()
        result = oqf.compute("player_123", deliveries_df, match_info)

    *match_info* is a list of dicts, one per match played by this player::

        {
            "match_id": "m001",
            "opposition_elo": 1550.0,   # float or None
            "player_runs": 45,          # total runs in that match
            "player_balls": 38,         # balls faced in that match
            "player_wickets": 3,        # wickets taken (for economy)
            "runs_conceded": 42,        # runs conceded (for economy)
            "balls_bowled": 24,         # balls bowled (for economy)
        }
    """

    def __init__(
        self,
        high_elo_threshold: float = _HIGH_ELO_THRESHOLD,
        min_deliveries: int = _MIN_DELIVERIES,
    ) -> None:
        self.high_elo_threshold = high_elo_threshold
        self.min_deliveries = min_deliveries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        player_id: str,
        deliveries_df: pl.DataFrame,
        match_info: list[dict],
    ) -> dict[str, Optional[float]]:
        """Compute 6 opposition quality features.

        Args:
            player_id: Player ID (logging only).
            deliveries_df: Delivery-level DataFrame.  Columns used:

                - ``match_id``      (str):   Match identifier
                - ``runs_batter``   (int):   Runs per delivery
                - ``is_legal_ball`` (bool):  True for legal deliveries
                - ``opposition_elo`` (float, optional): Team ELO

            match_info: List of per-match summary dicts (see class docstring).

        Returns:
            Dictionary with 6 keys → ``float | None``.
        """
        if not match_info:
            return self._null_result()

        # ------------------------------------------------------------------
        # Determine top/bottom attack labels from opposition ELO
        # ------------------------------------------------------------------
        elos = [
            m.get("opposition_elo")
            for m in match_info
            if m.get("opposition_elo") is not None
        ]
        if len(elos) < 2:
            top_threshold = self.high_elo_threshold
            bottom_threshold = self.high_elo_threshold - 200.0
        else:
            sorted_elos = sorted(elos)
            n = len(sorted_elos)
            top_idx = max(1, int(n * (1 - _TOP_FRACTION)))
            bottom_idx = max(0, int(n * _BOTTOM_FRACTION) - 1)
            top_threshold = float(sorted_elos[top_idx])
            bottom_threshold = float(sorted_elos[bottom_idx])

        # Build per-match ELO lookup
        match_elo: dict[str, Optional[float]] = {
            str(m["match_id"]): m.get("opposition_elo")
            for m in match_info
        }

        # Attach ELO to deliveries if not already present
        if "opposition_elo" not in deliveries_df.columns:
            if "match_id" in deliveries_df.columns:
                elo_df = pl.DataFrame(
                    {
                        "match_id": list(match_elo.keys()),
                        "opposition_elo": list(match_elo.values()),
                    }
                )
                deliveries_df = deliveries_df.join(
                    elo_df, on="match_id", how="left"
                )
            else:
                # Cannot attach ELO without match_id
                return self._null_result()

        legal = (
            deliveries_df.lazy()
            .filter(pl.col("is_legal_ball"))
            .collect()
            if "is_legal_ball" in deliveries_df.columns
            else deliveries_df
        )

        result: dict[str, Optional[float]] = {}

        # 1 & 2. SR vs top-10 / bottom-10 attacks
        top_df = legal.filter(
            pl.col("opposition_elo").is_not_null()
            & (pl.col("opposition_elo") >= top_threshold)
        )
        bottom_df = legal.filter(
            pl.col("opposition_elo").is_not_null()
            & (pl.col("opposition_elo") <= bottom_threshold)
        )

        result["sr_vs_top10_attacks"] = (
            compute_sr(
                float(top_df["runs_batter"].sum()), float(len(top_df))
            )
            if len(top_df) >= self.min_deliveries
            else None
        )
        result["sr_vs_bottom10_attacks"] = (
            compute_sr(
                float(bottom_df["runs_batter"].sum()), float(len(bottom_df))
            )
            if len(bottom_df) >= self.min_deliveries
            else None
        )

        # 3. quality_adjusted_avg (runs weighted by ELO)
        result["quality_adjusted_avg"] = self._quality_adjusted_avg(
            match_info
        )

        # 4. quality_adjusted_economy
        result["quality_adjusted_economy"] = (
            self._quality_adjusted_economy(match_info)
        )

        # 5. upset_performance_index
        result["upset_performance_index"] = (
            self._upset_performance_index(match_info)
        )

        # 6. high_elo_match_sr
        high_elo_df = legal.filter(
            pl.col("opposition_elo").is_not_null()
            & (pl.col("opposition_elo") > self.high_elo_threshold)
        )
        result["high_elo_match_sr"] = (
            compute_sr(
                float(high_elo_df["runs_batter"].sum()),
                float(len(high_elo_df)),
            )
            if len(high_elo_df) >= self.min_deliveries
            else None
        )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _quality_adjusted_avg(
        self, match_info: list[dict]
    ) -> Optional[float]:
        """Batting average weighted by opposition ELO."""
        weighted_runs = 0.0
        total_weight = 0.0
        innings_count = 0

        for m in match_info:
            elo = m.get("opposition_elo")
            runs = m.get("player_runs")
            balls = m.get("player_balls", 0)
            if elo is None or runs is None or balls is None:
                continue
            weight = clamp(
                (elo - _ELO_MIN) / (_ELO_MAX - _ELO_MIN), 0.01, 1.0
            )
            weighted_runs += runs * weight
            total_weight += weight
            innings_count += 1

        if innings_count < 3 or total_weight < 0.01:
            return None

        avg = safe_divide(weighted_runs, total_weight)
        return clamp(avg, 0.0, 200.0)

    def _quality_adjusted_economy(
        self, match_info: list[dict]
    ) -> Optional[float]:
        """Bowling economy weighted by opposition batting ELO."""
        weighted_economy = 0.0
        total_weight = 0.0
        matches_with_data = 0

        for m in match_info:
            elo = m.get("opposition_elo")
            runs_c = m.get("runs_conceded")
            balls_b = m.get("balls_bowled")
            if elo is None or runs_c is None or not balls_b:
                continue
            economy = safe_divide(runs_c, balls_b / 6.0)
            weight = clamp(
                (elo - _ELO_MIN) / (_ELO_MAX - _ELO_MIN), 0.01, 1.0
            )
            weighted_economy += economy * weight
            total_weight += weight
            matches_with_data += 1

        if matches_with_data < 3 or total_weight < 0.01:
            return None

        return clamp(safe_divide(weighted_economy, total_weight), 0.0, 50.0)

    def _upset_performance_index(
        self, match_info: list[dict]
    ) -> Optional[float]:
        """Fraction of matches where the player outperformed ELO expectations.

        A player's "expected SR" when facing opposition ELO *e* is
        approximated as::

            expected_sr = 100 * (1 - (e - ELO_MIN) / (ELO_MAX - ELO_MIN) * 0.4)

        If their actual SR exceeds expected_sr, it is an "upset" performance.
        """
        upsets = 0
        total = 0

        for m in match_info:
            elo = m.get("opposition_elo")
            balls = m.get("player_balls")
            runs = m.get("player_runs")
            if elo is None or not balls or runs is None:
                continue

            total += 1
            actual_sr = safe_divide(runs, balls) * 100.0
            oq_frac = clamp((elo - _ELO_MIN) / (_ELO_MAX - _ELO_MIN), 0.0, 1.0)
            expected_sr = 100.0 * (1.0 - oq_frac * 0.4)
            if actual_sr >= expected_sr:
                upsets += 1

        if total < 3:
            return None
        return clamp(safe_divide(upsets, total), 0.0, 1.0)

    def _null_result(self) -> dict[str, None]:
        return {
            "sr_vs_top10_attacks": None,
            "sr_vs_bottom10_attacks": None,
            "quality_adjusted_avg": None,
            "quality_adjusted_economy": None,
            "upset_performance_index": None,
            "high_elo_match_sr": None,
        }
