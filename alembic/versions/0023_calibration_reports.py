"""calibration_reports (recommender design § 13.2): one row per run of the calibration gate
(recommender.calibration), its report as JSON with its decision and batch count alongside.
Aggregates only: no user, batch or tasting id. Nothing to backfill: the app computes the first
report at startup.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-13

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calibration_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("computed_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("n_batches", sa.Integer(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_calibration_reports_computed_at", "calibration_reports", ["computed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_calibration_reports_computed_at", table_name="calibration_reports")
    op.drop_table("calibration_reports")
