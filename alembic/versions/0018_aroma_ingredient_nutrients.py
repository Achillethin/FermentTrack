"""USDA nutrients for the aroma ingredients of 0017 (copied from the bundled fdc catalogue)

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-07

0017 added nine ingredients without nutrient rows, so a recipe built from them looked like
almost pure water to the forecast (a napa-cabbage kimchi barely acidified). Their foods are
in fdc_food_nutrients (0007): copy them exactly as a USDA-search pick does
(routers/batches.py _ingredient_for_fdc_food). The unique ingredients.fdc_id is set only
where no other ingredient holds that food yet (a user may have picked it by search).
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from fermenttrack.seed_data import INGREDIENT_FDC_IDS_V4

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE, VERSION = "usda_fdc", "fdc_catalog_v1"


def upgrade() -> None:
    bind = op.get_bind()
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
    for name, fdc_id in INGREDIENT_FDC_IDS_V4.items():
        ing = bind.execute(
            sa.text("SELECT id, fdc_id FROM ingredients WHERE name = :n AND canonical_id IS NULL"),
            {"n": name},
        ).first()
        if ing is None:
            continue
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
    bind = op.get_bind()
    for name, fdc_id in INGREDIENT_FDC_IDS_V4.items():
        ing = bind.execute(
            sa.text("SELECT id FROM ingredients WHERE name = :n AND canonical_id IS NULL"),
            {"n": name},
        ).first()
        if ing is None:
            continue
        bind.execute(
            sa.text(
                "DELETE FROM ingredient_nutrients WHERE ingredient_id = :i AND source = :s"
                " AND source_food_id = :f AND source_version = :v"
            ),
            {"i": ing.id, "s": SOURCE, "f": str(fdc_id), "v": VERSION},
        )
        bind.execute(
            sa.text("UPDATE ingredients SET fdc_id = NULL WHERE id = :i AND fdc_id = :f"),
            {"i": ing.id, "f": fdc_id},
        )
