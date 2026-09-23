"""split vague seed ingredients into specific ones; Water gains lacto_ferment

Generic rows (Rice/grain/soybean, Flour, Fruit, ...) are retired with
is_active=False, never deleted, so historical batch_ingredients keep their FK.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-23

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from fermenttrack.seed_data import INGREDIENT_SEED_DATA_V3, RETIRED_V3, WATER_SYSTEMS_V3

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_WATER_SYSTEMS = ["kombucha", "sourdough"]


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
    t = _table()
    op.bulk_insert(
        t,
        [
            {
                "id": uuid.uuid4(),
                "canonical_id": None,
                "name": name,
                "default_role": role,
                "fermentation_systems": systems,
                "is_active": True,
            }
            for name, role, systems in INGREDIENT_SEED_DATA_V3
        ],
    )
    op.execute(t.update().where(t.c.name.in_(RETIRED_V3)).values(is_active=False))
    op.execute(t.update().where(t.c.name == "Water").values(fermentation_systems=WATER_SYSTEMS_V3))


def downgrade() -> None:
    # Fails on FK if any batch already logged a V3 ingredient — intended: don't lose recipe data.
    t = _table()
    op.execute(
        t.update().where(t.c.name == "Water").values(fermentation_systems=_OLD_WATER_SYSTEMS)
    )
    op.execute(t.update().where(t.c.name.in_(RETIRED_V3)).values(is_active=True))
    op.execute(t.delete().where(t.c.name.in_([n for n, _r, _s in INGREDIENT_SEED_DATA_V3])))
