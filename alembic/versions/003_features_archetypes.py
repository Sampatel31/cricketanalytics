"""003_features_archetypes - Add feature/archetype/alert/auction/UMAP tables.

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 02:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create player_features, player_archetypes, archetype_transitions,
    sovereign_alerts, franchise_dna_sessions, auction_picks, squad_balance,
    umap_models, and hdbscan_clusters tables.
    """

    # ------------------------------------------------------------------
    # player_features
    # ------------------------------------------------------------------
    op.create_table(
        "player_features",
        sa.Column(
            "feature_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "player_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("season", sa.String(10), nullable=False),
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("confidence_weight", sa.Float(), server_default="1.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("player_id", "format", "season", name="uq_player_features"),
    )
    op.create_index("ix_player_features_player_id", "player_features", ["player_id"])
    op.create_index("ix_player_features_season", "player_features", ["season"])
    op.create_index("ix_player_features_format", "player_features", ["format"])

    # ------------------------------------------------------------------
    # player_archetypes
    # ------------------------------------------------------------------
    op.create_table(
        "player_archetypes",
        sa.Column(
            "assignment_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "player_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("season", sa.String(10), nullable=False),
        sa.Column(
            "archetype_code",
            sa.String(50),
            sa.ForeignKey("archetypes.code", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("archetype_label", sa.String(200), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "player_id", "format", "season", name="uq_player_archetypes"
        ),
    )
    op.create_index(
        "ix_player_archetypes_player_id", "player_archetypes", ["player_id"]
    )
    op.create_index("ix_player_archetypes_season", "player_archetypes", ["season"])

    # ------------------------------------------------------------------
    # archetype_transitions
    # ------------------------------------------------------------------
    op.create_table(
        "archetype_transitions",
        sa.Column(
            "transition_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "player_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("from_archetype", sa.String(50), nullable=True),
        sa.Column("to_archetype", sa.String(50), nullable=True),
        sa.Column("season", sa.String(10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_archetype_transitions_player_id",
        "archetype_transitions",
        ["player_id"],
    )
    op.create_index(
        "ix_archetype_transitions_season", "archetype_transitions", ["season"]
    )

    # ------------------------------------------------------------------
    # sovereign_alerts
    # ------------------------------------------------------------------
    op.create_table(
        "sovereign_alerts",
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "player_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("resolved", sa.Boolean(), server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_sovereign_alerts_player_id", "sovereign_alerts", ["player_id"]
    )
    op.create_index(
        "ix_sovereign_alerts_severity", "sovereign_alerts", ["severity"]
    )
    op.create_index(
        "ix_sovereign_alerts_resolved", "sovereign_alerts", ["resolved"]
    )
    op.create_index(
        "ix_sovereign_alerts_created_at", "sovereign_alerts", ["created_at"]
    )

    # ------------------------------------------------------------------
    # franchise_dna_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "franchise_dna_sessions",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("franchise_name", sa.String(200), nullable=False),
        sa.Column(
            "dna_vector",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_franchise_dna_sessions_franchise_name",
        "franchise_dna_sessions",
        ["franchise_name"],
    )
    op.create_index(
        "ix_franchise_dna_sessions_created_at",
        "franchise_dna_sessions",
        ["created_at"],
    )

    # ------------------------------------------------------------------
    # auction_picks
    # ------------------------------------------------------------------
    op.create_table(
        "auction_picks",
        sa.Column(
            "pick_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("franchise_dna_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "player_id",
            sa.String(100),
            sa.ForeignKey("players.player_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("pick_number", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_auction_picks_session_id", "auction_picks", ["session_id"])
    op.create_index("ix_auction_picks_player_id", "auction_picks", ["player_id"])

    # ------------------------------------------------------------------
    # squad_balance
    # ------------------------------------------------------------------
    op.create_table(
        "squad_balance",
        sa.Column(
            "balance_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("franchise_dna_sessions.session_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "archetype_balance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("dna_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_squad_balance_session_id", "squad_balance", ["session_id"])

    # ------------------------------------------------------------------
    # umap_models
    # ------------------------------------------------------------------
    op.create_table(
        "umap_models",
        sa.Column(
            "model_id", sa.Integer(), primary_key=True, autoincrement=True
        ),
        sa.Column("format_type", sa.String(20), nullable=False, unique=True),
        sa.Column("model_data", sa.LargeBinary(), nullable=False),
        sa.Column(
            "fitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_umap_models_format_type", "umap_models", ["format_type"])

    # ------------------------------------------------------------------
    # hdbscan_clusters
    # ------------------------------------------------------------------
    op.create_table(
        "hdbscan_clusters",
        sa.Column(
            "cluster_id", sa.Integer(), primary_key=True, autoincrement=True
        ),
        sa.Column("format_type", sa.String(20), nullable=False, unique=True),
        sa.Column("labels", sa.LargeBinary(), nullable=False),
        sa.Column(
            "centroids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "fitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_hdbscan_clusters_format_type", "hdbscan_clusters", ["format_type"]
    )


def downgrade() -> None:
    """Drop all tables added in this migration."""
    op.drop_table("hdbscan_clusters")
    op.drop_table("umap_models")
    op.drop_table("squad_balance")
    op.drop_table("auction_picks")
    op.drop_table("franchise_dna_sessions")
    op.drop_table("sovereign_alerts")
    op.drop_table("archetype_transitions")
    op.drop_table("player_archetypes")
    op.drop_table("player_features")
