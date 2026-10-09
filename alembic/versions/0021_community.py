"""community_recipes and community_recipe_forecasts (recommender design § 10.3): recipes users
publish from their finished batches, reviewed by an admin, and the approved ones' forecasts per
temperature (the grid's statistics, computed by the job queue). A batch is published once until
rejected (a partial unique index). recommendation_links gains the foreign key its
community_recipe_id was waiting for (0019) and parent_batch_id, the parent batch of an
own_batch link; earlier own_batch links named it as recipe_key "batch:<id>": it is moved into
parent_batch_id (recipe_key set null) when that batch still exists, and moved back on
downgrade. Both foreign keys are set null when their row goes. SQLite alters
recommendation_links by copying it (batch mode).

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-09

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = sa.text("status IN ('pending', 'approved', 'rejected')")
NOT_REJECTED = sa.text("status <> 'rejected'")
LEGACY_PREFIX = "batch:"
LINKS = sa.table(
    "recommendation_links",
    sa.column("batch_id", UUID(as_uuid=True)), sa.column("source_kind", sa.Text()),
    sa.column("recipe_key", sa.Text()), sa.column("parent_batch_id", UUID(as_uuid=True)),
)  # fmt: skip
BATCHES = sa.table("batches", sa.column("id", UUID(as_uuid=True)))
OWN_BATCH = LINKS.c.source_kind == "own_batch"


def upgrade() -> None:
    op.create_table(
        "community_recipes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column(
            "source_batch_id", UUID(as_uuid=True),
            sa.ForeignKey(
                "batches.id", ondelete="SET NULL", name="fk_community_recipes_source_batch_id"
            ),
            nullable=True,
        ),
        sa.Column("pseudonym", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("fermentation_type", sa.Text(), nullable=False),
        sa.Column("recipe", sa.JSON(), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.Column("duration_h", sa.Float(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.CheckConstraint(STATUSES, name="ck_community_recipes_status"),
    )  # fmt: skip
    op.create_index("ix_community_recipes_owner_id", "community_recipes", ["owner_id"])
    op.create_index(
        "uq_community_recipes_source_batch", "community_recipes", ["source_batch_id"],
        unique=True, postgresql_where=NOT_REJECTED, sqlite_where=NOT_REJECTED,
    )  # fmt: skip
    op.create_table(
        "community_recipe_forecasts",
        sa.Column(
            "recipe_id", UUID(as_uuid=True),
            sa.ForeignKey("community_recipes.id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column("temp_c", sa.Float(), primary_key=True),
        sa.Column("grid_version", sa.Text(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    )  # fmt: skip
    with op.batch_alter_table("recommendation_links") as batch:
        batch.add_column(sa.Column("parent_batch_id", UUID(as_uuid=True), nullable=True))
        batch.create_foreign_key(
            "fk_recommendation_links_parent_batch_id", "batches", ["parent_batch_id"], ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_recommendation_links_community_recipe_id", "community_recipes",
            ["community_recipe_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_index(
            "ix_recommendation_links_community_recipe_id", ["community_recipe_id"]
        )
    _move_legacy_parents()


def _move_legacy_parents() -> None:
    """An own_batch link's recipe_key "batch:<id>" into parent_batch_id, when that batch
    exists (an unparsable key or a deleted batch keeps the key)."""
    conn = op.get_bind()
    legacy = conn.execute(
        sa.select(LINKS.c.batch_id, LINKS.c.recipe_key)
        .where(OWN_BATCH, LINKS.c.recipe_key.like(f"{LEGACY_PREFIX}%"))
    ).all()
    for batch_id, key in legacy:
        try:
            parent = uuid.UUID(key.removeprefix(LEGACY_PREFIX))
        except ValueError:
            continue
        if conn.execute(sa.select(BATCHES.c.id).where(BATCHES.c.id == parent)).first() is None:
            continue
        conn.execute(
            sa.update(LINKS).where(LINKS.c.batch_id == batch_id)
            .values(parent_batch_id=parent, recipe_key=None)
        )  # fmt: skip


def downgrade() -> None:
    conn = op.get_bind()  # own_batch links name their parent batch as before 0021
    parents = conn.execute(
        sa.select(LINKS.c.batch_id, LINKS.c.parent_batch_id)
        .where(OWN_BATCH, LINKS.c.parent_batch_id.is_not(None))
    ).all()
    for batch_id, parent in parents:
        conn.execute(
            sa.update(LINKS).where(LINKS.c.batch_id == batch_id)
            .values(recipe_key=f"{LEGACY_PREFIX}{parent}")
        )  # fmt: skip
    with op.batch_alter_table("recommendation_links") as batch:
        batch.drop_index("ix_recommendation_links_community_recipe_id")
        batch.drop_constraint("fk_recommendation_links_community_recipe_id", type_="foreignkey")
        batch.drop_constraint("fk_recommendation_links_parent_batch_id", type_="foreignkey")
        batch.drop_column("parent_batch_id")
    op.drop_table("community_recipe_forecasts")
    op.drop_index("uq_community_recipes_source_batch", table_name="community_recipes")
    op.drop_index("ix_community_recipes_owner_id", table_name="community_recipes")
    op.drop_table("community_recipes")
