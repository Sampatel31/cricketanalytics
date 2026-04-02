"""002_enriched_balls - Add enriched_balls table.

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 01:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add enriched_balls table for context-enriched delivery features."""
    op.create_table(
        "enriched_balls",
        sa.Column(
            "enriched_id", sa.BigInteger(), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "delivery_id",
            sa.BigInteger(),
            sa.ForeignKey("deliveries.delivery_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("score_at_ball", sa.Integer(), server_default="0"),
        sa.Column("wickets_fallen", sa.SmallInteger(), server_default="0"),
        sa.Column("balls_remaining", sa.SmallInteger(), server_default="0"),
        sa.Column("target", sa.Integer(), nullable=True),
        sa.Column("required_run_rate", sa.Float(), nullable=True),
        sa.Column("current_run_rate", sa.Float(), nullable=True),
        sa.Column("pressure_index", sa.Float(), nullable=True),
        sa.Column("phase", sa.String(20), nullable=True),
    )
    op.create_index(
        "ix_enriched_balls_delivery_id", "enriched_balls", ["delivery_id"]
    )
    op.create_index("ix_enriched_balls_phase", "enriched_balls", ["phase"])


def downgrade() -> None:
    """Drop the enriched_balls table."""
    op.drop_table("enriched_balls")
