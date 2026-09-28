"""population_priors table + batches.population_pooled_at — empirical-Bayes plug-in
pooling of per-batch AMIS posteriors into a population-level prior per (organism,
kinetic parameter). See prediction/population.py and
docs/superpowers/specs/2026-09-28-population-pooling-design.md.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-28

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "population_priors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organism_id", UUID(as_uuid=True), sa.ForeignKey("organisms.id"), nullable=False),
        sa.Column("param_name", sa.Text(), nullable=False),
        sa.Column("n_obs", sa.Integer(), nullable=False),
        sa.Column("median", sa.Float(), nullable=False),
        sa.Column("lo", sa.Float(), nullable=False),
        sa.Column("hi", sa.Float(), nullable=False),
        sa.Column("scale", sa.Text(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("organism_id", "param_name"),
    )
    with op.batch_alter_table("batches") as batch:
        batch.add_column(sa.Column("population_pooled_at", TIMESTAMP(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("batches") as batch:
        batch.drop_column("population_pooled_at")
    op.drop_table("population_priors")
