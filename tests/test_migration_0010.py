"""Migration 0010 (garum gains Aspergillus oryzae) on a throwaway SQLite file, FKs enforced.

Reuses 0009's fixture and helpers: same portable-core migration style, same SQLite harness.
"""

from __future__ import annotations

import importlib.util

import pytest
import sqlalchemy as sa
from test_migration_0009 import (  # noqa: F401
    ROOT,
    TABLES,
    V1,
    V2,
    _add_override,
    _counts,
    _orgs,
    db,
)

from alembic import command
from fermenttrack.biochem import KEGG_BIOCHEM_V3, load_snapshot, snapshot_delta
from fermenttrack.models import BatchOrganism, FermentationTypeOrganism, Organism

V3 = load_snapshot(KEGG_BIOCHEM_V3)
DELTA = snapshot_delta(V2, V3)
KOJI_GARUM = {"fermentation_type": "garum", "organism": "Aspergillus oryzae"}


def _garum_defaults(engine: sa.Engine) -> dict[str, bool]:
    with engine.connect() as c:
        rows = c.execute(
            sa.select(Organism.name, FermentationTypeOrganism.is_default)
            .join(FermentationTypeOrganism, FermentationTypeOrganism.organism_id == Organism.id)
            .where(FermentationTypeOrganism.fermentation_type == "garum")
        )
        return dict(rows.all())


def _override_ids(engine: sa.Engine) -> list:
    with engine.connect() as c:
        return c.execute(sa.select(BatchOrganism.id)).scalars().all()


def test_0010_adds_one_garum_link_and_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0009")
    v2_counts = _counts(engine)
    assert v2_counts == {t: len(V2[t]) for t in TABLES}
    assert _garum_defaults(engine) == {"Tetragenococcus halophilus": True}

    orgs = _orgs(engine)
    override_id = _add_override(engine, orgs["Saccharomyces cerevisiae"][0], "garum")

    command.upgrade(cfg, "0010")
    v3_counts = _counts(engine)
    assert v3_counts == {**v2_counts, "fermentation_type_organisms": v2_counts[
        "fermentation_type_organisms"] + 1}  # fmt: skip
    assert v3_counts == {t: len(V3[t]) for t in TABLES}
    assert _garum_defaults(engine) == {
        "Tetragenococcus halophilus": True, "Aspergillus oryzae": True,
    }
    assert _orgs(engine) == orgs  # nothing re-id'd or re-tagged
    assert _override_ids(engine) == [override_id]

    command.downgrade(cfg, "0009")
    assert _counts(engine) == v2_counts
    assert _garum_defaults(engine) == {"Tetragenococcus halophilus": True}
    assert _override_ids(engine) == [override_id]

    command.upgrade(cfg, "0010")  # re-applies cleanly
    assert _counts(engine) == v3_counts


def test_0010_delta_is_exactly_the_koji_garum_link() -> None:
    assert {t: r for t, r in DELTA.items() if r} == {"fermentation_type_organisms": [KOJI_GARUM]}


def test_0010_guard_refuses_non_link_deltas() -> None:
    path = ROOT / "alembic" / "versions" / "0010_biochemistry_v3.py"
    spec = importlib.util.spec_from_file_location("mig_0010", path)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    assert mig.links_only(DELTA) == [KOJI_GARUM]
    v1_to_v2 = snapshot_delta(V1, V2)  # carries new organisms, enzymes, compounds, ...
    with pytest.raises(RuntimeError, match="only adds fermentation_type_organisms"):
        mig.links_only(v1_to_v2)
    only_org = {t: [] for t in DELTA} | {"organisms": v1_to_v2["organisms"][:1]}
    with pytest.raises(RuntimeError, match="organisms"):
        mig.links_only(only_org)
