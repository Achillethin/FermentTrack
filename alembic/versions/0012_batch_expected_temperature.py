"""batches.expected_temperature_c — the user's estimated fermentation temperature (°C)

Nullable: existing batches have no estimate, and the prediction model falls back to the
fermentation type's typical temperature when it is missing. batch_alter_table so the
downgrade's DROP COLUMN also works on SQLite (local dev, tests).

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-24

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("batches") as batch:
        batch.add_column(sa.Column("expected_temperature_c", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("batches") as batch:
        batch.drop_column("expected_temperature_c")
