"""sourdough engine: culture style, batch sourdough plan, per-batch kinetic evidence, and the
three sourdough organisms (K. humilis, L. brevis, L. reuteri; no KEGG enzyme links yet).

See docs/superpowers/specs/2026-09-28-sourdough-engine-design.md. population_priors (0015)
is left in place, unused: the crossed hierarchy reads batch_evidence instead.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-28

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = "sourdough_engine_v1"
NEW_ORGANISMS = {
    "Kazachstania humilis": "yeast",
    "Lactobacillus brevis": "bacteria",
    "Lactobacillus reuteri": "bacteria",
}
organisms_t = sa.table(
    "organisms", sa.column("id", UUID(as_uuid=True)), sa.column("name"), sa.column("kingdom"),
    sa.column("source_version"),
)  # fmt: skip


def upgrade() -> None:
    with op.batch_alter_table("cultures") as batch:
        batch.add_column(sa.Column("style", sa.Text(), nullable=True))
    with op.batch_alter_table("batches") as batch:
        batch.add_column(sa.Column("sourdough_plan", sa.JSON(), nullable=True))
    op.create_table(
        "batch_evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "batch_id", UUID(as_uuid=True), sa.ForeignKey("batches.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "culture_id", UUID(as_uuid=True), sa.ForeignKey("cultures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("style", sa.Text(), nullable=True),
        sa.Column("organism", sa.Text(), nullable=False, index=True),
        sa.Column("param", sa.Text(), nullable=False),
        sa.Column("ell", sa.Float(), nullable=False),
        sa.Column("lam", sa.Float(), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("batch_id", "organism", "param"),
    )  # fmt: skip
    conn = op.get_bind()
    have = {r[0] for r in conn.execute(sa.text("SELECT name FROM organisms"))}
    rows = [
        {"id": uuid.uuid4(), "name": n, "kingdom": k, "source_version": SOURCE}
        for n, k in NEW_ORGANISMS.items()
        if n not in have
    ]
    if rows:
        op.bulk_insert(organisms_t, rows)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM organisms WHERE source_version = :s").bindparams(s=SOURCE)
    )
    op.drop_table("batch_evidence")
    with op.batch_alter_table("batches") as batch:
        batch.drop_column("sourdough_plan")
    with op.batch_alter_table("cultures") as batch:
        batch.drop_column("style")
