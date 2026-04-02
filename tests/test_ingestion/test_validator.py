"""Tests for MatchValidator and DuplicateDetector."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from sovereign.ingestion.models import MatchInfo, ParsedMatch, RawDelivery
from sovereign.ingestion.validator import (
    DuplicateDetector,
    MatchValidator,
    compute_file_hash,
)

validator = MatchValidator()


def _delivery(
    over: int = 0,
    ball: int = 0,
    innings: int = 1,
    runs_batter: int = 1,
    runs_extras: int = 0,
    batter_id: str = "batter1",
    bowler_id: str = "bowler1",
) -> RawDelivery:
    return RawDelivery(
        batter_id=batter_id,
        bowler_id=bowler_id,
        non_striker_id="ns1",
        batting_team="India",
        bowling_team="Pakistan",
        innings_number=innings,
        over_number=over,
        ball_number=ball,
        runs_batter=runs_batter,
        runs_extras=runs_extras,
        runs_total=runs_batter + runs_extras,
        is_legal_ball=True,
        is_wicket=False,
    )


def _info(**kwargs) -> MatchInfo:
    defaults = dict(
        match_id="test-001",
        date=date(2023, 6, 15),
        format="T20I",
        team1="India",
        team2="Pakistan",
    )
    defaults.update(kwargs)
    return MatchInfo(**defaults)


def _valid_match(n_deliveries: int = 24) -> ParsedMatch:
    deliveries = [_delivery(over=i // 6, ball=i % 6) for i in range(n_deliveries)]
    return ParsedMatch(match_info=_info(), deliveries=deliveries)


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------

def test_valid_match_passes():
    """A well-formed match passes validation."""
    is_valid, errors = validator.validate_match(_valid_match())
    assert is_valid is True
    assert errors == []


# ---------------------------------------------------------------------------
# Negative tests – missing fields
# ---------------------------------------------------------------------------

def test_missing_teams_fails():
    """Missing team1/team2 causes validation error."""
    info = _info(team1="", team2="")
    match = ParsedMatch(match_info=info, deliveries=[_delivery() for _ in range(24)])
    is_valid, errors = validator.validate_match(match)
    assert is_valid is False
    assert any("teams" in e.lower() for e in errors)


def test_too_few_deliveries_fails():
    """Less than 20 deliveries triggers minimum delivery check."""
    match = _valid_match(n_deliveries=5)
    is_valid, errors = validator.validate_match(match)
    assert is_valid is False
    assert any("deliveries" in e.lower() for e in errors)


def test_invalid_ball_number_fails():
    """Ball number > 9 should fail."""
    deliveries = [_delivery(over=0, ball=b) for b in range(24)]
    # Force an invalid ball number
    deliveries[0] = RawDelivery(
        batter_id="b",
        bowler_id="bw",
        non_striker_id="ns",
        batting_team="India",
        bowling_team="Pak",
        innings_number=1,
        over_number=0,
        ball_number=15,  # invalid
        runs_batter=0,
        runs_extras=0,
        runs_total=0,
        is_legal_ball=True,
        is_wicket=False,
    )
    match = ParsedMatch(match_info=_info(), deliveries=deliveries)
    is_valid, errors = validator.validate_match(match)
    assert is_valid is False
    assert any("ball_number" in e for e in errors)


def test_negative_runs_fails():
    """Negative runs_batter should fail."""
    deliveries = [_delivery(over=i // 6, ball=i % 6) for i in range(24)]
    deliveries[0] = _delivery(runs_batter=-1)
    match = ParsedMatch(match_info=_info(), deliveries=deliveries)
    is_valid, errors = validator.validate_match(match)
    assert is_valid is False
    assert any("negative" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# File hash tests
# ---------------------------------------------------------------------------

def test_file_hash_consistency(t20i_yaml_path: Path):
    """Same file produces the same hash on consecutive calls."""
    h1 = compute_file_hash(t20i_yaml_path)
    h2 = compute_file_hash(t20i_yaml_path)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_duplicate_detector_works(t20i_yaml_path: Path):
    """DuplicateDetector returns False for first call, True for second."""
    detector = DuplicateDetector()
    assert detector.is_duplicate(t20i_yaml_path) is False
    assert detector.is_duplicate(t20i_yaml_path) is True


def test_duplicate_detector_different_files(t20i_yaml_path: Path, odi_yaml_path: Path):
    """Different files are not considered duplicates."""
    detector = DuplicateDetector()
    assert detector.is_duplicate(t20i_yaml_path) is False
    assert detector.is_duplicate(odi_yaml_path) is False


def test_all_errors_collected():
    """All validation errors are collected before returning (non-fail-fast)."""
    info = _info(team1="", team2="")  # missing teams
    deliveries = [_delivery(runs_batter=-1, over=i // 6, ball=i % 6) for i in range(3)]  # too few + negative runs
    match = ParsedMatch(match_info=info, deliveries=deliveries)
    is_valid, errors = validator.validate_match(match)
    assert is_valid is False
    # Should have at least 2 distinct errors (teams + deliveries count)
    assert len(errors) >= 2
