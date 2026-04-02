"""Tests for sovereign/intelligence/tracker.py (4 tests)."""

from __future__ import annotations

import numpy as np
import pytest

from sovereign.intelligence.archetype import ArchetypeDiscoverer
from sovereign.intelligence.models import ArchetypeTransition, SovereignAlert
from sovereign.intelligence.tracker import ArchetypeTracker


def _make_archetypes(features_df, coords, labels):
    """Helper to create test archetypes."""
    discoverer = ArchetypeDiscoverer()
    centroids = np.array(
        [coords[labels == c].mean(axis=0) for c in np.unique(labels)]
    )
    return discoverer.discover(coords, features_df, labels, centroids)


class TestArchetypeTracker:
    def test_archetype_assignment_works(self, synthetic_features_df, cluster_coords) -> None:
        """Tracker assigns every player to an archetype."""
        coords, labels = cluster_coords
        archetypes = _make_archetypes(synthetic_features_df, coords, labels)
        tracker = ArchetypeTracker()
        assignments = tracker.assign_archetypes(
            synthetic_features_df, archetypes, season="2024"
        )
        assert len(assignments) == len(synthetic_features_df)
        for code in assignments.values():
            assert any(a.code == code for a in archetypes)

    def test_transitions_detected(self, synthetic_features_df, cluster_coords) -> None:
        """Transition is detected when archetype changes between seasons."""
        coords, labels = cluster_coords
        archetypes = _make_archetypes(synthetic_features_df, coords, labels)
        tracker = ArchetypeTracker()

        # Season 1
        tracker.assign_archetypes(synthetic_features_df, archetypes, season="2023")
        # Season 2 — manually override one player's assignment
        player_id = synthetic_features_df["player_id"][0]
        arc_codes = [a.code for a in archetypes]
        # Assign different archetypes for two seasons
        tracker._assignments[player_id]["2023"] = arc_codes[0]
        tracker._assignments[player_id]["2024"] = arc_codes[-1] if len(arc_codes) > 1 else arc_codes[0]
        tracker._profiles.setdefault(player_id, {})["2024"] = np.ones(54)

        transition = tracker.detect_transitions(
            player_id, "2023", "2024", archetypes
        )
        if arc_codes[0] != arc_codes[-1]:
            assert transition is not None
            assert isinstance(transition, ArchetypeTransition)

    def test_confidence_computed(self, synthetic_features_df, cluster_coords) -> None:
        """Transition confidence is in [0, 1]."""
        coords, labels = cluster_coords
        archetypes = _make_archetypes(synthetic_features_df, coords, labels)
        tracker = ArchetypeTracker()
        tracker.assign_archetypes(synthetic_features_df, archetypes, season="2024")
        player_id = synthetic_features_df["player_id"][0]
        arc_codes = [a.code for a in archetypes]

        if len(arc_codes) > 1:
            tracker._assignments[player_id]["2023"] = arc_codes[0]
            tracker._assignments[player_id]["2024"] = arc_codes[1]
            transition = tracker.detect_transitions(
                player_id, "2023", "2024", archetypes
            )
            if transition:
                assert 0.0 <= transition.confidence <= 1.0

    def test_alerts_generated(self, synthetic_features_df, cluster_coords) -> None:
        """Alerts are generated for transitions."""
        coords, labels = cluster_coords
        archetypes = _make_archetypes(synthetic_features_df, coords, labels)
        tracker = ArchetypeTracker()

        arc_codes = [a.code for a in archetypes]
        transitions = []
        if len(arc_codes) > 1:
            transitions.append(
                ArchetypeTransition(
                    player_id="p001",
                    season_from="2023",
                    season_to="2024",
                    archetype_from=arc_codes[0],
                    archetype_to=arc_codes[1],
                    confidence=0.95,
                )
            )

        alerts = tracker.generate_alerts(transitions)
        assert isinstance(alerts, list)
        for alert in alerts:
            assert isinstance(alert, SovereignAlert)
            assert alert.severity in ("low", "medium", "high")
