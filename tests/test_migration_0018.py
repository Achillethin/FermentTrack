"""Migration 0018 (USDA nutrients for the aroma ingredients) on a throwaway SQLite file.
Reuses 0009's fixture."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command
from fermenttrack.seed_data import INGREDIENT_FDC_IDS_V4


def _nutrients(engine: sa.Engine) -> dict[str, dict[str, float]]:
    with engine.connect() as c:
        rows = c.execute(sa.text(
            "SELECT i.name, n.nutrient, n.amount_per_100g FROM ingredient_nutrients n"
            " JOIN ingredients i ON i.id = n.ingredient_id"
            " WHERE n.source = 'usda_fdc' AND n.source_version = 'fdc_catalog_v1'"
        ))  # fmt: skip
        out: dict[str, dict[str, float]] = {}
        for name, nutrient, amount in rows:
            out.setdefault(name, {})[nutrient] = amount
        return out


def _fdc_ids(engine: sa.Engine) -> dict[str, int | None]:
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT name, fdc_id FROM ingredients"))
        return {n: f for n, f in rows if n in INGREDIENT_FDC_IDS_V4}


def test_0018_gives_the_aroma_ingredients_their_usda_nutrients(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0017")
    assert not set(_nutrients(engine)) & set(INGREDIENT_FDC_IDS_V4)
    command.upgrade(cfg, "0018")
    got = _nutrients(engine)
    for name in INGREDIENT_FDC_IDS_V4:
        assert len(got.get(name, {})) >= 5, name
    assert got["Napa cabbage"]["sugars_total"] == pytest.approx(1.41)
    assert got["Carrot"]["sugars_total"] == pytest.approx(4.74)
    assert _fdc_ids(engine) == INGREDIENT_FDC_IDS_V4
    command.downgrade(cfg, "0017")
    assert not set(_nutrients(engine)) & set(INGREDIENT_FDC_IDS_V4)
    assert set(_fdc_ids(engine).values()) == {None}
    command.upgrade(cfg, "0018")  # re-applies cleanly
    assert _fdc_ids(engine) == INGREDIENT_FDC_IDS_V4


def test_0018_keeps_an_fdc_id_a_user_already_picked(db) -> None:  # noqa: F811
    """A user may have added "Cucumber, with peel, raw" through USDA search already: the
    unique fdc_id stays with that row, and the curated Cucumber still gets its nutrients."""
    cfg, engine = db
    command.upgrade(cfg, "0017")
    with engine.begin() as c:
        c.execute(
            sa.text(
                "INSERT INTO ingredients (id, name, default_role, fermentation_systems,"
                " is_active, fdc_id) VALUES (:id, 'Cucumber, with peel, raw', 'base',"
                " '[\"lacto_ferment\"]', 1, 168409)"
            ),
            {"id": uuid.uuid4().hex},
        )
    command.upgrade(cfg, "0018")
    assert _fdc_ids(engine)["Cucumber"] is None
    assert _nutrients(engine)["Cucumber"]["sugars_total"] == pytest.approx(1.67)
