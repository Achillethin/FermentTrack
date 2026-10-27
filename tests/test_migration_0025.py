"""Migration 0025 (the Noma and Katz round's ingredients and their USDA nutrients) on a
throwaway SQLite file. Reuses 0009's fixture."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command
from fermenttrack.seed_data import INGREDIENT_FDC_IDS_V5, INGREDIENT_SEED_DATA_V5

NAMES = {n for n, _r, _s in INGREDIENT_SEED_DATA_V5}


def _state(engine: sa.Engine) -> tuple[set[str], dict[str, int | None], dict[str, float]]:
    """(V5 names present, their fdc_id, sugars_total per name from the copied nutrients)."""
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT name, fdc_id FROM ingredients")).all()
        sugars = c.execute(sa.text(
            "SELECT i.name, n.amount_per_100g FROM ingredient_nutrients n"
            " JOIN ingredients i ON i.id = n.ingredient_id"
            " WHERE n.nutrient = 'sugars_total' AND n.source = 'usda_fdc'"
        )).all()  # fmt: skip
    present = {n for n, _f in rows if n in NAMES}
    return present, {n: f for n, f in rows if n in NAMES}, {n: a for n, a in sugars if n in NAMES}


def test_0025_adds_the_round_2_ingredients_with_nutrients_and_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0024")
    assert _state(engine)[0] == set()
    command.upgrade(cfg, "0025")
    present, fdc, sugars = _state(engine)
    assert present == NAMES
    assert {n: f for n, f in fdc.items() if f is not None} == INGREDIENT_FDC_IDS_V5
    assert sugars["Blueberries"] == pytest.approx(9.96)
    assert sugars["Plums"] == pytest.approx(9.92)
    command.downgrade(cfg, "0024")
    assert _state(engine) == (set(), {}, {})
    command.upgrade(cfg, "0025")  # re-applies cleanly
    assert _state(engine)[0] == NAMES
