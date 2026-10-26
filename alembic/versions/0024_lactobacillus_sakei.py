"""Lactobacillus sakei (Latilactobacillus sakei), a default lacto_ferment organism

Kimchi's cold-active homofermenter (recommender v2 release 2; kinetics and sources in
prediction/organisms.py): the organism row (no KEGG enzyme links yet, like the sourdough
organisms of 0016) and its lacto_ferment default link. Idempotent; the downgrade removes
only what this migration added.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-26

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE = "lactobacillus_sakei_v1"
NAME = "Lactobacillus sakei"
TYPE = "lacto_ferment"

organisms_t = sa.table(
    "organisms", sa.column("id", UUID(as_uuid=True)), sa.column("name"), sa.column("kingdom"),
    sa.column("source_version"),
)  # fmt: skip
links_t = sa.table(
    "fermentation_type_organisms", sa.column("id", UUID(as_uuid=True)),
    sa.column("fermentation_type"), sa.column("organism_id", UUID(as_uuid=True)),
    sa.column("is_default", sa.Boolean()),
)  # fmt: skip


def _organism_id(conn: sa.Connection) -> uuid.UUID | None:
    row = conn.execute(sa.select(organisms_t.c.id).where(organisms_t.c.name == NAME)).first()
    return None if row is None else row[0]


def upgrade() -> None:
    conn = op.get_bind()
    organism_id = _organism_id(conn)
    if organism_id is None:
        organism_id = uuid.uuid4()
        op.bulk_insert(organisms_t, [
            {"id": organism_id, "name": NAME, "kingdom": "bacteria", "source_version": SOURCE}
        ])  # fmt: skip
    linked = conn.execute(
        sa.select(links_t.c.id).where(
            links_t.c.fermentation_type == TYPE, links_t.c.organism_id == organism_id
        )
    ).first()
    if linked is None:
        op.bulk_insert(links_t, [{
            "id": uuid.uuid4(), "fermentation_type": TYPE, "organism_id": organism_id,
            "is_default": True,
        }])  # fmt: skip


def downgrade() -> None:
    conn = op.get_bind()
    organism_id = _organism_id(conn)
    if organism_id is None:
        return
    conn.execute(
        sa.delete(links_t).where(
            links_t.c.fermentation_type == TYPE, links_t.c.organism_id == organism_id
        )
    )
    conn.execute(
        sa.delete(organisms_t).where(
            organisms_t.c.id == organism_id, organisms_t.c.source_version == SOURCE
        )
    )
