"""001_initial_schema - Create core tables.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create players, matches, deliveries, archetypes, processed_files tables."""

    # ------------------------------------------------------------------
    # players
    # ------------------------------------------------------------------
    op.create_table(
        "players",
        sa.Column("player_id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_players_country", "players", ["country"])
    op.create_index("ix_players_role", "players", ["role"])

    # ------------------------------------------------------------------
    # matches
    # ------------------------------------------------------------------
    op.create_table(
        "matches",
        sa.Column("match_id", sa.String(100), primary_key=True),
        sa.Column("match_date", sa.Date(), nullable=True),
        sa.Column("format", sa.String(20), nullable=True),
        sa.Column("team1", sa.String(100), nullable=True),
        sa.Column("team2", sa.String(100), nullable=True),
        sa.Column("venue", sa.String(200), nullable=True),
        sa.Column("winner", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_matches_date", "matches", ["match_date"])
    op.create_index("ix_matches_format", "matches", ["format"])

    # ------------------------------------------------------------------
    # deliveries
    # ------------------------------------------------------------------
    op.create_table(
        "deliveries",
        sa.Column(
            "delivery_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "match_id",
            sa.String(100),
            sa.ForeignKey("matches.match_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("innings", sa.SmallInteger(), nullable=False),
        sa.Column("over_number", sa.SmallInteger(), nullable=False),
        sa.Column("ball_number", sa.SmallInteger(), nullable=False),
        sa.Column(
            "batter_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "bowler_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "non_striker_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("runs_batter", sa.SmallInteger(), server_default="0"),
        sa.Column("runs_extras", sa.SmallInteger(), server_default="0"),
        sa.Column("runs_total", sa.SmallInteger(), server_default="0"),
        sa.Column("wicket", sa.Boolean(), server_default="false"),
        sa.Column("wicket_kind", sa.String(50), nullable=True),
        sa.Column(
            "player_dismissed_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_deliveries_match_id", "deliveries", ["match_id"])
    op.create_index("ix_deliveries_batter_id", "deliveries", ["batter_id"])
    op.create_index("ix_deliveries_bowler_id", "deliveries", ["bowler_id"])
    op.create_index("ix_deliveries_wicket", "deliveries", ["wicket"])

    # ------------------------------------------------------------------
    # archetypes
    # ------------------------------------------------------------------
    op.create_table(
        "archetypes",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "centroid_features", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ------------------------------------------------------------------
    # processed_files
    # ------------------------------------------------------------------
    op.create_table(
        "processed_files",
        sa.Column(
            "file_id", sa.Integer(), primary_key=True, autoincrement=True
        ),
        sa.Column("filename", sa.String(500), nullable=False, unique=True),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("record_count", sa.Integer(), nullable=True),
    )
    op.create_index("ix_processed_files_filename", "processed_files", ["filename"])
    op.create_index(
        "ix_processed_files_processed_at", "processed_files", ["processed_at"]
    )


def downgrade() -> None:
    """Drop all tables created in upgrade."""
    op.drop_table("processed_files")
    op.drop_table("archetypes")
    op.drop_table("deliveries")
    op.drop_table("matches")
    op.drop_table("players")
