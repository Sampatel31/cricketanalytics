"""004_matching_engine — Add matching engine tables for Phase 4.

Adds:
- ``franchise_dna``        — Franchise DNA profiles
- ``player_scores``        — Player homology scores + valuations
- ``squad_state``          — Real-time squad composition snapshots
- ``overbid_alerts``       — Overbid warning records
- ``archetype_gap_alerts`` — Archetype gap warning records

Revision ID: 004
Revises: 003
Create Date: 2024-01-01 03:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create matching engine tables."""

    # ------------------------------------------------------------------
    # franchise_dna
    # ------------------------------------------------------------------
    op.create_table(
        "franchise_dna",
        sa.Column(
            "dna_id",
            sa.String(36),
            primary_key=True,
            comment="UUID identifying this DNA profile",
        ),
        sa.Column(
            "franchise_name", sa.String(200), nullable=False,
            comment="Name of the franchise"
        ),
        sa.Column(
            "dna_mode", sa.String(20), nullable=False,
            comment="Build mode: slider, exemplar, or historical"
        ),
        sa.Column(
            "feature_vector_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="54-dimensional normalized feature vector",
        ),
        sa.Column(
            "target_archetypes_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="'[]'",
            comment="Preferred archetype codes",
        ),
        sa.Column(
            "description", sa.Text(), nullable=False, server_default="''",
            comment="Mode-specific description of DNA construction"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_franchise_dna_franchise_name", "franchise_dna", ["franchise_name"])
    op.create_index("ix_franchise_dna_dna_mode", "franchise_dna", ["dna_mode"])
    op.create_index("ix_franchise_dna_created_at", "franchise_dna", ["created_at"])

    # ------------------------------------------------------------------
    # player_scores
    # ------------------------------------------------------------------
    op.create_table(
        "player_scores",
        sa.Column(
            "score_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "player_id", sa.String(100), nullable=False,
            comment="Unique player identifier"
        ),
        sa.Column(
            "dna_id",
            sa.String(36),
            sa.ForeignKey("franchise_dna.dna_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("homology_score", sa.Float(), nullable=False,
                  comment="Cosine similarity to franchise DNA [0, 1]"),
        sa.Column("archetype_bonus", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("confidence_weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("fair_value", sa.Float(), nullable=False, server_default="0.0",
                  comment="Estimated fair value in crores"),
        sa.Column("market_price", sa.Float(), nullable=False, server_default="0.0",
                  comment="Current market price in crores"),
        sa.Column("arbitrage_gap", sa.Float(), nullable=False, server_default="0.0",
                  comment="fair_value minus market_price"),
        sa.Column("arbitrage_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("recommendation", sa.String(10), nullable=False, server_default="'NEUTRAL'"),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_player_scores_player_id", "player_scores", ["player_id"])
    op.create_index("ix_player_scores_dna_id", "player_scores", ["dna_id"])
    op.create_index("ix_player_scores_recommendation", "player_scores", ["recommendation"])
    op.create_index("ix_player_scores_homology_score", "player_scores", ["homology_score"])

    # ------------------------------------------------------------------
    # squad_state
    # ------------------------------------------------------------------
    op.create_table(
        "squad_state",
        sa.Column(
            "squad_id", sa.String(36), primary_key=True,
            comment="UUID identifying this squad snapshot"
        ),
        sa.Column("franchise_name", sa.String(200), nullable=False),
        sa.Column(
            "players_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="'[]'",
            comment="List of player_ids locked in",
        ),
        sa.Column("budget_total", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("budget_spent", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "archetype_balance_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="'{}'",
            comment="archetype_code → count mapping",
        ),
        sa.Column("squad_dna_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_squad_state_franchise_name", "squad_state", ["franchise_name"])
    op.create_index("ix_squad_state_last_updated", "squad_state", ["last_updated"])

    # ------------------------------------------------------------------
    # overbid_alerts
    # ------------------------------------------------------------------
    op.create_table(
        "overbid_alerts",
        sa.Column(
            "alert_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column("player_id", sa.String(100), nullable=False),
        sa.Column("squad_id", sa.String(36),
                  sa.ForeignKey("squad_state.squad_id", ondelete="CASCADE"),
                  nullable=True),
        sa.Column("current_bid", sa.Float(), nullable=False),
        sa.Column("max_bid_ceiling", sa.Float(), nullable=False),
        sa.Column("overpay_amount", sa.Float(), nullable=False),
        sa.Column("overpay_pct", sa.Float(), nullable=False),
        sa.Column(
            "alternatives_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="'[]'",
        ),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_overbid_alerts_player_id", "overbid_alerts", ["player_id"])
    op.create_index("ix_overbid_alerts_severity", "overbid_alerts", ["severity"])
    op.create_index("ix_overbid_alerts_created_at", "overbid_alerts", ["created_at"])

    # ------------------------------------------------------------------
    # archetype_gap_alerts
    # ------------------------------------------------------------------
    op.create_table(
        "archetype_gap_alerts",
        sa.Column(
            "alert_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column("squad_id", sa.String(36),
                  sa.ForeignKey("squad_state.squad_id", ondelete="CASCADE"),
                  nullable=True),
        sa.Column("archetype_code", sa.String(50), nullable=False),
        sa.Column("archetype_label", sa.String(200), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("current_count", sa.Integer(), nullable=False),
        sa.Column("auction_progress_pct", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_archetype_gap_alerts_squad_id", "archetype_gap_alerts", ["squad_id"]
    )
    op.create_index(
        "ix_archetype_gap_alerts_archetype_code",
        "archetype_gap_alerts",
        ["archetype_code"],
    )
    op.create_index(
        "ix_archetype_gap_alerts_created_at",
        "archetype_gap_alerts",
        ["created_at"],
    )


def downgrade() -> None:
    """Drop all tables added in this migration (in reverse FK order)."""
    op.drop_table("archetype_gap_alerts")
    op.drop_table("overbid_alerts")
    op.drop_table("squad_state")
    op.drop_table("player_scores")
    op.drop_table("franchise_dna")
