"""Pydantic data models for the ingestion layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class MatchClassification:
    """Result of classifying a match file."""

    format_type: str
    is_rejected: bool
    rejection_reason: Optional[str]
    schema_version: int  # 1 (pre-2023) or 2 (post-2023)


@dataclass
class MatchInfo:
    """Metadata extracted from a match file."""

    match_id: str
    date: date
    format: str
    team1: str
    team2: str
    venue: Optional[str] = None
    event_name: Optional[str] = None
    event_stage: Optional[str] = None
    gender: str = "male"
    season: Optional[str] = None
    match_type: Optional[str] = None
    overs: Optional[int] = None


@dataclass
class RawDelivery:
    """A single delivery as parsed from the Cricsheet file."""

    batter_id: str
    bowler_id: str
    non_striker_id: str
    batting_team: str
    bowling_team: str
    innings_number: int
    over_number: int
    ball_number: int
    runs_batter: int
    runs_extras: int
    runs_total: int
    is_legal_ball: bool
    is_wicket: bool
    wicket_kind: Optional[str] = None
    player_dismissed_id: Optional[str] = None


@dataclass
class ParsedMatch:
    """A fully parsed match containing metadata and all deliveries."""

    match_info: MatchInfo
    deliveries: list[RawDelivery] = field(default_factory=list)


@dataclass
class IngestStats:
    """Summary statistics from a full ingestion run."""

    total_files: int = 0
    accepted_files: int = 0
    rejected_franchise: int = 0
    failed_files: int = 0
    total_deliveries: int = 0
    total_players_unique: int = 0
    elapsed_seconds: float = 0.0
