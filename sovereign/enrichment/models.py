"""Enrichment data models for Sovereign Cricket Analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sovereign.ingestion.models import RawDelivery


@dataclass
class EnrichedDelivery(RawDelivery):
    """A :class:`RawDelivery` extended with ball-by-ball context fields."""

    # Score state at the moment this ball was bowled
    team_score_at_ball: int = 0
    wickets_fallen: int = 0
    wickets_in_hand: int = 11
    partnership_runs: int = 0
    partnership_balls: int = 0

    # Chase context (None in first innings)
    target: Optional[int] = None
    required_runs: Optional[int] = None
    balls_remaining: Optional[int] = None

    # Rate context
    current_run_rate: Optional[float] = None
    required_run_rate: Optional[float] = None

    # Phase / probability
    phase_label: str = "unknown"
    win_probability: float = 0.5

    # SPI (filled in after SPICalculator runs)
    spi_total: Optional[float] = None


@dataclass
class SPIComponents:
    """All SPI components and the weighted total for a single delivery.

    All component values are clamped to ``[0, 10]``.
    """

    run_pressure: float = 0.0
    wicket_criticality: float = 0.0
    match_phase: float = 0.0
    tournament_stage: float = 0.0
    opposition_quality: float = 0.0
    total: float = 0.0

    @property
    def tier(self) -> str:
        """Pressure tier label based on total SPI."""
        if self.total < 3.0:
            return "low"
        if self.total < 6.0:
            return "medium"
        if self.total < 8.0:
            return "high"
        return "extreme"
