"""Sovereign Matching Engine — Phase 4.

Provides franchise DNA building, player homology scoring, fair value
estimation, squad management, and arbitrage detection.
"""

from __future__ import annotations

from sovereign.matching.models import (
    ArchetypeGapAlert,
    ArbitrageError,
    DNABuildError,
    FranchiseDNA,
    OverbidAlert,
    PlayerScore,
    SquadState,
    ValuationError,
)

__all__ = [
    "FranchiseDNA",
    "PlayerScore",
    "SquadState",
    "OverbidAlert",
    "ArchetypeGapAlert",
    "DNABuildError",
    "ValuationError",
    "ArbitrageError",
]
