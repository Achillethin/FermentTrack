# alembic/versions/0013_biochemistry_v4.py
"""biochemistry v4: the six pathway enzymes the fermentation forecast relies on

Adds exactly `snapshot_delta(v3, v4)`: invertase (3.2.1.26), phosphoketolase (4.1.2.9),
PQQ glucose dehydrogenase (1.1.5.2), maltose phosphorylase (2.4.1.8),
6-phospho-beta-galactosidase (3.2.1.85) and cellulose synthase (2.4.1.12), their
compounds, representative reactions and organism links (each backed by a KEGG gene
annotation, docs/superpowers/specs/2026-09-25-biochemistry-v4-curation.md). No organisms
or fermentation-type links change. Existing rows are never deleted or re-id'd; downgrade
removes only what this migration added (by natural key and the v4 source tag).

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-25

"""
from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op
from fermenttrack.biochem import KEGG_BIOCHEM_V3, KEGG_BIOCHEM_V4, load_snapshot, snapshot_delta

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

V4_TAG = "kegg_biochem_v4"


def _uuid_col(name: str) -> sa.ColumnClause[Any]:
    return sa.column(name, UUID(as_uuid=True))


organisms_t = sa.table("organisms", _uuid_col("id"), sa.column("name"))
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


def _delta() -> dict[str, list[dict[str, Any]]]:
    # Both snapshots are frozen, so this migration stays a faithful record of what it changed.
    delta = snapshot_delta(load_snapshot(KEGG_BIOCHEM_V3), load_snapshot(KEGG_BIOCHEM_V4))
    unexpected = {
        t: len(delta[t]) for t in ("organisms", "fermentation_type_organisms") if delta[t]
    }
    if unexpected:
        raise RuntimeError(f"0013 adds no organisms or type links; delta has {unexpected}")
    return delta


def _ids(table: sa.TableClause, key_col: str) -> dict[str, uuid.UUID]:
    rows = op.get_bind().execute(sa.select(table.c[key_col], table.c.id))
    return {key: id_ for key, id_ in rows}


def _link_rows(delta: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, uuid.UUID]]]:
    """Delta link rows resolved to live ids (after the delta's own rows exist)."""
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
    }


def _insert_new(table: sa.TableClause, rows: list[dict[str, Any]]) -> None:
    """Insert link rows whose natural key does not exist yet (defensive idempotence)."""
    if not rows:
        return
    cols = list(rows[0])
    existing = set(op.get_bind().execute(sa.select(*[table.c[c] for c in cols])).tuples())
    new = [{"id": uuid.uuid4(), **r} for r in rows if tuple(r[c] for c in cols) not in existing]
    if new:
        op.bulk_insert(table, new)


def upgrade() -> None:
    delta = _delta()
    have_enz = set(_ids(enzymes_t, "ec_number"))
    have_cpd = set(_ids(compounds_t, "kegg_compound_id"))
    enzymes = [
        {
            "id": uuid.uuid4(), "ec_number": e["ec_number"], "name": e["name"],
            "kegg_entry_id": None, "source_version": V4_TAG,
        }
        for e in delta["enzymes"] if e["ec_number"] not in have_enz
    ]  # fmt: skip
    compounds = [
        {
            "id": uuid.uuid4(), "kegg_compound_id": c["kegg_compound_id"], "name": c["name"],
            "category": c["category"], "source_version": V4_TAG,
        }
        for c in delta["compounds"] if c["kegg_compound_id"] not in have_cpd
    ]  # fmt: skip
    if enzymes:
        op.bulk_insert(enzymes_t, enzymes)
    if compounds:
        op.bulk_insert(compounds_t, compounds)
    links = _link_rows(delta)
    _insert_new(organism_enzymes_t, links["organism_enzymes"])
    _insert_new(enzyme_reactions_t, links["enzyme_reactions"])


def downgrade() -> None:
    delta = _delta()
    conn = op.get_bind()
    links = _link_rows(delta)  # resolve ids before anything is deleted
    for table, rows in (
        (organism_enzymes_t, links["organism_enzymes"]),
        (enzyme_reactions_t, links["enzyme_reactions"]),
    ):
        for r in rows:
            conn.execute(sa.delete(table).where(*[table.c[k] == v for k, v in r.items()]))
    conn.execute(sa.delete(enzymes_t).where(
        enzymes_t.c.ec_number.in_([e["ec_number"] for e in delta["enzymes"]]),
        enzymes_t.c.source_version == V4_TAG,
    ))
    conn.execute(sa.delete(compounds_t).where(
        compounds_t.c.kegg_compound_id.in_([c["kegg_compound_id"] for c in delta["compounds"]]),
        compounds_t.c.source_version == V4_TAG,
    ))  # fmt: skip
