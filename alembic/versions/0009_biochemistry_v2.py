# alembic/versions/0009_biochemistry_v2.py
"""biochemistry v2: additive KEGG snapshot (more organisms/enzymes/compounds/links)

Adds exactly `snapshot_delta(v1, v2)` on top of migration 0008, keyed by natural
identity (organism name, EC number, KEGG compound id). Existing reference rows are
never deleted or re-id'd: batch_organisms overrides point at their UUIDs.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-24

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op
from fermenttrack.biochem import KEGG_BIOCHEM_V1, KEGG_BIOCHEM_V2, load_snapshot, snapshot_delta

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

V2_TAG = "kegg_biochem_v2"


def _uuid_col(name: str) -> sa.ColumnClause[Any]:
    return sa.column(name, UUID(as_uuid=True))


organisms_t = sa.table(
    "organisms", _uuid_col("id"), sa.column("name"), sa.column("kingdom"),
    sa.column("ncbi_taxon_id"), sa.column("kegg_organism_code"), sa.column("source_version"),
)  # fmt: skip
enzymes_t = sa.table(
    "enzymes", _uuid_col("id"), sa.column("ec_number"), sa.column("name"),
    sa.column("kegg_entry_id"), sa.column("source_version"),
)  # fmt: skip
compounds_t = sa.table(
    "compounds", _uuid_col("id"), sa.column("kegg_compound_id"), sa.column("name"),
    sa.column("category"), sa.column("source_version"),
)  # fmt: skip
organism_enzymes_t = sa.table(
    "organism_enzymes", _uuid_col("id"), _uuid_col("organism_id"), _uuid_col("enzyme_id")
)
enzyme_reactions_t = sa.table(
    "enzyme_reactions", _uuid_col("id"), _uuid_col("enzyme_id"), _uuid_col("substrate_id"),
    _uuid_col("product_id"),
)  # fmt: skip
fermentation_type_organisms_t = sa.table(
    "fermentation_type_organisms", _uuid_col("id"), sa.column("fermentation_type"),
    _uuid_col("organism_id"), sa.column("is_default", sa.Boolean()),
)  # fmt: skip
batch_organisms_t = sa.table("batch_organisms", _uuid_col("organism_id"))


def _ids(table: sa.TableClause, key_col: str) -> dict[str, uuid.UUID]:
    """Live natural key -> id for one reference table."""
    rows = op.get_bind().execute(sa.select(table.c[key_col], table.c.id))
    return {key: id_ for key, id_ in rows}


def _link_rows(delta: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, uuid.UUID]]]:
    """Delta link rows resolved to live ids (after the delta's own rows exist).

    Each row is {column: id, ...}; a link may join a v1 row to a v2 row or two v1 rows.
    """
    org = _ids(organisms_t, "name")
    enz = _ids(enzymes_t, "ec_number")
    cpd = _ids(compounds_t, "kegg_compound_id")
    return {
        "organism_enzymes": [
            {"organism_id": org[r["organism"]], "enzyme_id": enz[r["ec_number"]]}
            for r in delta["organism_enzymes"]
        ],
        "enzyme_reactions": [
            {
                "enzyme_id": enz[r["ec_number"]],
                "substrate_id": cpd[r["substrate_kegg_id"]],
                "product_id": cpd[r["product_kegg_id"]],
            }
            for r in delta["enzyme_reactions"]
        ],
        "fermentation_type_organisms": [
            {"fermentation_type": r["fermentation_type"], "organism_id": org[r["organism"]]}
            for r in delta["fermentation_type_organisms"]
        ],
    }


def _delta() -> dict[str, list[dict[str, Any]]]:
    # Both snapshots are frozen, so this migration stays a faithful record of what it changed.
    return snapshot_delta(load_snapshot(KEGG_BIOCHEM_V1), load_snapshot(KEGG_BIOCHEM_V2))


def _insert(table: sa.TableClause, rows: list[dict[str, Any]]) -> None:
    if rows:
        op.bulk_insert(table, rows)


def _insert_new_links(table: sa.TableClause, rows: list[dict[str, Any]], **defaults: Any) -> None:
    if not rows:
        return
    cols = list(rows[0])
    existing = set(op.get_bind().execute(sa.select(*[table.c[c] for c in cols])).tuples())
    _insert(table, [
        {"id": uuid.uuid4(), **defaults, **r}
        for r in rows if tuple(r[c] for c in cols) not in existing
    ])  # fmt: skip


def upgrade() -> None:
    delta = _delta()

    # Defensive idempotence: skip anything whose natural key already exists.
    have_org = set(_ids(organisms_t, "name"))
    have_enz = set(_ids(enzymes_t, "ec_number"))
    have_cpd = set(_ids(compounds_t, "kegg_compound_id"))
    _insert(organisms_t, [
        {
            "id": uuid.uuid4(), "name": o["name"], "kingdom": o["kingdom"],
            "ncbi_taxon_id": None, "kegg_organism_code": None, "source_version": V2_TAG,
        }
        for o in delta["organisms"] if o["name"] not in have_org
    ])  # fmt: skip
    _insert(enzymes_t, [
        {
            "id": uuid.uuid4(), "ec_number": e["ec_number"], "name": e["name"],
            "kegg_entry_id": None, "source_version": V2_TAG,
        }
        for e in delta["enzymes"] if e["ec_number"] not in have_enz
    ])  # fmt: skip
    _insert(compounds_t, [
        {
            "id": uuid.uuid4(), "kegg_compound_id": c["kegg_compound_id"], "name": c["name"],
            "category": c["category"], "source_version": V2_TAG,
        }
        for c in delta["compounds"] if c["kegg_compound_id"] not in have_cpd
    ])  # fmt: skip

    links = _link_rows(delta)
    _insert_new_links(organism_enzymes_t, links["organism_enzymes"])
    _insert_new_links(enzyme_reactions_t, links["enzyme_reactions"])
    _insert_new_links(
        fermentation_type_organisms_t, links["fermentation_type_organisms"], is_default=True
    )


def downgrade() -> None:
    delta = _delta()
    conn = op.get_bind()
    links = _link_rows(delta)  # resolve ids before anything is deleted

    for table, rows in (
        (organism_enzymes_t, links["organism_enzymes"]),
        (enzyme_reactions_t, links["enzyme_reactions"]),
        (fermentation_type_organisms_t, links["fermentation_type_organisms"]),
    ):
        for r in rows:
            conn.execute(sa.delete(table).where(*[table.c[k] == v for k, v in r.items()]))

    # batch_organisms rows pointing at v2 organisms would dangle once those are deleted.
    v2_org_ids = list(conn.execute(
        sa.select(organisms_t.c.id).where(
            organisms_t.c.name.in_([o["name"] for o in delta["organisms"]]),
            organisms_t.c.source_version == V2_TAG,
        )
    ).scalars())
    if v2_org_ids:
        conn.execute(sa.delete(batch_organisms_t).where(
            batch_organisms_t.c.organism_id.in_(v2_org_ids)
        ))
        conn.execute(sa.delete(organisms_t).where(organisms_t.c.id.in_(v2_org_ids)))
    conn.execute(sa.delete(enzymes_t).where(
        enzymes_t.c.ec_number.in_([e["ec_number"] for e in delta["enzymes"]]),
        enzymes_t.c.source_version == V2_TAG,
    ))
    conn.execute(sa.delete(compounds_t).where(
        compounds_t.c.kegg_compound_id.in_([c["kegg_compound_id"] for c in delta["compounds"]]),
        compounds_t.c.source_version == V2_TAG,
    ))  # fmt: skip
