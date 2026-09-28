"""Migration 0016 (sourdough engine: cultures.style, batches.sourdough_plan, batch_evidence,
three organisms) on a throwaway SQLite file, FKs enforced. Reuses 0009's fixture."""

from __future__ import annotations

import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command

NEW = {"Kazachstania humilis", "Lactobacillus brevis", "Lactobacillus reuteri"}


def _state(engine: sa.Engine) -> tuple[set[str], set[str], bool, set[str]]:
    insp = sa.inspect(engine)
    with engine.connect() as c:
        names = {r[0] for r in c.execute(sa.text("SELECT name FROM organisms"))}
    return (
        {col["name"] for col in insp.get_columns("cultures")},
        {col["name"] for col in insp.get_columns("batches")},
        insp.has_table("batch_evidence"),
        names & NEW,
    )


def test_0016_sourdough_engine_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0015")
    cultures, batches, evidence, organisms = _state(engine)
    assert "style" not in cultures and "sourdough_plan" not in batches
    assert not evidence and not organisms

    command.upgrade(cfg, "0016")
    cultures, batches, evidence, organisms = _state(engine)
    assert "style" in cultures and "sourdough_plan" in batches
    assert evidence and organisms == NEW

    command.downgrade(cfg, "0015")
    cultures, batches, evidence, organisms = _state(engine)
    assert "style" not in cultures and not evidence and not organisms

    command.upgrade(cfg, "0016")  # re-applies cleanly
    assert _state(engine)[3] == NEW
