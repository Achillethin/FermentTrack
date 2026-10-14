"""recommendation_links: the recommendation a batch was started from (recommender design
§ 11.2), written by POST /batches/from-recommendation; and reminders.kind, so the pH check
that Start batch creates (kind 'safety') is not closed by a stage change like a stage timer
(kind 'stage', every existing row).

community_recipe_id has no foreign key yet: community_recipes arrives with 0021.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-08

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_links",
        sa.Column(
            "batch_id", UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("recipe_key", sa.Text(), nullable=True),
        sa.Column("community_recipe_id", UUID(as_uuid=True), nullable=True),
        sa.Column("operators", sa.JSON(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.Column("temp_schedule", sa.JSON(), nullable=True),
        sa.Column("window", sa.JSON(), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
        sa.Column("grid_version", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=True),
    )  # fmt: skip
    with op.batch_alter_table("reminders") as batch:
        batch.add_column(
            sa.Column("kind", sa.Text(), nullable=False, server_default=sa.text("'stage'"))
        )


def downgrade() -> None:
    with op.batch_alter_table("reminders") as batch:
        batch.drop_column("kind")
    op.drop_table("recommendation_links")
