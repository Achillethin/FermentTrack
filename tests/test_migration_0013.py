"""Migration 0013 (biochemistry v4: six pathway enzymes) on a throwaway SQLite file.

Reuses 0009's fixture and helpers: same portable-core migration style, same SQLite harness.
"""

from __future__ import annotations

import sqlalchemy as sa
from test_migration_0009 import TABLES, _add_override, _counts, _orgs, db  # noqa: F401

from alembic import command
from fermenttrack.biochem import KEGG_BIOCHEM_V3, load_snapshot, snapshot_delta
from fermenttrack.models import BatchOrganism, Enzyme, Organism, OrganismEnzyme

V3 = load_snapshot(KEGG_BIOCHEM_V3)
V4 = load_snapshot()
DELTA = snapshot_delta(V3, V4)


def _has_link(engine: sa.Engine, organism: str, ec: str) -> bool:
    with engine.connect() as c:
        q = (
            sa.select(sa.func.count())
            .select_from(OrganismEnzyme)
            .join(Organism, Organism.id == OrganismEnzyme.organism_id)
            .join(Enzyme, Enzyme.id == OrganismEnzyme.enzyme_id)
            .where(Organism.name == organism, Enzyme.ec_number == ec)
        )
        return c.execute(q).scalar_one() == 1


def test_0013_is_additive_and_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0012")
    v3_counts = _counts(engine)
    assert v3_counts == {t: len(V3[t]) for t in TABLES}
    orgs = _orgs(engine)
    override_id = _add_override(engine, orgs["Saccharomyces cerevisiae"][0], "kombucha")

    command.upgrade(cfg, "0013")
    v4_counts = _counts(engine)
    assert v4_counts == {t: v3_counts[t] + len(DELTA[t]) for t in TABLES}
    assert v4_counts == {t: len(V4[t]) for t in TABLES}
    assert _orgs(engine) == orgs  # organisms untouched
    assert _has_link(engine, "Saccharomyces cerevisiae", "3.2.1.26")
    assert _has_link(engine, "Lactococcus lactis", "3.2.1.85")
    assert not _has_link(engine, "Lactobacillus plantarum", "4.1.2.9")
    with engine.connect() as c:
        tags = set(c.execute(sa.select(Enzyme.source_version)).scalars())
        assert "kegg_biochem_v4" in tags

    command.downgrade(cfg, "0012")
    assert _counts(engine) == v3_counts
    with engine.connect() as c:
        assert c.execute(sa.select(BatchOrganism.id)).scalar_one() == override_id

    command.upgrade(cfg, "0013")  # re-applies cleanly
    assert _counts(engine) == v4_counts
