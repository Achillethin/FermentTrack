"""tag existing Salt ingredient for lacto_ferment and garum

Both stage machines have a named salting step (lacto_ferment's
prep_and_salt, garum's salt_fish) but the seeded Salt row only covered
cheese/koji/miso/sourdough — an oversight from migration 0002, predating
0003's lacto_ferment/garum substrates. Widens the existing row rather than
inserting a duplicate "Salt" ingredient.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-23

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_SYSTEMS = ["cheese", "koji", "miso", "sourdough"]
_NEW_SYSTEMS = ["cheese", "koji", "miso", "sourdough", "lacto_ferment", "garum"]


def _ingredients_table() -> sa.Table:
    return sa.table(
        "ingredients",
        sa.column("name", sa.Text()),
        sa.column("fermentation_systems", sa.JSON()),
    )


def upgrade() -> None:
    table = _ingredients_table()
    op.execute(table.update().where(table.c.name == "Salt").values(fermentation_systems=_NEW_SYSTEMS))


def downgrade() -> None:
    table = _ingredients_table()
    op.execute(table.update().where(table.c.name == "Salt").values(fermentation_systems=_OLD_SYSTEMS))
