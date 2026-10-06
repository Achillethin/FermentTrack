"""aroma ingredients in the catalogue: napa cabbage, cucumber, radish, carrot, garlic, onion,
caraway seeds, dill, lemongrass (aroma increment B6; no FDC nutrient rows)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-06

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from fermenttrack.seed_data import INGREDIENT_SEED_DATA_V4

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table() -> sa.Table:
    return sa.table(
        "ingredients",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("canonical_id", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("default_role", sa.Text()),
        sa.column("fermentation_systems", sa.JSON()),
        sa.column("is_active", sa.Boolean()),
    )


def upgrade() -> None:
    op.bulk_insert(
        _table(),
        [
            {
                "id": uuid.uuid4(),
                "canonical_id": None,
                "name": name,
                "default_role": role,
                "fermentation_systems": systems,
                "is_active": True,
            }
            for name, role, systems in INGREDIENT_SEED_DATA_V4
        ],
    )


def downgrade() -> None:
    # Fails on FK if a batch already logged one of them: intended, recipe data is kept.
    t = _table()
    op.execute(t.delete().where(t.c.name.in_([n for n, _r, _s in INGREDIENT_SEED_DATA_V4])))
