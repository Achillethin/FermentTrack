"""Noma and Katz round ingredients (recipe curation § 9): catalogue rows and USDA nutrients

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-26

The fourteen INGREDIENT_SEED_DATA_V5 rows (inserted only where the name is not already there),
then, as 0018 did for the aroma ingredients, the nutrients of each INGREDIENT_FDC_IDS_V5 food
copied from fdc_food_nutrients exactly as a USDA-search pick does. The unique ingredients.fdc_id
is set only where no other ingredient holds that food (a user may have picked it by search).
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from fermenttrack.seed_data import INGREDIENT_FDC_IDS_V5, INGREDIENT_SEED_DATA_V5

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE, VERSION = "usda_fdc", "fdc_catalog_v1"

ingredients_t = sa.table(
    "ingredients",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("canonical_id", sa.Text()),
    sa.column("name", sa.Text()),
    sa.column("default_role", sa.Text()),
    sa.column("fermentation_systems", sa.JSON()),
    sa.column("is_active", sa.Boolean()),
)
nutrients_t = sa.table(
    "ingredient_nutrients",
    sa.column("id", sa.Uuid()),
    sa.column("ingredient_id", sa.Uuid()),
    sa.column("nutrient", sa.Text()),
    sa.column("amount_per_100g", sa.Float()),
    sa.column("source", sa.Text()),
    sa.column("source_food_id", sa.Text()),
    sa.column("source_version", sa.Text()),
)


def _curated(bind: sa.Connection, name: str) -> sa.Row | None:
    return bind.execute(
        sa.text("SELECT id, fdc_id FROM ingredients WHERE name = :n AND canonical_id IS NULL"),
        {"n": name},
    ).first()


def upgrade() -> None:
    bind = op.get_bind()
    op.bulk_insert(ingredients_t, [
        {"id": uuid.uuid4(), "canonical_id": None, "name": name, "default_role": role,
         "fermentation_systems": systems, "is_active": True}
        for name, role, systems in INGREDIENT_SEED_DATA_V5
        if _curated(bind, name) is None
    ])  # fmt: skip
    for name, fdc_id in INGREDIENT_FDC_IDS_V5.items():
        ing = _curated(bind, name)
        assert ing is not None, name
        has = bind.execute(
            sa.text("SELECT 1 FROM ingredient_nutrients WHERE ingredient_id = :i AND source = :s"),
            {"i": ing.id, "s": SOURCE},
        ).first()
        if has is None:
            rows = bind.execute(
                sa.text(
                    "SELECT nutrient, amount_per_100g FROM fdc_food_nutrients WHERE fdc_id = :f"
                ),
                {"f": fdc_id},
            ).all()
            op.bulk_insert(nutrients_t, [
                {"id": uuid.uuid4(), "ingredient_id": uuid.UUID(str(ing.id)), "nutrient": n,
                 "amount_per_100g": a,
                 "source": SOURCE, "source_food_id": str(fdc_id), "source_version": VERSION}
                for n, a in rows
            ])  # fmt: skip
        taken = bind.execute(
            sa.text("SELECT 1 FROM ingredients WHERE fdc_id = :f"), {"f": fdc_id}
        ).first()
        if ing.fdc_id is None and taken is None:
            bind.execute(
                sa.text("UPDATE ingredients SET fdc_id = :f WHERE id = :i"),
                {"f": fdc_id, "i": ing.id},
            )


def downgrade() -> None:
    # Fails on FK if a batch already logged one of them: intended, recipe data is kept.
    bind = op.get_bind()
    for name, fdc_id in INGREDIENT_FDC_IDS_V5.items():
        ing = _curated(bind, name)
        if ing is not None:
            bind.execute(
                sa.text(
                    "DELETE FROM ingredient_nutrients WHERE ingredient_id = :i AND source = :s"
                    " AND source_food_id = :f AND source_version = :v"
                ),
                {"i": ing.id, "s": SOURCE, "f": str(fdc_id), "v": VERSION},
            )
    names = [n for n, _r, _s in INGREDIENT_SEED_DATA_V5]
    op.execute(
        ingredients_t.delete().where(
            ingredients_t.c.name.in_(names), ingredients_t.c.canonical_id.is_(None)
        )
    )
