"""Fixtures for ingestion tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from sovereign.ingestion.models import MatchInfo, ParsedMatch, RawDelivery

SAMPLE_DIR = Path(__file__).parent / "sample_data"


@pytest.fixture
def t20i_yaml_path() -> Path:
    return SAMPLE_DIR / "t20i_v2.yaml"


@pytest.fixture
def ipl_yaml_path() -> Path:
    return SAMPLE_DIR / "ipl_franchise.yaml"


@pytest.fixture
def odi_yaml_path() -> Path:
    return SAMPLE_DIR / "odi_final_v2.yaml"


@pytest.fixture
def minimal_match_info() -> MatchInfo:
    return MatchInfo(
        match_id="test-001",
        date=date(2023, 6, 15),
        format="T20I",
        team1="India",
        team2="Pakistan",
        venue="Eden Gardens",
    )


def _make_delivery(
    over: int = 0,
    ball: int = 0,
    innings: int = 1,
    runs_batter: int = 1,
    runs_extras: int = 0,
    is_wicket: bool = False,
    is_legal: bool = True,
    batter_id: str = "batter1",
    bowler_id: str = "bowler1",
) -> RawDelivery:
    return RawDelivery(
        batter_id=batter_id,
        bowler_id=bowler_id,
        non_striker_id="non_striker1",
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


@pytest.fixture
def valid_parsed_match(minimal_match_info: MatchInfo) -> ParsedMatch:
    """A minimal valid ParsedMatch with 24 deliveries."""
    deliveries = [_make_delivery(over=o, ball=b) for o in range(4) for b in range(6)]
    return ParsedMatch(match_info=minimal_match_info, deliveries=deliveries)
