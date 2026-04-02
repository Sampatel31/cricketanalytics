"""Season-by-season archetype tracking and transition detection."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import polars as pl

from sovereign.intelligence.models import ArchetypeTransition, SovereignAlert
from sovereign.intelligence.utils import cosine_similarity, nearest_archetype

logger = logging.getLogger(__name__)


class ArchetypeTracker:
    """Assign archetypes to players and detect season-to-season transitions.

    Args:
        alert_confidence_threshold: Minimum confidence for generating a
            high-severity :class:`SovereignAlert` on transition.
    """

    def __init__(self, alert_confidence_threshold: float = 0.9) -> None:
        self._alert_threshold = alert_confidence_threshold
        # In-memory store: player_id → {season → archetype_code}
        self._assignments: dict[str, dict[str, str]] = {}
        # In-memory store: player_id → {season → feature vector (np.ndarray)}
        self._profiles: dict[str, dict[str, np.ndarray]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assign_archetypes(
        self,
        features_df: pl.DataFrame,
        archetypes: list,
        season: str,
    ) -> dict[str, str]:
        """Assign each player in *features_df* to the nearest archetype.

        Args:
            features_df: DataFrame with ``player_id`` column and 54 feature
                columns.
            archetypes: List of :class:`~sovereign.intelligence.models.Archetype`
                instances.
            season: Season identifier (e.g. ``"2024"``).

        Returns:
            Mapping from ``player_id`` to ``archetype_code``.
        """
        if not archetypes:
            logger.warning("No archetypes provided; returning empty assignment")
            return {}

        # Build centroid matrix from the 54D feature centroids
        feat_keys = list(archetypes[0].centroid_features.keys())
        centroids = np.array(
            [[a.centroid_features.get(k, 0.0) for k in feat_keys] for a in archetypes]
        )

        _META = {"player_id", "format_type", "season", "confidence_weight", "innings_count"}
        feat_cols = [c for c in features_df.columns if c not in _META]

        assignments: dict[str, str] = {}
        player_ids = features_df["player_id"].to_list()
        feat_np = features_df.select(feat_cols).to_numpy().astype(np.float64)

        for i, player_id in enumerate(player_ids):
            player_vec = feat_np[i]
            idx, _ = nearest_archetype(player_vec, centroids)
            code = archetypes[idx].code
            assignments[player_id] = code

            # Store profile for transition detection
            if player_id not in self._assignments:
                self._assignments[player_id] = {}
            self._assignments[player_id][season] = code

            if player_id not in self._profiles:
                self._profiles[player_id] = {}
            self._profiles[player_id][season] = player_vec

        logger.info(
            "Assigned %d players to archetypes for season %s", len(assignments), season
        )
        return assignments

    def detect_transitions(
        self,
        player_id: str,
        previous_season: str,
        current_season: str,
        archetypes: list,
    ) -> Optional[ArchetypeTransition]:
        """Detect whether a player has changed archetype between two seasons.

        Args:
            player_id: Unique player identifier.
            previous_season: Earlier season identifier.
            current_season: Later season identifier.
            archetypes: Current list of :class:`Archetype` instances.

        Returns:
            An :class:`ArchetypeTransition` if the archetype changed, else None.
        """
        prev_map = self._assignments.get(player_id, {})
        arc_from = prev_map.get(previous_season)
        arc_to = prev_map.get(current_season)

        if arc_from is None or arc_to is None:
            logger.debug(
                "Cannot detect transition for %s: missing season data", player_id
            )
            return None

        if arc_from == arc_to:
            return None

        # Compute confidence
        confidence = self._compute_transition_confidence(
            player_id, current_season, arc_to, archetypes
        )
        return ArchetypeTransition(
            player_id=player_id,
            season_from=previous_season,
            season_to=current_season,
            archetype_from=arc_from,
            archetype_to=arc_to,
            confidence=confidence,
        )

    def generate_alerts(
        self,
        transitions: list[ArchetypeTransition],
    ) -> list[SovereignAlert]:
        """Generate :class:`SovereignAlert` records from transitions.

        Args:
            transitions: List of detected transitions.

        Returns:
            List of :class:`SovereignAlert` instances.
        """
        alerts: list[SovereignAlert] = []
        for t in transitions:
            severity = (
                "high" if t.confidence >= self._alert_threshold
                else "medium" if t.confidence >= 0.7
                else "low"
            )
            alert = SovereignAlert(
                alert_type="archetype_shift",
                player_id=t.player_id,
                archetype_code=t.archetype_to,
                message=(
                    f"Player {t.player_id} shifted from {t.archetype_from} to "
                    f"{t.archetype_to} (season {t.season_from}→{t.season_to}, "
                    f"confidence={t.confidence:.2f})"
                ),
                severity=severity,
            )
            alerts.append(alert)
        return alerts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_transition_confidence(
        self,
        player_id: str,
        current_season: str,
        new_archetype_code: str,
        archetypes: list,
    ) -> float:
        """Compute how well the player's new profile fits the new archetype.

        Returns a similarity score in [0, 1].
        """
        profile = self._profiles.get(player_id, {}).get(current_season)
        if profile is None:
            return 0.5  # default uncertainty

        # Find the new archetype
        new_arc = next((a for a in archetypes if a.code == new_archetype_code), None)
        if new_arc is None:
            return 0.5

        feat_keys = list(new_arc.centroid_features.keys())
        centroid = np.array([new_arc.centroid_features.get(k, 0.0) for k in feat_keys])

        # Align profile length to centroid
        n = min(len(profile), len(centroid))
        sim = cosine_similarity(profile[:n], centroid[:n])
        # Normalize from [-1,1] to [0,1]
        return max(0.0, min(1.0, (sim + 1.0) / 2.0))
