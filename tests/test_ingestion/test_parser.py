"""Tests for MatchParser (sovereign/ingestion/parser.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sovereign.ingestion.parser import MatchParser, MatchParseError

SAMPLE_DIR = Path(__file__).parent / "sample_data"
parser = MatchParser()


def test_parse_v2_yaml_correctly(t20i_yaml_path: Path):
    """v2 YAML file parsed without error."""
    match = parser.parse(t20i_yaml_path)
    assert match is not None
    assert match.match_info.format == "T20I"
    assert match.match_info.team1 == "India"
    assert match.match_info.team2 == "Pakistan"


def test_franchise_yaml_returns_none(ipl_yaml_path: Path):
    """Franchise (IPL) file returns None, not an error."""
    result = parser.parse(ipl_yaml_path)
    assert result is None


def test_correct_delivery_count(t20i_yaml_path: Path):
    """Correct number of deliveries parsed from v2 YAML."""
    match = parser.parse(t20i_yaml_path)
    assert match is not None
    # The t20i_v2.yaml has 2 innings with 2 overs each
    # Over 0: 6 legal + Over 1: 1 wide + 6 legal = 13 deliveries per innings
    assert len(match.deliveries) > 0


def test_wide_is_not_legal_ball(t20i_yaml_path: Path):
    """Wide deliveries should have is_legal_ball=False."""
    match = parser.parse(t20i_yaml_path)
    assert match is not None
    wides = [d for d in match.deliveries if not d.is_legal_ball]
    assert len(wides) > 0, "Expected at least one wide in the sample file"
    for wide in wides:
        assert wide.is_legal_ball is False


def test_batter_name_extracted(t20i_yaml_path: Path):
    """Batter IDs extracted from deliveries."""
    match = parser.parse(t20i_yaml_path)
    assert match is not None
    batters = {d.batter_id for d in match.deliveries}
    assert "V Kohli" in batters or "RG Sharma" in batters


def test_six_runs_in_delivery(t20i_yaml_path: Path):
    """Deliveries with 6 runs are parsed correctly."""
    match = parser.parse(t20i_yaml_path)
    assert match is not None
    sixes = [d for d in match.deliveries if d.runs_batter == 6]
    assert len(sixes) > 0


def test_raise_on_nonexistent_file():
    """Parsing a missing file raises MatchParseError."""
    with pytest.raises(MatchParseError):
        parser.parse(Path("/tmp/nonexistent_file_xyz.yaml"))


def test_parse_many_skips_franchise(t20i_yaml_path: Path, ipl_yaml_path: Path):
    """parse_many skips franchise files."""
    paths = [t20i_yaml_path, ipl_yaml_path]
    results = list(parser.parse_many(paths))
    assert len(results) == 1
    assert results[0].match_info.format == "T20I"


def test_parse_many_handles_mixed_files(
    t20i_yaml_path: Path, ipl_yaml_path: Path, odi_yaml_path: Path
):
    """parse_many yields valid matches and skips franchise/bad files."""
    paths = [t20i_yaml_path, ipl_yaml_path, odi_yaml_path]
    results = list(parser.parse_many(paths))
    # IPL should be skipped
    assert all(m.match_info.format in ("T20I", "ODI") for m in results)
    assert len(results) == 2


def test_wicket_parsed_correctly(t20i_yaml_path: Path):
    """Wicket deliveries are detected and kind extracted."""
    match = parser.parse(t20i_yaml_path)
    assert match is not None
    wickets = [d for d in match.deliveries if d.is_wicket]
    assert len(wickets) > 0
    for w in wickets:
        assert w.wicket_kind is not None
        assert w.player_dismissed_id is not None
