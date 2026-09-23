"""fdc_foods / fdc_food_nutrients catalog + ingredients.fdc_id (backfilled for curated rows)

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from fermenttrack.fdc_catalog import FDC_CATALOG_V1, catalog_seed_rows, load_catalog

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHUNK = 5000


def upgrade() -> None:
    foods_t = op.create_table(
        "fdc_foods",
        sa.Column("fdc_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("data_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
    )
    nutrients_t = op.create_table(
        "fdc_food_nutrients",
        sa.Column("fdc_id", sa.Integer(), sa.ForeignKey("fdc_foods.fdc_id"), primary_key=True),
        sa.Column("nutrient", sa.Text(), primary_key=True),
        sa.Column("amount_per_100g", sa.Float(), nullable=False),
    )
    op.add_column("ingredients", sa.Column("fdc_id", sa.Integer(), nullable=True))
    op.create_index("ix_ingredients_fdc_id", "ingredients", ["fdc_id"], unique=True)

    # FDC_CATALOG_V1 is frozen, so this migration stays a faithful record of what it inserted.
    foods, nutrients = catalog_seed_rows(load_catalog(FDC_CATALOG_V1))
    for i in range(0, len(foods), _CHUNK):
        op.bulk_insert(foods_t, foods[i : i + _CHUNK])
    for i in range(0, len(nutrients), _CHUNK):
        op.bulk_insert(nutrients_t, nutrients[i : i + _CHUNK])

    # Curated ingredients already carry FDC provenance on their v1 nutrient rows.
    op.execute(
        sa.text(
            "UPDATE ingredients SET fdc_id = ("
            " SELECT CAST(MIN(n.source_food_id) AS INTEGER) FROM ingredient_nutrients n"
            " WHERE n.ingredient_id = ingredients.id AND n.source = 'usda_fdc')"
            " WHERE EXISTS (SELECT 1 FROM ingredient_nutrients n"
            " WHERE n.ingredient_id = ingredients.id AND n.source = 'usda_fdc')"
        )
    )


def downgrade() -> None:
    op.drop_index("ix_ingredients_fdc_id", table_name="ingredients")
    op.drop_column("ingredients", "fdc_id")
    op.drop_table("fdc_food_nutrients")
    op.drop_table("fdc_foods")
