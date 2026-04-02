"""Tactical Features (15 features).

Behavioural interpretation
--------------------------
These features capture *how* a player plays rather than the raw averages.
They answer questions like:

- Does the player accelerate late in an innings?
- Does pressure cause anxiety (dot-ball spiral) or controlled aggression?
- Is home ground a comfort factor?
- How quickly does the player "re-calibrate" after a bad patch?

Features returned (15)
----------------------
clutch_delta, recovery_rate, running_score_avg, partnership_acceleration,
cold_start_sr, pace_vs_spin_delta, home_away_delta, innings_type_delta,
consistency_index, momentum_riding_score, momentum_reset_score,
aggression_escalation, boundary_dependency, dot_ball_anxiety, big_match_index
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import polars as pl

from sovereign.features.utils import (
    clamp,
    coefficient_of_variation,
    compute_sr,
    normalize_score,
    rolling_mean,
    safe_divide,
)

logger = logging.getLogger(__name__)

_WINDOW = 5           # rolling window for momentum / recovery
_MIN_BALLS = 10       # minimum balls for any tactical metric
_RECENT_BALLS = 10    # balls used for "recent form" windows


class TacticalFeatures:
    """Compute 15 tactical / behavioural features for a single batter.

    Usage::

        tf = TacticalFeatures()
        result = tf.compute("player_123", df)

    Expected DataFrame columns
    --------------------------
    - ``runs_batter``   (int):  Runs scored by the batter
    - ``is_legal_ball`` (bool): True for legal deliveries
    - ``spi_total``     (float, optional): SPI for big_match_index
    - ``over_number``   (int, optional):   For phase-based features
    - ``ball_in_innings`` (int, optional): Ball sequence within innings
    - ``innings_number`` (int, optional):  Innings 1 or 2 for chase/defend
    - ``bowler_type``   (str, optional):  'pace' | 'spin' for pace_vs_spin
    - ``is_home``       (bool, optional): True if home match
    - ``target``        (int, optional):  Chase target (None in 1st innings)
    - ``partnership_ball`` (int, optional): Ball within the partnership
    """

    def __init__(
        self,
        window: int = _WINDOW,
        recent_balls: int = _RECENT_BALLS,
        min_balls: int = _MIN_BALLS,
    ) -> None:
        self.window = window
        self.recent_balls = recent_balls
        self.min_balls = min_balls

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        player_id: str,
        deliveries_df: pl.DataFrame,
    ) -> dict[str, Optional[float]]:
        """Compute all 15 tactical features.

        Args:
            player_id: Player ID (used for logging only).
            deliveries_df: See class docstring for expected columns.

        Returns:
            Dictionary with 15 keys → ``float | None``.
        """
        legal = (
            deliveries_df.lazy()
            .filter(pl.col("is_legal_ball"))
            .collect()
        )

        n = len(legal)
        if n < self.min_balls:
            return self._null_result()

        result: dict[str, Optional[float]] = {}

        # 1. clutch_delta: SR in death overs − SR in powerplay overs
        result["clutch_delta"] = self._clutch_delta(legal)

        # 2. recovery_rate
        result["recovery_rate"] = self._recovery_rate(legal)

        # 3. running_score_avg
        result["running_score_avg"] = self._running_score_avg(legal)

        # 4. partnership_acceleration
        result["partnership_acceleration"] = self._partnership_acceleration(
            legal
        )

        # 5. cold_start_sr
        result["cold_start_sr"] = self._cold_start_sr(legal)

        # 6. pace_vs_spin_delta
        result["pace_vs_spin_delta"] = self._pace_vs_spin_delta(legal)

        # 7. home_away_delta
        result["home_away_delta"] = self._home_away_delta(legal)

        # 8. innings_type_delta (chasing vs defending)
        result["innings_type_delta"] = self._innings_type_delta(legal)

        # 9. consistency_index (inverse CV)
        result["consistency_index"] = self._consistency_index(legal)

        # 10. momentum_riding_score
        result["momentum_riding_score"] = self._momentum_riding_score(legal)

        # 11. momentum_reset_score
        result["momentum_reset_score"] = self._momentum_reset_score(legal)

        # 12. aggression_escalation
        result["aggression_escalation"] = self._aggression_escalation(legal)

        # 13. boundary_dependency
        result["boundary_dependency"] = self._boundary_dependency(legal)

        # 14. dot_ball_anxiety
        result["dot_ball_anxiety"] = self._dot_ball_anxiety(legal)

        # 15. big_match_index
        result["big_match_index"] = self._big_match_index(legal)

        return result

    # ------------------------------------------------------------------
    # Individual feature helpers
    # ------------------------------------------------------------------

    def _clutch_delta(self, df: pl.DataFrame) -> Optional[float]:
        """SR in death overs − SR in powerplay overs."""
        if "over_number" not in df.columns:
            return None

        def _sr_phase(phase_df: pl.DataFrame) -> Optional[float]:
            if len(phase_df) < self.min_balls:
                return None
            runs = float(phase_df["runs_batter"].sum())
            return compute_sr(runs, float(len(phase_df)))

        pp_df = df.filter(pl.col("over_number") <= 6)
        death_df = df.filter(pl.col("over_number") > 15)
        sr_pp = _sr_phase(pp_df)
        sr_death = _sr_phase(death_df)
        if sr_pp is None or sr_death is None:
            return None
        return clamp(sr_death - sr_pp, -200.0, 200.0)

    def _recovery_rate(self, df: pl.DataFrame) -> Optional[float]:
        """Fraction of windows after a dot ball where ≥1 run is scored.

        Uses a *window*-ball rolling window.  For each position that starts
        a "dot sequence" (runs_batter == 0), measure whether the very next
        delivery scores ≥ 1.
        """
        runs = df["runs_batter"].to_list()
        if len(runs) < 2:
            return None

        recoveries = 0
        dot_followed = 0
        for i in range(len(runs) - 1):
            if runs[i] == 0:
                dot_followed += 1
                if runs[i + 1] > 0:
                    recoveries += 1

        if dot_followed == 0:
            return 1.0
        return clamp(safe_divide(recoveries, dot_followed), 0.0, 1.0)

    def _running_score_avg(self, df: pl.DataFrame) -> Optional[float]:
        """Average runs scored in a rolling *window*-ball window."""
        runs_series = df["runs_batter"]
        if len(runs_series) < self.window:
            return None
        rm = rolling_mean(runs_series.cast(pl.Float64), self.window)
        mean_val = rm.mean()
        if mean_val is None:
            return None
        return clamp(float(mean_val), -5.0, 50.0)

    def _partnership_acceleration(
        self, df: pl.DataFrame
    ) -> Optional[float]:
        """Runs-per-ball change in the second half vs first half of a
        partnership.

        Uses ``partnership_ball`` if present, otherwise uses ball sequence
        within innings.
        """
        col = "partnership_ball" if "partnership_ball" in df.columns else None
        if col is None:
            if "ball_in_innings" in df.columns:
                col = "ball_in_innings"
            else:
                return None

        n = len(df)
        if n < 2 * self.min_balls:
            return None

        mid = n // 2
        first_half = df.head(mid)
        second_half = df.tail(n - mid)

        rpb_first = safe_divide(
            float(first_half["runs_batter"].sum()), float(len(first_half))
        )
        rpb_second = safe_divide(
            float(second_half["runs_batter"].sum()), float(len(second_half))
        )
        return clamp((rpb_second - rpb_first) * 6, -50.0, 50.0)

    def _cold_start_sr(self, df: pl.DataFrame) -> Optional[float]:
        """SR in the first 10 balls of the innings."""
        first_10 = df.head(10)
        if len(first_10) < 5:
            return None
        runs = float(first_10["runs_batter"].sum())
        return compute_sr(runs, float(len(first_10)))

    def _pace_vs_spin_delta(self, df: pl.DataFrame) -> Optional[float]:
        """SR vs pace minus SR vs spin."""
        if "bowler_type" not in df.columns:
            return None

        pace_df = df.filter(pl.col("bowler_type") == "pace")
        spin_df = df.filter(pl.col("bowler_type") == "spin")

        if len(pace_df) < self.min_balls or len(spin_df) < self.min_balls:
            return None

        sr_pace = compute_sr(
            float(pace_df["runs_batter"].sum()), float(len(pace_df))
        )
        sr_spin = compute_sr(
            float(spin_df["runs_batter"].sum()), float(len(spin_df))
        )
        if sr_pace is None or sr_spin is None:
            return None
        return clamp(sr_pace - sr_spin, -100.0, 100.0)

    def _home_away_delta(self, df: pl.DataFrame) -> Optional[float]:
        """SR at home minus SR away."""
        if "is_home" not in df.columns:
            return None

        home_df = df.filter(pl.col("is_home"))
        away_df = df.filter(~pl.col("is_home"))

        if len(home_df) < self.min_balls or len(away_df) < self.min_balls:
            return None

        sr_home = compute_sr(
            float(home_df["runs_batter"].sum()), float(len(home_df))
        )
        sr_away = compute_sr(
            float(away_df["runs_batter"].sum()), float(len(away_df))
        )
        if sr_home is None or sr_away is None:
            return None
        return clamp(sr_home - sr_away, -100.0, 100.0)

    def _innings_type_delta(self, df: pl.DataFrame) -> Optional[float]:
        """SR when chasing (target set) minus SR when defending."""
        if "target" not in df.columns and "innings_number" not in df.columns:
            return None

        # Chasing: innings_number == 2 or target is not null
        if "target" in df.columns:
            chase_df = df.filter(pl.col("target").is_not_null())
            defend_df = df.filter(pl.col("target").is_null())
        else:
            chase_df = df.filter(pl.col("innings_number") == 2)
            defend_df = df.filter(pl.col("innings_number") == 1)

        if len(chase_df) < self.min_balls or len(defend_df) < self.min_balls:
            return None

        sr_chase = compute_sr(
            float(chase_df["runs_batter"].sum()), float(len(chase_df))
        )
        sr_defend = compute_sr(
            float(defend_df["runs_batter"].sum()), float(len(defend_df))
        )
        if sr_chase is None or sr_defend is None:
            return None
        return clamp(sr_chase - sr_defend, -100.0, 100.0)

    def _consistency_index(self, df: pl.DataFrame) -> Optional[float]:
        """Inverse of the coefficient of variation of per-delivery runs.

        A player who always scores around the mean has a low CV → high CI.
        CI = 1 / (1 + CV)  so it is always in [0, 1].
        """
        cv = coefficient_of_variation(
            df["runs_batter"].cast(pl.Float64)
        )
        if cv is None:
            return None
        return clamp(safe_divide(1.0, 1.0 + abs(cv)), 0.0, 1.0)

    def _momentum_riding_score(self, df: pl.DataFrame) -> Optional[float]:
        """Pearson correlation of rolling mean with next-delivery run.

        Captures whether good form leads to continued good form.
        """
        if len(df) < self.window + self.recent_balls:
            return None

        runs = df["runs_batter"].cast(pl.Float64)
        rm = rolling_mean(runs, self.window)

        # Shift rolling mean to compare against next delivery
        rm_arr = rm.to_numpy()[:-1]
        next_arr = runs.to_numpy()[1:]
        if len(rm_arr) < 5:
            return None

        try:
            corr = float(np.corrcoef(rm_arr, next_arr)[0, 1])
        except Exception:
            return None

        if np.isnan(corr):
            return None
        # Map correlation from [-1, 1] to [0, 1]
        return clamp((corr + 1.0) / 2.0, 0.0, 1.0)

    def _momentum_reset_score(self, df: pl.DataFrame) -> Optional[float]:
        """Probability of a good delivery following a run of poor form.

        "Poor form" = last *window* deliveries were all dots.
        """
        if len(df) < self.window + 1:
            return None

        runs = df["runs_batter"].to_list()
        resets = 0
        total_poor_streaks = 0

        for i in range(self.window, len(runs)):
            window = runs[i - self.window: i]
            if all(r == 0 for r in window):
                total_poor_streaks += 1
                if runs[i] > 0:
                    resets += 1

        if total_poor_streaks == 0:
            return None
        return clamp(safe_divide(resets, total_poor_streaks), 0.0, 1.0)

    def _aggression_escalation(self, df: pl.DataFrame) -> Optional[float]:
        """Rate of SR increase within a single innings.

        Computes slope of a linear fit through the per-ball running SR.
        Normalised to [0, 1].
        """
        if len(df) < self.min_balls:
            return None

        runs = df["runs_batter"].to_numpy(allow_copy=True).astype(float)
        cumruns = np.cumsum(runs)
        balls = np.arange(1, len(runs) + 1, dtype=float)
        sr_curve = cumruns / balls * 100.0

        if len(sr_curve) < 3:
            return None

        # Fit a line y = a + b*x; b is the slope
        x = np.arange(len(sr_curve), dtype=float)
        try:
            coeffs = np.polyfit(x, sr_curve, 1)
        except np.linalg.LinAlgError:
            return None

        slope = float(coeffs[0])
        # Positive slope → aggression increases → high score
        return clamp(normalize_score(slope, -5.0, 5.0), 0.0, 1.0)

    def _boundary_dependency(self, df: pl.DataFrame) -> Optional[float]:
        """Fraction of total runs that come from 4s and 6s."""
        total_runs = float(df["runs_batter"].sum())
        if total_runs < 1.0:
            return None

        if "is_boundary" not in df.columns:
            boundary_df = df.filter(pl.col("runs_batter") >= 4)
        else:
            boundary_df = df.filter(pl.col("is_boundary"))

        boundary_runs = float(boundary_df["runs_batter"].sum())
        return clamp(safe_divide(boundary_runs, total_runs), 0.0, 1.0)

    def _dot_ball_anxiety(self, df: pl.DataFrame) -> Optional[float]:
        """Increase in SR immediately after ≥2 consecutive dot balls.

        A higher score means the player over-reacts to dots (anxiety).
        """
        runs = df["runs_batter"].to_list()
        if len(runs) < 3:
            return None

        normal_sr_sum = 0.0
        after_dots_sr_sum = 0.0
        after_dots_count = 0
        normal_count = 0

        for i in range(2, len(runs)):
            if runs[i - 2] == 0 and runs[i - 1] == 0:
                after_dots_sr_sum += runs[i] * 100.0
                after_dots_count += 1
            else:
                normal_sr_sum += runs[i] * 100.0
                normal_count += 1

        if after_dots_count == 0 or normal_count == 0:
            return None

        avg_after = safe_divide(after_dots_sr_sum, after_dots_count)
        avg_normal = safe_divide(normal_sr_sum, normal_count)
        diff = avg_after - avg_normal
        # Normalise: 0 = no change; 1 = strong over-reaction (>200 SR diff)
        return clamp(normalize_score(diff, 0.0, 200.0), 0.0, 1.0)

    def _big_match_index(self, df: pl.DataFrame) -> Optional[float]:
        """SR in SPI > 7 relative to SR in SPI < 3.

        Normalised to [0, 1] where 1.0 means the player performs twice as
        well under extreme pressure as in low-pressure situations.
        """
        if "spi_total" not in df.columns:
            return None

        high_spi = df.filter(pl.col("spi_total") > 7.0)
        low_spi = df.filter(
            pl.col("spi_total").is_not_null() & (pl.col("spi_total") < 3.0)
        )

        if len(high_spi) < 5 or len(low_spi) < 5:
            return None

        sr_high = compute_sr(
            float(high_spi["runs_batter"].sum()), float(len(high_spi))
        )
        sr_low = compute_sr(
            float(low_spi["runs_batter"].sum()), float(len(low_spi))
        )
        if sr_low is None or sr_high is None or sr_low < 1.0:
            return None

        ratio = sr_high / sr_low
        # ratio 1.0 → neutral; 2.0 → very big match player
        return clamp(normalize_score(ratio, 0.0, 2.0), 0.0, 1.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _null_result(self) -> dict[str, None]:
        keys = [
            "clutch_delta", "recovery_rate", "running_score_avg",
            "partnership_acceleration", "cold_start_sr", "pace_vs_spin_delta",
            "home_away_delta", "innings_type_delta", "consistency_index",
            "momentum_riding_score", "momentum_reset_score",
            "aggression_escalation", "boundary_dependency",
            "dot_ball_anxiety", "big_match_index",
        ]
        return {k: None for k in keys}
