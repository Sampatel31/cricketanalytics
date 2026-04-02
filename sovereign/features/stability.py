"""Stability Features (9 features).

Behavioural interpretation
--------------------------
A player's *stability* characterises the consistency and trajectory of their
career arc.  Elite players maintain their archetype across seasons and formats;
fragile players oscillate.  The HMM-based form-regime score captures latent
"good / average / poor" patches that raw averages hide.

Features returned (9)
----------------------
hmm_form_regime, archetype_consistency, sample_confidence_weight,
age_trajectory, format_adaptability_score, big_match_performance_idx,
debut_vs_current_delta, career_peak_proximity, injury_absence_shift
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import polars as pl

from sovereign.features.utils import clamp, compute_sr, normalize_score, safe_divide

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_INNINGS = 5          # below this → confidence weight = 0.1
_FULL_INNINGS = 30        # at this count → confidence weight = 1.0
_HMM_N_STATES = 3         # "good", "average", "poor"
_INJURY_GAP_DAYS = 180    # 6-month gap triggers injury detection


class StabilityFeatures:
    """Compute 9 stability / career-consistency features for a single player.

    Usage::

        sf = StabilityFeatures()
        result = sf.compute("player_123", seasons_data)

    *seasons_data* is a list of dicts, each with at minimum:

    .. code-block:: python

        {
            "season": "2023",
            "deliveries": pl.DataFrame,      # delivery-level data
            "innings_count": 12,             # innings in this season
            "archetype": "aggressive",       # optional archetype label
            "match_dates": [date, ...],      # optional match date list
            "tournament_stage": "final",     # optional for big_match_idx
        }
    """

    def __init__(
        self,
        hmm_n_states: int = _HMM_N_STATES,
        min_innings: int = _MIN_INNINGS,
        full_innings: int = _FULL_INNINGS,
        injury_gap_days: int = _INJURY_GAP_DAYS,
    ) -> None:
        self.hmm_n_states = hmm_n_states
        self.min_innings = min_innings
        self.full_innings = full_innings
        self.injury_gap_days = injury_gap_days

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(
        self,
        player_id: str,
        seasons_data: list[dict],
    ) -> dict[str, Optional[float]]:
        """Compute all 9 stability features.

        Args:
            player_id: Player identifier (used for logging only).
            seasons_data: List of per-season data dicts.  See class docstring
                for the expected schema.  Seasons need not be in order.

        Returns:
            Dictionary with 9 keys → ``float | None``.
        """
        if not seasons_data:
            return self._null_result()

        # Aggregate innings counts across all seasons
        total_innings = sum(
            int(s.get("innings_count", 0)) for s in seasons_data
        )

        result: dict[str, Optional[float]] = {}

        # 3. sample_confidence_weight
        result["sample_confidence_weight"] = self._confidence_weight(
            total_innings
        )

        # Collect per-season SR for trajectory features
        season_srs = self._per_season_sr(seasons_data)

        # 1. hmm_form_regime
        result["hmm_form_regime"] = self._hmm_form_regime(seasons_data)

        # 2. archetype_consistency
        result["archetype_consistency"] = self._archetype_consistency(
            seasons_data
        )

        # 4. age_trajectory
        result["age_trajectory"] = self._age_trajectory(season_srs)

        # 5. format_adaptability_score
        result["format_adaptability_score"] = self._format_adaptability(
            seasons_data
        )

        # 6. big_match_performance_idx
        result["big_match_performance_idx"] = self._big_match_performance_idx(
            seasons_data
        )

        # 7. debut_vs_current_delta
        result["debut_vs_current_delta"] = self._debut_vs_current_delta(season_srs)

        # 8. career_peak_proximity
        result["career_peak_proximity"] = self._career_peak_proximity(
            season_srs
        )

        # 9. injury_absence_shift
        result["injury_absence_shift"] = self._injury_absence_shift(
            seasons_data
        )

        return result

    # ------------------------------------------------------------------
    # Individual feature helpers
    # ------------------------------------------------------------------

    def _confidence_weight(self, innings_count: int) -> float:
        """Scale confidence linearly from 0.1 at *min_innings* to 1.0 at
        *full_innings*.
        """
        if innings_count <= self.min_innings:
            return 0.1
        if innings_count >= self.full_innings:
            return 1.0
        slope = (1.0 - 0.1) / (self.full_innings - self.min_innings)
        return round(0.1 + slope * (innings_count - self.min_innings), 4)

    def _hmm_form_regime(
        self, seasons_data: list[dict]
    ) -> Optional[float]:
        """Fit a Gaussian HMM to per-over SR sequences and return a stability
        score based on how long the player stays in the "good" state.

        Returns a value in [0, 1] where 1.0 = always in good form.
        """
        # Collect delivery-level runs into a single sequence
        all_runs: list[float] = []
        for season in seasons_data:
            df: Optional[pl.DataFrame] = season.get("deliveries")
            if df is None or df.is_empty():
                continue
            if "runs_batter" not in df.columns:
                continue
            legal = df.filter(pl.col("is_legal_ball")) if "is_legal_ball" in df.columns else df
            all_runs.extend(legal["runs_batter"].cast(pl.Float64).to_list())

        if len(all_runs) < 30:
            return None

        # Use rolling 6-ball (1-over) averages as observation sequence
        arr = np.array(all_runs, dtype=float)
        window = 6
        n_obs = len(arr) - window + 1
        if n_obs < self.hmm_n_states * 3:
            return None

        obs = np.array(
            [arr[i: i + window].mean() for i in range(n_obs)],
            dtype=float,
        ).reshape(-1, 1)

        try:
            from hmmlearn import hmm as hmmlib  # type: ignore[import]

            model = hmmlib.GaussianHMM(
                n_components=self.hmm_n_states,
                covariance_type="diag",
                n_iter=100,
                random_state=42,
            )
            model.fit(obs)
            # State means: highest mean = "good" state
            state_means = model.means_.flatten()
            good_state = int(np.argmax(state_means))
            states = model.predict(obs)
            good_pct = float(np.mean(states == good_state))
            return clamp(good_pct, 0.0, 1.0)
        except Exception as exc:
            logger.debug("HMM fitting failed for player: %s", exc)
            # Fallback: use fraction of above-average overs
            mean_obs = float(obs.mean())
            good_pct = float(np.mean(obs.flatten() >= mean_obs))
            return clamp(good_pct, 0.0, 1.0)

    def _archetype_consistency(
        self, seasons_data: list[dict]
    ) -> Optional[float]:
        """Fraction of seasons with the same archetype label."""
        archetypes = [
            s["archetype"]
            for s in seasons_data
            if s.get("archetype") is not None
        ]
        if len(archetypes) < 2:
            return None
        most_common = max(set(archetypes), key=archetypes.count)
        return clamp(
            safe_divide(archetypes.count(most_common), len(archetypes)),
            0.0,
            1.0,
        )

    def _per_season_sr(
        self, seasons_data: list[dict]
    ) -> list[tuple[str, float]]:
        """Return sorted (season, strike_rate) pairs for each season with data."""
        pairs: list[tuple[str, float]] = []
        for season in seasons_data:
            df: Optional[pl.DataFrame] = season.get("deliveries")
            if df is None or df.is_empty():
                continue
            legal = df
            if "is_legal_ball" in df.columns:
                legal = df.filter(pl.col("is_legal_ball"))
            if "runs_batter" not in legal.columns or len(legal) < 6:
                continue
            runs = float(legal["runs_batter"].sum())
            n = float(len(legal))
            sr = (runs / n) * 100.0
            pairs.append((str(season.get("season", "?")), sr))
        return sorted(pairs, key=lambda x: x[0])

    def _age_trajectory(
        self, season_srs: list[tuple[str, float]]
    ) -> Optional[float]:
        """Fit a quadratic to the career SR curve.

        The derivative at the *last* season indicates trajectory:
        - negative derivative → declining (→ +1)
        - near-zero → at peak (→ 0)
        - positive derivative → rising (→ -1)
        """
        if len(season_srs) < 3:
            return None

        srs = np.array([sr for _, sr in season_srs], dtype=float)
        x = np.arange(len(srs), dtype=float)

        try:
            coeffs = np.polyfit(x, srs, 2)  # ax² + bx + c
        except np.linalg.LinAlgError:
            return None

        a, b, _ = coeffs
        # Derivative at last point: 2a*x_last + b
        x_last = float(len(srs) - 1)
        deriv = 2.0 * a * x_last + b

        # Map derivative to [-1, 1]: negative → declining, positive → rising
        # We invert the sign: rising player should have negative age_trajectory
        # (closer to the future peak)
        score = -clamp(deriv / max(abs(deriv) + 1e-6, 1.0), -1.0, 1.0)
        return clamp(score, -1.0, 1.0)

    def _format_adaptability(
        self, seasons_data: list[dict]
    ) -> Optional[float]:
        """CV-based consistency of SR across different formats."""
        format_srs: dict[str, list[float]] = {}
        for season in seasons_data:
            fmt = str(season.get("format", "unknown"))
            df: Optional[pl.DataFrame] = season.get("deliveries")
            if df is None or df.is_empty():
                continue
            legal = df.filter(pl.col("is_legal_ball")) if "is_legal_ball" in df.columns else df
            if "runs_batter" not in legal.columns or len(legal) < 6:
                continue
            sr = float(legal["runs_batter"].sum()) / len(legal) * 100.0
            format_srs.setdefault(fmt, []).append(sr)

        if len(format_srs) < 2:
            return None

        all_srs = [sr for srs in format_srs.values() for sr in srs]
        arr = pl.Series(all_srs, dtype=pl.Float64)
        from sovereign.features.utils import coefficient_of_variation
        cv = coefficient_of_variation(arr)
        if cv is None:
            return None
        # Low CV → consistent across formats → high score
        return clamp(safe_divide(1.0, 1.0 + abs(cv)), 0.0, 1.0)

    def _big_match_performance_idx(
        self, seasons_data: list[dict]
    ) -> Optional[float]:
        """SR in finals/semi-finals relative to group-stage SR."""
        big_runs, big_balls = 0.0, 0.0
        normal_runs, normal_balls = 0.0, 0.0

        _HIGH_STAGE = {"final", "semi-final", "semi final", "semifinal"}

        for season in seasons_data:
            stage = str(season.get("tournament_stage", "")).lower().strip()
            df: Optional[pl.DataFrame] = season.get("deliveries")
            if df is None or df.is_empty() or "runs_batter" not in df.columns:
                continue
            legal = df.filter(pl.col("is_legal_ball")) if "is_legal_ball" in df.columns else df
            runs = float(legal["runs_batter"].sum())
            balls = float(len(legal))

            if any(s in stage for s in _HIGH_STAGE):
                big_runs += runs
                big_balls += balls
            else:
                normal_runs += runs
                normal_balls += balls

        if big_balls < 10 or normal_balls < 10:
            return None

        sr_big = safe_divide(big_runs, big_balls) * 100.0
        sr_normal = safe_divide(normal_runs, normal_balls) * 100.0
        if sr_normal < 1.0:
            return None

        ratio = safe_divide(sr_big, sr_normal, default=1.0)
        return clamp(normalize_score(ratio, 0.0, 2.0), 0.0, 1.0)

    def _debut_vs_current_delta(
        self, season_srs: list[tuple[str, float]]
    ) -> Optional[float]:
        """SR in the most recent season minus SR in the first season."""
        if len(season_srs) < 2:
            return None
        sr_debut = season_srs[0][1]
        sr_current = season_srs[-1][1]
        return clamp(sr_current - sr_debut, -100.0, 100.0)

    def _career_peak_proximity(
        self, season_srs: list[tuple[str, float]]
    ) -> Optional[float]:
        """How close the most recent season SR is to the career peak SR."""
        if len(season_srs) < 2:
            return None
        srs = [sr for _, sr in season_srs]
        peak = max(srs)
        current = srs[-1]
        if peak < 1.0:
            return None
        return clamp(safe_divide(current, peak), 0.0, 1.0)

    def _injury_absence_shift(
        self, seasons_data: list[dict]
    ) -> Optional[float]:
        """Performance change immediately after a gap > *injury_gap_days* days.

        Returns the fraction of post-gap seasons where SR improved vs pre-gap.
        A value of 1.0 means the player always came back stronger.
        """
        from datetime import date as dt_date

        dated_seasons: list[tuple[dt_date, float]] = []
        for season in seasons_data:
            dates = season.get("match_dates")
            df: Optional[pl.DataFrame] = season.get("deliveries")
            if not dates or df is None or df.is_empty():
                continue
            legal = df.filter(pl.col("is_legal_ball")) if "is_legal_ball" in df.columns else df
            if "runs_batter" not in legal.columns or len(legal) < 6:
                continue
            sr = float(legal["runs_batter"].sum()) / len(legal) * 100.0
            # Use the last match date of the season as the reference point
            last_date = max(dates)
            dated_seasons.append((last_date, sr))

        if len(dated_seasons) < 2:
            return None

        dated_seasons.sort(key=lambda x: x[0])

        gaps_found = 0
        improved_after = 0
        for i in range(1, len(dated_seasons)):
            gap = (dated_seasons[i][0] - dated_seasons[i - 1][0]).days
            if gap >= self.injury_gap_days:
                gaps_found += 1
                if dated_seasons[i][1] > dated_seasons[i - 1][1]:
                    improved_after += 1

        if gaps_found == 0:
            return None
        return clamp(safe_divide(improved_after, gaps_found), 0.0, 1.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _null_result(self) -> dict[str, None]:
        keys = [
            "hmm_form_regime", "archetype_consistency",
            "sample_confidence_weight", "age_trajectory",
            "format_adaptability_score", "big_match_performance_idx",
            "debut_vs_current_delta", "career_peak_proximity",
            "injury_absence_shift",
        ]
        return {k: None for k in keys}

    # expose helper for public use (e.g. builder)
    def debut_vs_current(
        self, season_srs: list[tuple[str, float]]
    ) -> Optional[float]:
        """Alias for :meth:`_debut_vs_current_delta` (public)."""
        return self._debut_vs_current_delta(season_srs)
