"""SQLAlchemy ORM models for Sovereign Cricket Analytics.

All 15 tables are defined here with full type annotations, indexes,
foreign-key constraints and audit timestamps.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


# ---------------------------------------------------------------------------
# Utility columns
# ---------------------------------------------------------------------------


def _now() -> datetime:
    """UTC timestamp default used as Python-level column default."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# 1. Players
# ---------------------------------------------------------------------------


class Player(Base):
    """Master player registry."""

    __tablename__ = "players"

    player_id: Mapped[str] = mapped_column(
        String(100), primary_key=True, comment="Unique player slug"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    country: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(
        String(50), comment="batsman / bowler / allrounder / wicketkeeper"
    )
    dob: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    deliveries_batting: Mapped[list["Delivery"]] = relationship(
        back_populates="batter", foreign_keys="Delivery.batter_id"
    )
    deliveries_bowling: Mapped[list["Delivery"]] = relationship(
        back_populates="bowler", foreign_keys="Delivery.bowler_id"
    )
    features: Mapped[list["PlayerFeature"]] = relationship(back_populates="player")
    archetypes: Mapped[list["PlayerArchetype"]] = relationship(back_populates="player")

    __table_args__ = (
        Index("ix_players_country", "country"),
        Index("ix_players_role", "role"),
    )


# ---------------------------------------------------------------------------
# 2. Matches
# ---------------------------------------------------------------------------


class Match(Base):
    """Cricket match metadata."""

    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(
        String(100), primary_key=True, comment="Cricsheet match ID"
    )
    match_date: Mapped[date | None] = mapped_column(Date)
    format: Mapped[str | None] = mapped_column(
        String(20), comment="T20I / ODI / TEST"
    )
    team1: Mapped[str | None] = mapped_column(String(100))
    team2: Mapped[str | None] = mapped_column(String(100))
    venue: Mapped[str | None] = mapped_column(String(200))
    winner: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="match")

    __table_args__ = (
        Index("ix_matches_date", "match_date"),
        Index("ix_matches_format", "format"),
    )


# ---------------------------------------------------------------------------
# 3. Deliveries
# ---------------------------------------------------------------------------


class Delivery(Base):
    """Ball-by-ball delivery records."""

    __tablename__ = "deliveries"

    delivery_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    match_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("matches.match_id", ondelete="CASCADE"),
        nullable=False,
    )
    innings: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    over_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ball_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    batter_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="SET NULL"),
        nullable=True,
    )
    bowler_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="SET NULL"),
        nullable=True,
    )
    non_striker_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="SET NULL"),
    )
    runs_batter: Mapped[int] = mapped_column(SmallInteger, default=0)
    runs_extras: Mapped[int] = mapped_column(SmallInteger, default=0)
    runs_total: Mapped[int] = mapped_column(SmallInteger, default=0)
    wicket: Mapped[bool] = mapped_column(Boolean, default=False)
    wicket_kind: Mapped[str | None] = mapped_column(String(50))
    player_dismissed_id: Mapped[str | None] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="SET NULL"),
    )

    match: Mapped["Match"] = relationship(back_populates="deliveries")
    batter: Mapped["Player | None"] = relationship(
        back_populates="deliveries_batting", foreign_keys=[batter_id]
    )
    bowler: Mapped["Player | None"] = relationship(
        back_populates="deliveries_bowling", foreign_keys=[bowler_id]
    )
    enriched: Mapped["EnrichedBall | None"] = relationship(
        back_populates="delivery", uselist=False
    )

    __table_args__ = (
        Index("ix_deliveries_match_id", "match_id"),
        Index("ix_deliveries_batter_id", "batter_id"),
        Index("ix_deliveries_bowler_id", "bowler_id"),
        Index("ix_deliveries_wicket", "wicket"),
    )


# ---------------------------------------------------------------------------
# 4. Enriched balls
# ---------------------------------------------------------------------------


class EnrichedBall(Base):
    """Context-enriched delivery features (score pressure, RRR, etc.)."""

    __tablename__ = "enriched_balls"

    enriched_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    delivery_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("deliveries.delivery_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    score_at_ball: Mapped[int] = mapped_column(Integer, default=0)
    wickets_fallen: Mapped[int] = mapped_column(SmallInteger, default=0)
    balls_remaining: Mapped[int] = mapped_column(SmallInteger, default=0)
    target: Mapped[int | None] = mapped_column(Integer)
    required_run_rate: Mapped[float | None] = mapped_column(Float)
    current_run_rate: Mapped[float | None] = mapped_column(Float)
    pressure_index: Mapped[float | None] = mapped_column(Float)
    phase: Mapped[str | None] = mapped_column(
        String(20), comment="powerplay / middle / death"
    )

    delivery: Mapped["Delivery"] = relationship(back_populates="enriched")

    __table_args__ = (
        Index("ix_enriched_balls_delivery_id", "delivery_id"),
        Index("ix_enriched_balls_phase", "phase"),
    )


# ---------------------------------------------------------------------------
# 5. Player features
# ---------------------------------------------------------------------------


class PlayerFeature(Base):
    """Season-level player feature vectors stored as JSONB."""

    __tablename__ = "player_features"

    feature_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    player_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="Serialised feature vector"
    )
    confidence_weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="features")

    __table_args__ = (
        UniqueConstraint("player_id", "format", "season", name="uq_player_features"),
        Index("ix_player_features_player_id", "player_id"),
        Index("ix_player_features_season", "season"),
        Index("ix_player_features_format", "format"),
    )


# ---------------------------------------------------------------------------
# 6. Archetypes (lookup table)
# ---------------------------------------------------------------------------


class Archetype(Base):
    """Archetype reference table."""

    __tablename__ = "archetypes"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    centroid_features: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        server_default=func.now(),
        onupdate=func.now(),
    )

    player_archetypes: Mapped[list["PlayerArchetype"]] = relationship(
        back_populates="archetype"
    )


# ---------------------------------------------------------------------------
# 7. Player archetypes
# ---------------------------------------------------------------------------


class PlayerArchetype(Base):
    """Season-level archetype assignment for each player."""

    __tablename__ = "player_archetypes"

    assignment_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    player_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    archetype_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("archetypes.code", ondelete="SET NULL"),
        nullable=True,
    )
    archetype_label: Mapped[str | None] = mapped_column(String(200))
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    player: Mapped["Player"] = relationship(back_populates="archetypes")
    archetype: Mapped["Archetype | None"] = relationship(
        back_populates="player_archetypes"
    )

    __table_args__ = (
        UniqueConstraint(
            "player_id", "format", "season", name="uq_player_archetypes"
        ),
        Index("ix_player_archetypes_player_id", "player_id"),
        Index("ix_player_archetypes_season", "season"),
    )


# ---------------------------------------------------------------------------
# 8. Archetype transitions
# ---------------------------------------------------------------------------


class ArchetypeTransition(Base):
    """Record of a player moving between archetypes across seasons."""

    __tablename__ = "archetype_transitions"

    transition_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    player_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    from_archetype: Mapped[str | None] = mapped_column(String(50))
    to_archetype: Mapped[str | None] = mapped_column(String(50))
    season: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_archetype_transitions_player_id", "player_id"),
        Index("ix_archetype_transitions_season", "season"),
    )


# ---------------------------------------------------------------------------
# 9. Sovereign alerts
# ---------------------------------------------------------------------------


class SovereignAlert(Base):
    """Automated system alerts for player performance signals."""

    __tablename__ = "sovereign_alerts"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    player_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="low / medium / high / critical"
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_sovereign_alerts_player_id", "player_id"),
        Index("ix_sovereign_alerts_severity", "severity"),
        Index("ix_sovereign_alerts_resolved", "resolved"),
        Index("ix_sovereign_alerts_created_at", "created_at"),
    )


# ---------------------------------------------------------------------------
# 10. Franchise DNA sessions
# ---------------------------------------------------------------------------


class FranchiseDnaSession(Base):
    """Franchise DNA analysis session."""

    __tablename__ = "franchise_dna_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    franchise_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dna_vector: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    auction_picks: Mapped[list["AuctionPick"]] = relationship(
        back_populates="session"
    )
    squad_balance: Mapped["SquadBalance | None"] = relationship(
        back_populates="session", uselist=False
    )

    __table_args__ = (
        Index("ix_franchise_dna_sessions_franchise_name", "franchise_name"),
        Index("ix_franchise_dna_sessions_created_at", "created_at"),
    )


# ---------------------------------------------------------------------------
# 11. Auction picks
# ---------------------------------------------------------------------------


class AuctionPick(Base):
    """Individual player pick within an auction session."""

    __tablename__ = "auction_picks"

    pick_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("franchise_dna_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    player_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("players.player_id", ondelete="SET NULL"),
        nullable=True,
    )
    price: Mapped[float | None] = mapped_column(Float)
    pick_number: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    session: Mapped["FranchiseDnaSession"] = relationship(
        back_populates="auction_picks"
    )

    __table_args__ = (
        Index("ix_auction_picks_session_id", "session_id"),
        Index("ix_auction_picks_player_id", "player_id"),
    )


# ---------------------------------------------------------------------------
# 12. Squad balance
# ---------------------------------------------------------------------------


class SquadBalance(Base):
    """Archetype balance metrics for a franchise auction session."""

    __tablename__ = "squad_balance"

    balance_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("franchise_dna_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    archetype_balance: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )
    dna_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    session: Mapped["FranchiseDnaSession"] = relationship(
        back_populates="squad_balance"
    )

    __table_args__ = (
        Index("ix_squad_balance_session_id", "session_id"),
    )


# ---------------------------------------------------------------------------
# 13. UMAP models
# ---------------------------------------------------------------------------


class UmapModel(Base):
    """Serialised UMAP reducer models per format."""

    __tablename__ = "umap_models"

    model_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    format_type: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True
    )
    model_data: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, comment="Pickled UMAP model"
    )
    fitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_umap_models_format_type", "format_type"),
    )


# ---------------------------------------------------------------------------
# 14. HDBSCAN clusters
# ---------------------------------------------------------------------------


class HdbscanCluster(Base):
    """Serialised HDBSCAN cluster results per format."""

    __tablename__ = "hdbscan_clusters"

    cluster_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    format_type: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True
    )
    labels: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False, comment="Serialised cluster label array"
    )
    centroids: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_hdbscan_clusters_format_type", "format_type"),
    )


# ---------------------------------------------------------------------------
# 15. Processed files
# ---------------------------------------------------------------------------


class ProcessedFile(Base):
    """Track which Cricsheet files have already been ingested."""

    __tablename__ = "processed_files"

    file_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    filename: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True
    )
    file_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 hex digest"
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    record_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_processed_files_filename", "filename"),
        Index("ix_processed_files_processed_at", "processed_at"),
    )
