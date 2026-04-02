"""Tests for sovereign/matching/squad.py (5 tests)."""

from __future__ import annotations

import pytest

from sovereign.matching.models import ArchetypeGapAlert, SquadState
from sovereign.matching.squad import SquadManager

from tests.test_matching.conftest import make_archetype_objects, make_franchise_dna


@pytest.fixture
def manager() -> SquadManager:
    """SquadManager for 'Test Franchise' with budget 100 crores."""
    return SquadManager(
        franchise_name="Test Franchise",
        budget_total=100.0,
        dna=make_franchise_dna(),
        archetypes=make_archetype_objects(),
        gap_alert_progress_pct=0.6,
    )


class TestSquadStateUpdatedOnAdd:
    """add_player updates squad state correctly."""

    def test_player_added_to_locked_in(self, manager: SquadManager) -> None:
        """Added player_id should appear in players_locked_in."""
        state = manager.add_player("p001", 10.0, "ARC_001", homology_score=0.8)
        assert "p001" in state.players_locked_in

    def test_squad_state_type(self, manager: SquadManager) -> None:
        """add_player should return a SquadState instance."""
        state = manager.add_player("p002", 5.0, "ARC_002", homology_score=0.6)
        assert isinstance(state, SquadState)


class TestBudgetTracking:
    """Budget tracking is accurate after multiple additions."""

    def test_budget_spent_accumulates(self, manager: SquadManager) -> None:
        """budget_spent should accumulate across multiple add_player calls."""
        manager.add_player("p001", 15.0, "ARC_001", homology_score=0.7)
        manager.add_player("p002", 20.0, "ARC_002", homology_score=0.6)
        state = manager.get_squad_state()

        assert state.budget_spent == pytest.approx(35.0)
        assert state.budget_total == pytest.approx(100.0)

    def test_budget_remaining_calculable(self, manager: SquadManager) -> None:
        """Remaining budget = total − spent should be computable from state."""
        manager.add_player("p001", 40.0, "ARC_001", homology_score=0.5)
        state = manager.get_squad_state()
        remaining = state.budget_total - state.budget_spent
        assert remaining == pytest.approx(60.0)


class TestArchetypeBalance:
    """Archetype balance counts are correct."""

    def test_archetype_counts_correct(self, manager: SquadManager) -> None:
        """Archetype balance should reflect the number of players added per archetype."""
        manager.add_player("p001", 10.0, "ARC_001", homology_score=0.8)
        manager.add_player("p002", 10.0, "ARC_001", homology_score=0.7)
        manager.add_player("p003", 10.0, "ARC_002", homology_score=0.6)

        balance = manager.get_archetype_balance()
        assert balance["ARC_001"]["current"] == 2
        assert balance["ARC_002"]["current"] == 1

    def test_archetype_balance_with_targets(self, manager: SquadManager) -> None:
        """Balance with targets shows both current and target counts."""
        manager.add_player("p001", 10.0, "ARC_001", homology_score=0.8)
        targets = {"ARC_001": 2, "ARC_003": 1}
        balance = manager.get_archetype_balance(target_counts=targets)

        assert balance["ARC_001"]["target"] == 2
        assert balance["ARC_001"]["current"] == 1
        assert balance["ARC_003"]["target"] == 1
        assert balance["ARC_003"]["current"] == 0


class TestGapDetection:
    """detect_gaps generates alerts for underrepresented archetypes."""

    def test_gap_alert_triggered_after_60_pct(self, manager: SquadManager) -> None:
        """Gaps should be alerted when auction progress > 60%."""
        # Add players for ARC_001 and ARC_002 but not ARC_003
        manager.add_player("p001", 10.0, "ARC_001", homology_score=0.8)
        manager.add_player("p002", 10.0, "ARC_002", homology_score=0.6)

        # 70% through auction (7/10 lots done)
        alerts = manager.detect_gaps(
            upcoming_lots=3,
            total_lots=10,
            target_counts={"ARC_001": 1, "ARC_002": 1, "ARC_003": 1},
        )

        gap_codes = {a.archetype_code for a in alerts}
        assert "ARC_003" in gap_codes
        # ARC_001 and ARC_002 are satisfied
        assert "ARC_001" not in gap_codes
        assert "ARC_002" not in gap_codes

    def test_no_gap_alert_before_threshold(self, manager: SquadManager) -> None:
        """No gap alerts should be generated before the progress threshold."""
        # 30% through auction (3/10 lots done)
        alerts = manager.detect_gaps(
            upcoming_lots=7,
            total_lots=10,
            target_counts={"ARC_001": 2},
        )
        assert alerts == []

    def test_gap_alert_is_archetype_gap_alert(self, manager: SquadManager) -> None:
        """Returned alerts must be ArchetypeGapAlert instances."""
        alerts = manager.detect_gaps(
            upcoming_lots=2,
            total_lots=10,
            target_counts={"ARC_001": 1},
        )
        for alert in alerts:
            assert isinstance(alert, ArchetypeGapAlert)


class TestEdgeCases:
    """Edge cases for squad management."""

    def test_duplicate_add_does_not_double_count(
        self, manager: SquadManager
    ) -> None:
        """Adding the same player twice should not add them twice to locked_in."""
        manager.add_player("p001", 10.0, "ARC_001", homology_score=0.8)
        state = manager.add_player("p001", 0.0, "ARC_001", homology_score=0.8)
        assert state.players_locked_in.count("p001") == 1

    def test_squad_dna_score_is_average_homology(
        self, manager: SquadManager
    ) -> None:
        """squad_dna_score should be the mean homology of all locked-in players."""
        manager.add_player("p001", 10.0, "ARC_001", homology_score=0.8)
        manager.add_player("p002", 10.0, "ARC_002", homology_score=0.6)
        state = manager.get_squad_state()
        assert state.squad_dna_score == pytest.approx(0.7, rel=1e-6)

    def test_empty_squad_dna_score_zero(self, manager: SquadManager) -> None:
        """Empty squad should have squad_dna_score of 0.0."""
        state = manager.get_squad_state()
        assert state.squad_dna_score == pytest.approx(0.0)

    def test_zero_total_lots_no_alerts(self, manager: SquadManager) -> None:
        """detect_gaps with total_lots=0 should return an empty list."""
        alerts = manager.detect_gaps(upcoming_lots=0, total_lots=0)
        assert alerts == []
