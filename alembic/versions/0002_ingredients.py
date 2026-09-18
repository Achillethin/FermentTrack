"""ingredients and batch_ingredients — recipe logging

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18

"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from fermenttrack.seed_data import INGREDIENT_SEED_DATA

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ingredients_table = op.create_table(
        "ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("default_role", sa.Text(), nullable=False),
        sa.Column("fermentation_systems", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "batch_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False
        ),
        sa.Column(
            "ingredient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingredients.id"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
    )
    op.create_index("ix_batch_ingredients_batch_id", "batch_ingredients", ["batch_id"])

    op.bulk_insert(
        ingredients_table,
        [
            {
                "id": uuid.uuid4(),
                "canonical_id": None,
                "name": name,
                "default_role": role,
                "fermentation_systems": systems,
                "is_active": True,
            }
            for name, role, systems in INGREDIENT_SEED_DATA
        ],
    )


def downgrade() -> None:
    op.drop_table("batch_ingredients")
    op.drop_table("ingredients")
