"""Ball-by-ball context builder.

For every delivery this module computes score state, RRR, phase labels,
partnership runs and a rough win probability.

Usage::

    from sovereign.enrichment.context import ContextBuilder

    builder = ContextBuilder(match_info)
    state: dict = {}
    for raw_delivery in parsed_match.deliveries:
        enriched = builder.build_context(raw_delivery, state)
"""

from __future__ import annotations

from typing import Optional

import structlog

from sovereign.enrichment.models import EnrichedDelivery
from sovereign.ingestion.models import MatchInfo, RawDelivery

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Phase boundaries per format
# ---------------------------------------------------------------------------
_PHASE_BOUNDARIES: dict[str, tuple[int, int, int, int]] = {
    # (pp_start, pp_end, middle_end, death_end) - all inclusive over numbers (0-indexed)
    "T20I": (0, 5, 14, 19),
    "T20": (0, 5, 14, 19),
    "WOMENS_T20I": (0, 5, 14, 19),
    "U19_T20I": (0, 5, 14, 19),
    "ODI": (0, 9, 39, 49),
    "WOMENS_ODI": (0, 9, 39, 49),
    "U19_ODI": (0, 9, 39, 49),
    "LIST_A": (0, 9, 39, 49),
    "TEST": (0, 9, 59, 999),
    "WOMENS_TEST": (0, 9, 59, 999),
    "FIRST_CLASS": (0, 9, 59, 999),
}

# Total legal balls per format
_TOTAL_LEGAL_BALLS: dict[str, Optional[int]] = {
    "T20I": 120,
    "T20": 120,
    "WOMENS_T20I": 120,
    "U19_T20I": 120,
    "ODI": 300,
    "WOMENS_ODI": 300,
    "U19_ODI": 300,
    "LIST_A": 300,
    "TEST": None,
    "WOMENS_TEST": None,
    "FIRST_CLASS": None,
}


def _phase_label(format_type: str, over_number: int) -> str:
    """Return 'powerplay', 'middle' or 'death' for *over_number* (0-indexed)."""
    bounds = _PHASE_BOUNDARIES.get(format_type.upper())
    if bounds is None:
        return "middle"
    _, pp_end, middle_end, _ = bounds
    if over_number <= pp_end:
        return "powerplay"
    if over_number <= middle_end:
        return "middle"
    return "death"


def phase_label(format_type: str, over_number: int) -> str:
    """Public alias for :func:`_phase_label`."""
    return _phase_label(format_type, over_number)


def _win_probability(
    innings: int,
    target: Optional[int],
    team_score: int,
    wickets_fallen: int,
    balls_remaining: Optional[int],
    format_type: str,
) -> float:
    """Simple logistic win probability approximation.

    First innings: returns 0.5 (neutral, no target yet).
    Second innings: uses run-rate ratio and wickets as a proxy.
    """
    if innings == 1 or target is None or balls_remaining is None:
        return 0.5

    required = target - team_score
    if required <= 0:
        return 1.0  # Already won
    if balls_remaining <= 0:
        return 0.0  # No balls left, cannot win

    total_balls = _TOTAL_LEGAL_BALLS.get(format_type.upper())
    if total_balls is None:
        total_balls = balls_remaining + (team_score * 6 // max(target, 1))

    # Simple resource factor: fraction of resources remaining
    resource_fraction = balls_remaining / total_balls if total_balls > 0 else 0.5
    wickets_fraction = (10 - wickets_fallen) / 10.0  # wickets in hand fraction

    # Pressure ratio: required vs what's feasible given resources
    feasible_runs = (balls_remaining / 6.0) * 8.0 * wickets_fraction
    if feasible_runs <= 0:
        return 0.0
    ratio = required / feasible_runs

    import math

    # Logistic mapping: ratio=1 → ~50%, ratio<1 → winning, ratio>1 → losing
    prob = 1.0 / (1.0 + math.exp(2.0 * (ratio - 1.0)))
    return max(0.0, min(1.0, prob))


class ContextBuilder:
    """Build per-ball context for a single match.

    The caller must pass a mutable *state* dict that is updated in place
    across deliveries, enabling incremental computation::

        state: dict = {}
        for d in match.deliveries:
            enriched = builder.build_context(d, state)
    """

    def __init__(self, match_info: MatchInfo) -> None:
        self.match_info = match_info
        self._format = (match_info.format or "UNKNOWN").upper()
        self._total_legal_balls = _TOTAL_LEGAL_BALLS.get(self._format)

    def build_context(
        self, delivery: RawDelivery, state: dict
    ) -> EnrichedDelivery:
        """Enrich *delivery* using accumulated *state*.

        *state* is mutated in-place and should be passed to subsequent calls.
        """
        innings = delivery.innings_number
        inn_key = f"innings_{innings}"

        if inn_key not in state:
            state[inn_key] = {
                "score": 0,
                "wickets": 0,
                "legal_balls": 0,
                "partnership_runs": 0,
                "partnership_balls": 0,
                "target": None,
            }

        inn = state[inn_key]

        # Retrieve target for second innings
        target: Optional[int] = None
        if innings == 2:
            target = state.get("innings_1", {}).get("score", 0) + 1

        # Phase label
        phase = _phase_label(self._format, delivery.over_number)

        # Compute remaining balls
        legal_balls_played = inn["legal_balls"]
        balls_remaining: Optional[int] = None
        if self._total_legal_balls is not None:
            balls_remaining = max(0, self._total_legal_balls - legal_balls_played)

        # Run rates
        current_run_rate: Optional[float] = None
        if inn["legal_balls"] > 0:
            current_run_rate = (inn["score"] / inn["legal_balls"]) * 6.0

        required_run_rate: Optional[float] = None
        if innings == 2 and target is not None and balls_remaining is not None and balls_remaining > 0:
            rr = target - inn["score"]
            if rr > 0:
                required_run_rate = (rr / balls_remaining) * 6.0
            else:
                required_run_rate = 0.0

        win_prob = _win_probability(
            innings,
            target if innings == 2 else None,
            inn["score"],
            inn["wickets"],
            balls_remaining,
            self._format,
        )

        # Build enriched delivery (copy all fields from raw)
        enriched = EnrichedDelivery(
            batter_id=delivery.batter_id,
            bowler_id=delivery.bowler_id,
            non_striker_id=delivery.non_striker_id,
            batting_team=delivery.batting_team,
            bowling_team=delivery.bowling_team,
            innings_number=innings,
            over_number=delivery.over_number,
            ball_number=delivery.ball_number,
            runs_batter=delivery.runs_batter,
            runs_extras=delivery.runs_extras,
            runs_total=delivery.runs_total,
            is_legal_ball=delivery.is_legal_ball,
            is_wicket=delivery.is_wicket,
            wicket_kind=delivery.wicket_kind,
            player_dismissed_id=delivery.player_dismissed_id,
            # Context
            team_score_at_ball=inn["score"],
            wickets_fallen=inn["wickets"],
            wickets_in_hand=11 - inn["wickets"],
            partnership_runs=inn["partnership_runs"],
            partnership_balls=inn["partnership_balls"],
            target=target if innings == 2 else None,
            required_runs=(target - inn["score"]) if (innings == 2 and target is not None) else None,
            balls_remaining=balls_remaining,
            current_run_rate=current_run_rate,
            required_run_rate=required_run_rate,
            phase_label=phase,
            win_probability=win_prob,
        )

        # Update state after snapshot
        inn["score"] += delivery.runs_total
        if delivery.is_legal_ball:
            inn["legal_balls"] += 1
        if delivery.is_wicket:
            inn["wickets"] += 1
            inn["partnership_runs"] = 0
            inn["partnership_balls"] = 0
        else:
            inn["partnership_runs"] += delivery.runs_total
            if delivery.is_legal_ball:
                inn["partnership_balls"] += 1

        return enriched
