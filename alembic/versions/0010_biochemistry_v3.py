# alembic/versions/0010_biochemistry_v3.py
"""biochemistry v3: garum gains Aspergillus oryzae as a default organism (koji-garum)

Adds exactly the fermentation_type_organisms rows in `snapshot_delta(v2, v3)`, resolved
by natural key (fermentation_type text, organism name). Only link additions are supported
here: a v2 -> v3 delta with new organisms/enzymes/compounds or organism_enzymes/
enzyme_reactions rows is refused (migration 0009 covers the general case). Nothing is
re-id'd, so batch_organisms overrides stay valid; downgrade removes only the added links.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-24

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op
from fermenttrack.biochem import KEGG_BIOCHEM_V2, KEGG_BIOCHEM_V3, load_snapshot, snapshot_delta

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LINKS = "fermentation_type_organisms"

organisms_t = sa.table("organisms", sa.column("id", UUID(as_uuid=True)), sa.column("name"))
links_t = sa.table(
    LINKS, sa.column("id", UUID(as_uuid=True)), sa.column("fermentation_type"),
    sa.column("organism_id", UUID(as_uuid=True)), sa.column("is_default", sa.Boolean()),
)  # fmt: skip


def links_only(delta: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """The delta's link rows; RuntimeError if it holds anything but fermentation_type_organisms."""
    other = {t: len(rows) for t, rows in delta.items() if t != LINKS and rows}
    if other:
        raise RuntimeError(f"migration 0010 only adds {LINKS} links; delta also has {other}")
    return delta[LINKS]


def _resolved() -> list[tuple[str, Any]]:
    """Delta links as (fermentation_type, live organism id)."""
    # Both snapshots are frozen, so this migration stays a faithful record of what it changed.
    v2, v3 = load_snapshot(KEGG_BIOCHEM_V2), load_snapshot(KEGG_BIOCHEM_V3)
    rows = links_only(snapshot_delta(v2, v3))
    org = dict(op.get_bind().execute(sa.select(organisms_t.c.name, organisms_t.c.id)).all())
    return [(r["fermentation_type"], org[r["organism"]]) for r in rows]


def _where(ftype: str, organism_id: Any) -> sa.ColumnElement[bool]:
    return sa.and_(links_t.c.fermentation_type == ftype, links_t.c.organism_id == organism_id)


def upgrade() -> None:
    conn = op.get_bind()
    for ftype, organism_id in _resolved():
        # Defensive idempotence: skip a link that already exists.
        if conn.execute(sa.select(links_t.c.id).where(_where(ftype, organism_id))).first() is None:
            op.bulk_insert(links_t, [{
                "id": uuid.uuid4(), "fermentation_type": ftype,
                "organism_id": organism_id, "is_default": True,
            }])  # fmt: skip


def downgrade() -> None:
    conn = op.get_bind()
    for ftype, organism_id in _resolved():
        conn.execute(sa.delete(links_t).where(_where(ftype, organism_id)))
