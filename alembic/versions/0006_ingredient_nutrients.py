"""ingredient_nutrients — USDA FDC reference composition, seeded from the frozen v1 snapshot

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from fermenttrack.nutrients import FDC_SNAPSHOT_V1, load_snapshot, nutrient_seed_rows

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = op.create_table(
        "ingredient_nutrients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ingredient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingredients.id"),
            nullable=False,
        ),
        sa.Column("nutrient", sa.Text(), nullable=False),
        sa.Column("amount_per_100g", sa.Float(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_food_id", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
        sa.UniqueConstraint("ingredient_id", "nutrient", "source"),
    )
    ingredients = sa.table(
        "ingredients",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.Text()),
    )
    rows = op.get_bind().execute(sa.select(ingredients.c.id, ingredients.c.name))
    ids_by_name = {name: id_ for id_, name in rows}
    # FDC_SNAPSHOT_V1 is frozen, so this migration stays a faithful record of what it inserted.
    op.bulk_insert(table, nutrient_seed_rows(load_snapshot(FDC_SNAPSHOT_V1), ids_by_name))


def downgrade() -> None:
    op.drop_table("ingredient_nutrients")
