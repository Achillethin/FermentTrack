"""tastings (recommender design § 11.2): a batch's tastings (t_h, 0-3 ratings per series or
taste, liking, make_again, notes), deleted with their batch; and recommendation_links.p_series,
P (noticeable) per target on the card's time axis, so the calibration gate (§ 13.2) can score a
tasting at any time. Earlier links keep p_series null (nothing is backfilled). The stop-by
prompt needs no column: it is a reminder of kind 'tasting' (reminders.kind is free text); on
downgrade such reminders stay and 0021's code closes them with the stage timers. SQLite drops
p_series by copying recommendation_links (batch mode).

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-09

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tastings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id", UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("t_h", sa.Float(), nullable=False),
        sa.Column("ratings", sa.JSON(), nullable=False),
        sa.Column("liking", sa.Integer(), nullable=True),
        sa.Column("make_again", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("t_h >= 0", name="ck_tastings_t_h"),
        sa.CheckConstraint("liking IS NULL OR liking BETWEEN 1 AND 5", name="ck_tastings_liking"),
    )  # fmt: skip
    op.create_index("ix_tastings_batch_id", "tastings", ["batch_id"])
    op.add_column("recommendation_links", sa.Column("p_series", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("recommendation_links") as batch:
        batch.drop_column("p_series")
    op.drop_index("ix_tastings_batch_id", table_name="tastings")
    op.drop_table("tastings")
