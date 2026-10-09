"""recommendation_jobs: the recommender's background jobs (design § 10.2, "search deeper"), a
FIFO queue drained by the single in-process worker (recommender.jobs). At most one queued or
running job per owner: a partial unique index (Postgres and SQLite both take the WHERE).
attempts: the claims of a job, for the worker's crash-loop guard.

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-09

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE = sa.text("status IN ('queued', 'running')")


def upgrade() -> None:
    op.create_table(
        "recommendation_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=True),
        sa.Column("done", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("started_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_recommendation_jobs_owner_id", "recommendation_jobs", ["owner_id"])
    op.create_index("ix_recommendation_jobs_queue", "recommendation_jobs", ["status", "created_at"])
    op.create_index(
        "uq_recommendation_jobs_one_active", "recommendation_jobs", ["owner_id"], unique=True,
        postgresql_where=ACTIVE, sqlite_where=ACTIVE,
    )  # fmt: skip


def downgrade() -> None:
    op.drop_index("uq_recommendation_jobs_one_active", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_queue", table_name="recommendation_jobs")
    op.drop_index("ix_recommendation_jobs_owner_id", table_name="recommendation_jobs")
    op.drop_table("recommendation_jobs")
