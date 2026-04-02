"""Fixtures for enrichment tests."""

from __future__ import annotations

from datetime import date

import pytest

from sovereign.enrichment.models import EnrichedDelivery
from sovereign.ingestion.models import MatchInfo, RawDelivery


@pytest.fixture
def t20i_match_info() -> MatchInfo:
    return MatchInfo(
        match_id="enrich-001",
        date=date(2023, 6, 15),
        format="T20I",
        team1="India",
        team2="Pakistan",
    )


@pytest.fixture
def odi_match_info() -> MatchInfo:
    return MatchInfo(
        match_id="enrich-odi-001",
        date=date(2023, 11, 19),
        format="ODI",
        team1="India",
        team2="Australia",
    )


@pytest.fixture
def test_match_info() -> MatchInfo:
    return MatchInfo(
        match_id="enrich-test-001",
        date=date(2023, 3, 1),
        format="TEST",
        team1="England",
        team2="Australia",
    )


def make_delivery(
    over: int = 0,
    ball: int = 0,
    innings: int = 1,
    runs_batter: int = 1,
    runs_extras: int = 0,
    is_legal: bool = True,
    is_wicket: bool = False,
) -> RawDelivery:
    return RawDelivery(
        batter_id="batter1",
        bowler_id="bowler1",
        non_striker_id="ns1",
        batting_team="India",
        bowling_team="Pakistan",
        innings_number=innings,
        over_number=over,
        ball_number=ball,
        runs_batter=runs_batter,
        runs_extras=runs_extras,
        runs_total=runs_batter + runs_extras,
        is_legal_ball=is_legal,
        is_wicket=is_wicket,
    )


def make_enriched(
    innings: int = 2,
    over: int = 19,
    wickets_fallen: int = 7,
    team_score: int = 150,
    target: int = 180,
    rrr: float = 18.0,
    crr: float = 8.0,
    phase: str = "death",
    balls_remaining: int = 6,
) -> EnrichedDelivery:
    effective_target = target if innings == 2 else None
    required_runs = (target - team_score) if (innings == 2 and target is not None) else None
    return EnrichedDelivery(
        batter_id="batter1",
        bowler_id="bowler1",
        non_striker_id="ns1",
        batting_team="India",
        bowling_team="Pakistan",
        innings_number=innings,
        over_number=over,
        ball_number=0,
        runs_batter=0,
        runs_extras=0,
        runs_total=0,
        is_legal_ball=True,
        is_wicket=False,
        team_score_at_ball=team_score,
        wickets_fallen=wickets_fallen,
        wickets_in_hand=11 - wickets_fallen,
        target=effective_target,
        required_runs=required_runs,
        balls_remaining=balls_remaining,
        current_run_rate=crr,
        required_run_rate=rrr if innings == 2 else None,
        phase_label=phase,
        win_probability=0.3,
    )
