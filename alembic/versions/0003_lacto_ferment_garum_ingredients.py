"""lacto_ferment and garum reference ingredients

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-20

"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from fermenttrack.seed_data import INGREDIENT_SEED_DATA_V2

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ingredients_table() -> sa.Table:
    # Lightweight reference to the existing table (created by 0002) — do not
    # op.create_table it again here, this migration only adds rows. Column
    # types must match 0002's create_table exactly (esp. the UUID type) or
    # SQLite's driver can't bind a Python uuid.UUID value.
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
        _ingredients_table(),
        [
            {
                "id": uuid.uuid4(),
                "canonical_id": None,
                "name": name,
                "default_role": role,
                "fermentation_systems": systems,
                "is_active": True,
            }
            for name, role, systems in INGREDIENT_SEED_DATA_V2
        ],
    )


def downgrade() -> None:
    table = _ingredients_table()
    names = [name for name, _role, _systems in INGREDIENT_SEED_DATA_V2]
    op.execute(table.delete().where(table.c.name.in_(names)))
