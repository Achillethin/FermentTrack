"""initial schema — cultures, batches, measurements, reminders

Revision ID: 0001
Revises:
Create Date: 2026-09-17

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cultures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("born_from", postgresql.UUID(as_uuid=True), sa.ForeignKey("cultures.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
    )

    op.create_table(
        "batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "culture_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cultures.id"), nullable=False
        ),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("current_stage", sa.Text(), nullable=False),
        sa.Column("stage_entered_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False, server_default="in_progress"),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_batches_culture_id", "batches", ["culture_id"])

    op.create_table(
        "measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False
        ),
        sa.Column("measured_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_measurements_batch_id", "measurements", ["batch_id"])

    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("due_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("repeat_interval", sa.Interval(), nullable=True),
        sa.Column("urgency", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_reminders_batch_id", "reminders", ["batch_id"])


def downgrade() -> None:
    op.drop_table("reminders")
    op.drop_table("measurements")
    op.drop_table("batches")
    op.drop_table("cultures")
