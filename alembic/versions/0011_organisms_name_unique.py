# alembic/versions/0011_organisms_name_unique.py
"""organisms.name is unique (migrations resolve organisms by name)

A unique INDEX rather than ALTER TABLE ADD CONSTRAINT, so it works on both SQLite and
PostgreSQL (see 0007). Production has no duplicate organism names: only migrations insert
organisms, and 0008/0009 skip names that already exist.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-24

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_organisms_name", "organisms", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_organisms_name", table_name="organisms")
