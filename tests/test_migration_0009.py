"""Migration 0009 (additive biochemistry v2) on a throwaway SQLite file.

Postgres is the production target but unavailable locally; the migration uses only
portable SQLAlchemy core constructs, so SQLite exercises the same logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from fermenttrack.biochem import KEGG_BIOCHEM_V1, KEGG_BIOCHEM_V2, load_snapshot, snapshot_delta
from fermenttrack.config import settings
from fermenttrack.models import (
    BatchOrganism,
    Compound,
    Enzyme,
    EnzymeReaction,
    FermentationTypeOrganism,
    Organism,
    OrganismEnzyme,
)

ROOT = Path(__file__).resolve().parent.parent
V1, V2 = load_snapshot(KEGG_BIOCHEM_V1), load_snapshot(KEGG_BIOCHEM_V2)
DELTA = snapshot_delta(V1, V2)
TABLES = {
    "organisms": Organism,
    "enzymes": Enzyme,
    "compounds": Compound,
    "organism_enzymes": OrganismEnzyme,
    "enzyme_reactions": EnzymeReaction,
    "fermentation_type_organisms": FermentationTypeOrganism,
}


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    url = f"sqlite:///{tmp_path / 'mig.db'}"
    monkeypatch.setattr(settings, "database_url", url)  # env.py reads settings at each run
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    engine = sa.create_engine(url)
    yield cfg, engine
    engine.dispose()


CULTURES = sa.Table(
    "cultures", sa.MetaData(),
    sa.Column("id", sa.Uuid), sa.Column("name", sa.Text), sa.Column("type", sa.Text),
    sa.Column("status", sa.Text), sa.Column("created_at", sa.DateTime(timezone=True)),
)  # fmt: skip
BATCHES = sa.Table(
    "batches", sa.MetaData(),
    sa.Column("id", sa.Uuid), sa.Column("culture_id", sa.Uuid),
    sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("current_stage", sa.Text),
    sa.Column("stage_entered_at", sa.DateTime(timezone=True)), sa.Column("outcome", sa.Text),
)  # fmt: skip


def _add_override(engine: sa.Engine, organism_id: uuid.UUID, ctype: str) -> uuid.UUID:
    """Culture + batch + a batch_organisms override row; returns the override row id."""
    culture_id, batch_id, override_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    with engine.begin() as c:
        c.execute(sa.insert(CULTURES).values(
            id=culture_id, name="c", type=ctype, status="active", created_at=now
        ))
        c.execute(sa.insert(BATCHES).values(
            id=batch_id, culture_id=culture_id, started_at=now, current_stage="s",
            stage_entered_at=now, outcome="in_progress",
        ))
        c.execute(sa.insert(BatchOrganism).values(
            id=override_id, batch_id=batch_id, organism_id=organism_id, source="custom",
            created_at=now,
        ))
    return override_id


def _counts(engine: sa.Engine) -> dict[str, int]:
    with engine.connect() as c:
        return {t: c.execute(sa.select(sa.func.count()).select_from(m)).scalar_one()
                for t, m in TABLES.items()}  # fmt: skip


def _orgs(engine: sa.Engine) -> dict[str, tuple[uuid.UUID, str]]:
    with engine.connect() as c:
        rows = c.execute(sa.select(Organism.name, Organism.id, Organism.source_version))
        return {n: (i, v) for n, i, v in rows}


def _link_exists(engine: sa.Engine, organism: str, ec: str) -> bool:
    with engine.connect() as c:
        q = (
            sa.select(sa.func.count())
            .select_from(OrganismEnzyme)
            .join(Organism, Organism.id == OrganismEnzyme.organism_id)
            .join(Enzyme, Enzyme.id == OrganismEnzyme.enzyme_id)
            .where(Organism.name == organism, Enzyme.ec_number == ec)
        )
        return c.execute(q).scalar_one() == 1


def test_0009_is_additive_and_reversible(db) -> None:
    cfg, engine = db
    command.upgrade(cfg, "0008")
    v1_counts = _counts(engine)
    assert v1_counts == {t: len(V1[t]) for t in TABLES}

    # A batch overriding its organisms with an existing v1 reference organism.
    v1_orgs = _orgs(engine)
    yeast_id = v1_orgs["Saccharomyces cerevisiae"][0]
    override_id = _add_override(engine, yeast_id, "koji")

    command.upgrade(cfg, "0009")
    v2_counts = _counts(engine)
    assert v2_counts == {t: v1_counts[t] + len(DELTA[t]) for t in TABLES}
    assert v2_counts == {t: len(V2[t]) for t in TABLES}
    v2_orgs = _orgs(engine)
    assert all(v2_orgs[n] == (i, v) for n, (i, v) in v1_orgs.items())  # ids/tags untouched
    assert {n for n, (_, v) in v2_orgs.items() if v == "kegg_biochem_v2"} == {
        o["name"] for o in DELTA["organisms"]
    }
    with engine.connect() as c:
        assert c.execute(sa.select(BatchOrganism.organism_id)).scalar_one() == yeast_id
        tags = {
            m: {r for (r,) in c.execute(sa.select(m.source_version))}
            for m in (Organism, Enzyme, Compound)
        }
        assert all(t == {"kegg_biochem_v1", "kegg_biochem_v2"} for t in tags.values())
        miso = c.execute(
            sa.select(Organism.name)
            .join(FermentationTypeOrganism, FermentationTypeOrganism.organism_id == Organism.id)
            .where(FermentationTypeOrganism.fermentation_type == "miso")
        ).scalars().all()
        eth = sa.orm.aliased(Compound)
        ald = sa.orm.aliased(Compound)
        adh_q = c.execute(
            sa.select(sa.func.count())
            .select_from(EnzymeReaction)
            .join(Enzyme, Enzyme.id == EnzymeReaction.enzyme_id)
            .join(eth, eth.id == EnzymeReaction.substrate_id)
            .join(ald, ald.id == EnzymeReaction.product_id)
            .where(Enzyme.ec_number == "1.1.5.5", eth.name == "Ethanol", ald.name == "Acetaldehyde")
        ).scalar_one()
    assert "Zygosaccharomyces rouxii" in miso and "Aspergillus oryzae" in miso  # v1 + v2 link
    assert adh_q == 1
    assert _link_exists(engine, "Leuconostoc mesenteroides", "1.1.1.28")
    assert not _link_exists(engine, "Leuconostoc mesenteroides", "1.1.1.27")
    assert _link_exists(engine, "Tetragenococcus halophilus", "1.1.1.27")  # v1 org, v1 enzyme
    assert _link_exists(engine, "Lactobacillus plantarum", "1.1.1.28")  # v1 org, v2 enzyme

    command.downgrade(cfg, "0008")
    assert _counts(engine) == v1_counts
    assert _orgs(engine) == v1_orgs
    with engine.connect() as c:
        assert c.execute(sa.select(BatchOrganism.id)).scalar_one() == override_id

    command.upgrade(cfg, "0009")  # re-applies cleanly
    assert _counts(engine) == v2_counts


def test_0009_downgrade_drops_overrides_on_v2_organisms(db) -> None:
    cfg, engine = db
    command.upgrade(cfg, "0009")
    zr = _orgs(engine)["Zygosaccharomyces rouxii"][0]
    _add_override(engine, zr, "miso")
    command.downgrade(cfg, "0008")  # would leave a dangling row otherwise
    with engine.connect() as c:
        assert c.execute(sa.select(sa.func.count()).select_from(BatchOrganism)).scalar_one() == 0
