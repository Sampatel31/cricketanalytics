"""Squad manager — real-time squad composition tracking.

Maintains squad state during an auction: tracks players locked in,
budget spent, archetype balance, and squad DNA score.  Generates
archetype gap alerts when the auction progresses past a threshold.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sovereign.intelligence.models import Archetype
from sovereign.matching.models import (
    ArchetypeGapAlert,
    FranchiseDNA,
    SquadState,
)


class SquadManager:
    """Track squad composition and generate real-time alerts.

    Args:
        franchise_name: Name of the franchise being managed.
        budget_total: Total available auction budget in crores.
        dna: Franchise DNA vector used to compute squad DNA score.
        archetypes: List of all known ``Archetype`` objects for label
            look-ups and gap detection.
        gap_alert_progress_pct: Auction progress fraction at which gap
            alerts are triggered (default 0.6 = 60%).
    """

    def __init__(
        self,
        franchise_name: str,
        budget_total: float,
        dna: FranchiseDNA,
        archetypes: list[Archetype],
        gap_alert_progress_pct: float = 0.6,
    ) -> None:
        self._franchise_name = franchise_name
        self._budget_total = budget_total
        self._dna = dna
        self._archetypes: dict[str, Archetype] = {a.code: a for a in archetypes}
        self._gap_alert_progress_pct = gap_alert_progress_pct

        # Mutable squad state
        self._squad_id: str = str(uuid.uuid4())
        self._players_locked_in: list[str] = []
        self._budget_spent: float = 0.0
        self._archetype_balance: dict[str, int] = {}

        # Per-player homology scores (populated via add_player)
        self._player_homology: dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def add_player(
        self,
        player_id: str,
        price_paid: float,
        archetype_code: str,
        homology_score: float = 0.0,
    ) -> SquadState:
        """Add a player to the squad and return the updated state.

        Args:
            player_id: Unique identifier of the player.
            price_paid: Amount paid in crores.
            archetype_code: Player's archetype code (e.g. "ARC_001").
            homology_score: Player's cosine similarity to the franchise DNA
                (used to recompute ``squad_dna_score``).

        Returns:
            Updated ``SquadState`` snapshot.
        """
        if player_id not in self._players_locked_in:
            self._players_locked_in.append(player_id)

        self._budget_spent += price_paid
        self._archetype_balance[archetype_code] = (
            self._archetype_balance.get(archetype_code, 0) + 1
        )
        self._player_homology[player_id] = float(homology_score)

        return self.get_squad_state()

    def get_squad_state(self) -> SquadState:
        """Return an immutable snapshot of the current squad state.

        Returns:
            ``SquadState`` with all fields populated from current state.
        """
        squad_dna = self._compute_squad_dna_score()
        return SquadState(
            squad_id=self._squad_id,
            franchise_name=self._franchise_name,
            players_locked_in=list(self._players_locked_in),
            budget_total=self._budget_total,
            budget_spent=self._budget_spent,
            archetype_balance=dict(self._archetype_balance),
            squad_dna_score=squad_dna,
            last_updated=datetime.now(timezone.utc),
        )

    def get_archetype_balance(
        self,
        target_counts: Optional[dict[str, int]] = None,
    ) -> dict[str, dict]:
        """Return archetype balance with optional target comparison.

        Args:
            target_counts: Optional mapping of archetype_code → desired count.
                If provided, each entry includes a ``"target"`` key.

        Returns:
            Dict of the form::

                {
                    "ARC_001": {"current": 1, "target": 2},
                    ...
                }
        """
        all_codes = set(self._archetype_balance.keys())
        if target_counts:
            all_codes |= set(target_counts.keys())

        result: dict[str, dict] = {}
        for code in sorted(all_codes):
            entry: dict = {"current": self._archetype_balance.get(code, 0)}
            if target_counts:
                entry["target"] = target_counts.get(code, 0)
            result[code] = entry
        return result

    def detect_gaps(
        self,
        upcoming_lots: int,
        total_lots: int,
        target_counts: Optional[dict[str, int]] = None,
    ) -> list[ArchetypeGapAlert]:
        """Identify archetype gaps and generate alerts.

        An alert is raised for archetype codes whose current count is
        below *target_counts* and for archetypes with zero players when
        the auction is more than ``gap_alert_progress_pct`` complete.

        Args:
            upcoming_lots: Number of lots still to be auctioned.
            total_lots: Total number of lots in the auction.
            target_counts: Mapping of archetype_code → desired player count.
                Defaults to using target counts of 1 for every known
                archetype if ``None``.

        Returns:
            List of ``ArchetypeGapAlert`` objects, one per gap found.
        """
        if total_lots <= 0:
            return []

        lots_done = total_lots - upcoming_lots
        progress_pct = lots_done / total_lots  # float in [0, 1]

        # Default: alert on any known archetype with 0 players
        effective_targets = target_counts or {
            code: 1 for code in self._archetypes
        }

        alerts: list[ArchetypeGapAlert] = []
        for code, target in effective_targets.items():
            current = self._archetype_balance.get(code, 0)
            if current >= target:
                continue

            # Only raise alert once auction is past the threshold
            if progress_pct < self._gap_alert_progress_pct:
                continue

            archetype = self._archetypes.get(code)
            label = archetype.label if archetype else code
            missing = target - current

            alerts.append(
                ArchetypeGapAlert(
                    archetype_code=code,
                    archetype_label=label,
                    target_count=target,
                    current_count=current,
                    auction_progress_pct=progress_pct,
                    message=(
                        f"Need {missing} more {label} player"
                        f"{'s' if missing > 1 else ''} "
                        f"— {upcoming_lots} lots remaining "
                        f"({progress_pct * 100:.0f}% of auction complete)."
                    ),
                )
            )
        return alerts

    # ------------------------------------------------------------------ #
    # Private helpers                                                       #
    # ------------------------------------------------------------------ #

    def _compute_squad_dna_score(self) -> float:
        """Return the average homology score of all confirmed picks.

        Returns:
            Mean homology score in [0, 1], or 0.0 if squad is empty.
        """
        if not self._player_homology:
            return 0.0
        total = sum(self._player_homology.values())
        return total / len(self._player_homology)
