"""cultures.owner_id — Supabase Auth user id (JWT `sub`), Stage 0 auth/sharing.

Nullable: rows created before this migration are unowned until backfilled
(scripts/assign_existing_data_to_user.py). batch_alter_table so the downgrade's
DROP COLUMN also works on SQLite (local dev, tests).

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-27

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("cultures") as batch:
        batch.add_column(sa.Column("owner_id", sa.Text(), nullable=True))
        batch.create_index("ix_cultures_owner_id", ["owner_id"])


def downgrade() -> None:
    with op.batch_alter_table("cultures") as batch:
        batch.drop_index("ix_cultures_owner_id")
        batch.drop_column("owner_id")
