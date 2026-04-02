"""Tests for MatchClassifier (sovereign/ingestion/classifier.py)."""

from __future__ import annotations

import pytest

from sovereign.ingestion.classifier import MatchClassifier

clf = MatchClassifier()


# ---------------------------------------------------------------------------
# Franchise rejection tests
# ---------------------------------------------------------------------------

def test_ipl_rejected():
    """IPL should be rejected with a descriptive reason."""
    result = clf.classify({
        "match_type": "T20",
        "event": {"name": "Indian Premier League", "stage": "group"},
        "teams": ["MI", "CSK"],
        "dates": ["2023-04-10"],
    })
    assert result.is_rejected is True
    assert result.rejection_reason is not None
    assert "Indian Premier League" in result.rejection_reason or "IPL" in result.rejection_reason.upper()


def test_bbl_rejected():
    """Big Bash League should be rejected."""
    result = clf.classify({
        "match_type": "T20",
        "event": {"name": "Big Bash League", "stage": "final"},
        "teams": ["Sydney Sixers", "Melbourne Stars"],
        "dates": ["2023-01-20"],
    })
    assert result.is_rejected is True


def test_psl_rejected():
    """PSL should be rejected."""
    result = clf.classify({
        "match_type": "T20",
        "event": {"name": "Pakistan Super League"},
        "teams": ["Karachi Kings", "Lahore Qalandars"],
        "dates": ["2023-02-15"],
    })
    assert result.is_rejected is True


# ---------------------------------------------------------------------------
# International acceptance tests
# ---------------------------------------------------------------------------

def test_t20i_accepted():
    """T20I matches should be accepted and classified as T20I."""
    result = clf.classify({
        "match_type": "T20I",
        "event": {"name": "ICC T20 World Cup 2022"},
        "teams": ["India", "Pakistan"],
        "dates": ["2022-10-23"],
        "gender": "male",
    })
    assert result.is_rejected is False
    assert result.format_type == "T20I"


def test_odi_accepted():
    """ODI matches should be accepted."""
    result = clf.classify({
        "match_type": "ODI",
        "event": {"name": "ICC World Cup 2023"},
        "teams": ["India", "Australia"],
        "dates": ["2023-11-19"],
        "gender": "male",
    })
    assert result.is_rejected is False
    assert result.format_type == "ODI"


# ---------------------------------------------------------------------------
# Domestic acceptance tests
# ---------------------------------------------------------------------------

def test_ranji_accepted():
    """Ranji Trophy (first-class) should be accepted."""
    result = clf.classify({
        "match_type": "FC",
        "event": {"name": "Ranji Trophy 2023-24"},
        "teams": ["Mumbai", "Karnataka"],
        "dates": ["2023-12-01"],
        "gender": "male",
    })
    assert result.is_rejected is False
    assert result.format_type == "FIRST_CLASS"


def test_smat_accepted():
    """Syed Mushtaq Ali Trophy should be accepted as T20."""
    result = clf.classify({
        "match_type": "T20",
        "event": {"name": "Syed Mushtaq Ali Trophy 2023"},
        "teams": ["Maharashtra", "Bengal"],
        "dates": ["2023-10-10"],
        "gender": "male",
    })
    assert result.is_rejected is False
    assert result.format_type == "T20"


# ---------------------------------------------------------------------------
# Women's classification
# ---------------------------------------------------------------------------

def test_womens_t20i_classified():
    """Women's T20I should be classified as WOMENS_T20I."""
    result = clf.classify({
        "match_type": "T20I",
        "event": {"name": "ICC Women's T20 World Cup"},
        "teams": ["India Women", "Australia Women"],
        "dates": ["2023-02-26"],
        "gender": "female",
    })
    assert result.is_rejected is False
    assert result.format_type == "WOMENS_T20I"


# ---------------------------------------------------------------------------
# Schema version detection
# ---------------------------------------------------------------------------

def test_schema_version_v2():
    """Event as dict → schema v2."""
    result = clf.classify({
        "match_type": "T20I",
        "event": {"name": "Asia Cup"},
        "teams": ["India", "Sri Lanka"],
        "dates": ["2023-09-01"],
    })
    assert result.schema_version == 2


def test_schema_version_v1():
    """Event as string → schema v1."""
    result = clf.classify({
        "match_type": "T20I",
        "event": "Asia Cup",
        "teams": ["India", "Sri Lanka"],
        "dates": ["2023-09-01"],
    })
    assert result.schema_version == 1
