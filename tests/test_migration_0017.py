"""Migration 0017 (aroma ingredients in the catalogue) on a throwaway SQLite file. Reuses
0009's fixture."""

from __future__ import annotations

import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command
from fermenttrack.seed_data import INGREDIENT_SEED_DATA_V4

NEW = {n for n, _r, _s in INGREDIENT_SEED_DATA_V4}


def _active(engine: sa.Engine) -> set[str]:
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT name, is_active FROM ingredients"))
        return {n for n, active in rows if active and n in NEW}


def test_0017_aroma_ingredients_are_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0016")
    assert _active(engine) == set()
    command.upgrade(cfg, "0017")
    assert _active(engine) == NEW
    command.downgrade(cfg, "0016")
    assert _active(engine) == set()
    command.upgrade(cfg, "0017")  # re-applies cleanly
    assert _active(engine) == NEW
