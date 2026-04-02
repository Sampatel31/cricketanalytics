"""Tests for SPICalculator (sovereign/enrichment/spi.py)."""

from __future__ import annotations

import pytest

from sovereign.config.settings import FormatType, settings
from sovereign.enrichment.spi import (
    SPICalculator,
    _elo_to_oq,
    _tournament_stage_score,
    phase_label,
    spi_calculator,
)
from tests.test_enrichment.conftest import make_enriched

calc = SPICalculator()


# ---------------------------------------------------------------------------
# Component range tests
# ---------------------------------------------------------------------------

def test_all_components_in_range():
    """All SPI components must be in [0, 10]."""
    ctx = make_enriched()
    components = calc.compute(ctx)
    for attr in ("run_pressure", "wicket_criticality", "match_phase", "tournament_stage", "opposition_quality"):
        val = getattr(components, attr)
        assert 0.0 <= val <= 10.0, f"{attr}={val} out of range"


def test_total_clamped():
    """Total SPI must be in [0, 10]."""
    ctx = make_enriched(rrr=20.0, crr=2.0, wickets_fallen=9, phase="death")
    components = calc.compute(ctx)
    assert 0.0 <= components.total <= 10.0


def test_final_death_over_high_spi():
    """Final overs in high-pressure chase should give high SPI."""
    ctx = make_enriched(
        innings=2,
        over=19,
        wickets_fallen=7,
        team_score=160,
        target=180,
        rrr=20.0,
        crr=8.0,
        phase="death",
        balls_remaining=6,
    )
    components = calc.compute_with_stage(ctx, event_stage="final", opposition_elo=1700.0)
    # High pressure scenario: should be ≥ 6 (high tier)
    assert components.total >= 6.0


def test_low_pressure_gives_low_spi():
    """First innings powerplay, comfortable run rate → low SPI."""
    ctx = make_enriched(
        innings=1,
        over=0,
        wickets_fallen=0,
        team_score=20,
        target=None,
        rrr=None,
        crr=8.0,
        phase="powerplay",
        balls_remaining=120,
    )
    # Remove second-innings fields
    ctx.target = None
    ctx.required_runs = None
    ctx.required_run_rate = None
    ctx.innings_number = 1
    components = calc.compute_with_stage(ctx, event_stage="group", opposition_elo=1300.0)
    assert components.total < 8.0  # should not be extreme


# ---------------------------------------------------------------------------
# Tier label tests
# ---------------------------------------------------------------------------

def test_tier_low():
    """SPI < 3 → tier == 'low'."""
    from sovereign.enrichment.models import SPIComponents
    c = SPIComponents(total=2.5)
    assert c.tier == "low"


def test_tier_medium():
    from sovereign.enrichment.models import SPIComponents
    c = SPIComponents(total=4.5)
    assert c.tier == "medium"


def test_tier_high():
    from sovereign.enrichment.models import SPIComponents
    c = SPIComponents(total=7.0)
    assert c.tier == "high"


def test_tier_extreme():
    from sovereign.enrichment.models import SPIComponents
    c = SPIComponents(total=9.0)
    assert c.tier == "extreme"


# ---------------------------------------------------------------------------
# Phase label tests
# ---------------------------------------------------------------------------

def test_phase_labels_t20():
    assert phase_label("T20I", 0) == "powerplay"
    assert phase_label("T20I", 10) == "middle"
    assert phase_label("T20I", 19) == "death"


def test_phase_labels_odi():
    assert phase_label("ODI", 9) == "powerplay"
    assert phase_label("ODI", 25) == "middle"
    assert phase_label("ODI", 48) == "death"


# ---------------------------------------------------------------------------
# ELO tests
# ---------------------------------------------------------------------------

def test_higher_elo_gives_higher_oq():
    """Higher ELO → higher opposition quality score."""
    oq_low = _elo_to_oq(1300.0)
    oq_high = _elo_to_oq(1700.0)
    assert oq_high > oq_low


def test_unknown_elo_defaults_to_5():
    """None ELO → 5.0 opposition quality."""
    assert _elo_to_oq(None) == 5.0


# ---------------------------------------------------------------------------
# Tournament stage tests
# ---------------------------------------------------------------------------

def test_final_stage_higher_than_group():
    """Final stage score > group stage score."""
    assert _tournament_stage_score("final") > _tournament_stage_score("group")


def test_final_stage_score():
    assert _tournament_stage_score("final") == 10.0


def test_semifinal_stage_score():
    assert _tournament_stage_score("semi-final") == 8.0


# ---------------------------------------------------------------------------
# Weight sum test
# ---------------------------------------------------------------------------

def test_all_weights_sum_to_one():
    """SPI weight profiles must sum to 1.0 for all formats."""
    for fmt in FormatType:
        w = settings.spi_weights(fmt)
        total = (
            w.run_pressure
            + w.wicket_criticality
            + w.match_phase
            + w.tournament_stage
            + w.opposition_quality
        )
        assert abs(total - 1.0) < 1e-6, f"Weights for {fmt} sum to {total}"


# ---------------------------------------------------------------------------
# First innings RP proxy
# ---------------------------------------------------------------------------

def test_first_innings_rp_proxy():
    """First innings RP uses a proxy (not None) and is in [0, 10]."""
    ctx = make_enriched(innings=1, rrr=None, crr=6.0, phase="middle")
    ctx.required_run_rate = None
    ctx.target = None
    ctx.required_runs = None
    ctx.innings_number = 1
    components = calc.compute(ctx)
    assert 0.0 <= components.run_pressure <= 10.0


def test_rrr_none_handled():
    """SPICalculator handles None RRR gracefully."""
    ctx = make_enriched(innings=1)
    ctx.required_run_rate = None
    ctx.target = None
    ctx.innings_number = 1
    # Should not raise
    components = calc.compute(ctx)
    assert components is not None
    assert 0.0 <= components.total <= 10.0


def test_singleton_available():
    """Module-level spi_calculator singleton is accessible."""
    assert spi_calculator is not None
    ctx = make_enriched()
    result = spi_calculator.compute(ctx)
    assert 0.0 <= result.total <= 10.0
