"""Tests for ContextBuilder (sovereign/enrichment/context.py)."""

from __future__ import annotations

from sovereign.enrichment.context import ContextBuilder, _phase_label
from sovereign.ingestion.models import MatchInfo
from tests.test_enrichment.conftest import make_delivery


def test_first_innings_has_no_rrr(t20i_match_info: MatchInfo):
    """RRR is None in the first innings (no target exists)."""
    builder = ContextBuilder(t20i_match_info)
    state: dict = {}
    d = make_delivery(innings=1, over=5, ball=0)
    ctx = builder.build_context(d, state)
    assert ctx.required_run_rate is None


def test_second_innings_rrr_computed(t20i_match_info: MatchInfo):
    """RRR is computed in the second innings."""
    builder = ContextBuilder(t20i_match_info)
    state: dict = {}

    # Build up first innings: score 150 in 120 legal balls
    for i in range(20):
        d = make_delivery(innings=1, over=i, ball=0, runs_batter=7)
        builder.build_context(d, state)

    # Second innings delivery
    d2 = make_delivery(innings=2, over=0, ball=0, runs_batter=1)
    ctx = builder.build_context(d2, state)

    # Target = 141 (first innings score + 1), some balls played
    assert ctx.required_run_rate is not None
    assert ctx.required_run_rate > 0


def test_partnership_resets_on_wicket(t20i_match_info: MatchInfo):
    """Partnership runs and balls reset to 0 after a wicket falls."""
    builder = ContextBuilder(t20i_match_info)
    state: dict = {}

    # Build partnership of 10 runs
    for _ in range(5):
        d = make_delivery(innings=1, runs_batter=2)
        builder.build_context(d, state)

    # Wicket delivery
    wicket_d = make_delivery(innings=1, over=1, is_wicket=True, runs_batter=0)
    ctx_after_wicket = builder.build_context(wicket_d, state)

    # Next delivery – partnership should be reset
    next_d = make_delivery(innings=1, over=2)
    ctx_next = builder.build_context(next_d, state)
    assert ctx_next.partnership_runs == 0
    assert ctx_next.partnership_balls == 0


def test_wickets_in_hand_correct(t20i_match_info: MatchInfo):
    """wickets_in_hand = 11 - wickets_fallen."""
    builder = ContextBuilder(t20i_match_info)
    state: dict = {}

    # Three wickets
    for _ in range(3):
        d = make_delivery(innings=1, is_wicket=True)
        builder.build_context(d, state)

    d = make_delivery(innings=1, over=1)
    ctx = builder.build_context(d, state)
    assert ctx.wickets_fallen == 3
    assert ctx.wickets_in_hand == 8


def test_balls_remaining_counts_legal_balls(t20i_match_info: MatchInfo):
    """balls_remaining decrements only for legal deliveries."""
    builder = ContextBuilder(t20i_match_info)
    state: dict = {}

    # Deliver 6 legal balls
    for i in range(6):
        d = make_delivery(innings=1, over=0, ball=i, is_legal=True)
        builder.build_context(d, state)

    # Deliver 2 wides (not legal)
    for i in range(2):
        d = make_delivery(innings=1, over=1, ball=i, is_legal=False, runs_extras=1)
        builder.build_context(d, state)

    d = make_delivery(innings=1, over=1, ball=2)
    ctx = builder.build_context(d, state)
    # 120 - 6 = 114 legal balls remaining (wides don't count)
    assert ctx.balls_remaining == 114


def test_phase_label_t20_powerplay():
    """Over 0-5 is powerplay in T20I."""
    assert _phase_label("T20I", 0) == "powerplay"
    assert _phase_label("T20I", 5) == "powerplay"


def test_phase_label_t20_death():
    """Over 16-20 is death in T20I (0-indexed over 15-19)."""
    assert _phase_label("T20I", 15) == "death"
    assert _phase_label("T20I", 19) == "death"


def test_phase_label_odi():
    """ODI phase boundaries."""
    assert _phase_label("ODI", 0) == "powerplay"
    assert _phase_label("ODI", 9) == "powerplay"
    assert _phase_label("ODI", 10) == "middle"
    assert _phase_label("ODI", 39) == "middle"
    assert _phase_label("ODI", 40) == "death"
    assert _phase_label("ODI", 49) == "death"


def test_win_probability_in_range(t20i_match_info: MatchInfo):
    """win_probability is always in [0, 1]."""
    builder = ContextBuilder(t20i_match_info)
    state: dict = {}
    for i in range(30):
        d = make_delivery(innings=1, over=i // 6, ball=i % 6, runs_batter=5)
        builder.build_context(d, state)
    for i in range(30):
        d2 = make_delivery(innings=2, over=i // 6, ball=i % 6, runs_batter=4)
        ctx = builder.build_context(d2, state)
        assert 0.0 <= ctx.win_probability <= 1.0


def test_test_cricket_handled(test_match_info: MatchInfo):
    """Test cricket doesn't crash when balls_remaining is None."""
    builder = ContextBuilder(test_match_info)
    state: dict = {}
    d = make_delivery(innings=1, over=50, ball=0)
    ctx = builder.build_context(d, state)
    # Test cricket has no balls_remaining
    assert ctx.balls_remaining is None
    assert ctx.required_run_rate is None
