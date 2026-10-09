"""Migration 0021 (community_recipes, community_recipe_forecasts, recommendation_links'
community_recipe_id foreign key and parent_batch_id) on a throwaway SQLite file, FKs enforced.
Reuses 0009's fixture."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401
from test_migration_0019 import _culture_and_batch

from alembic import command
from fermenttrack.models import CommunityRecipe, CommunityRecipeForecast, RecommendationLink


def _columns(engine: sa.Engine, table: str) -> set[str] | None:
    insp = sa.inspect(engine)
    if not insp.has_table(table):
        return None
    return {c["name"] for c in insp.get_columns(table)}


def _fks(engine: sa.Engine, table: str) -> set[tuple[str, str, str | None]]:
    return {
        (fk["constrained_columns"][0], fk["referred_table"], fk["options"].get("ondelete"))
        for fk in sa.inspect(engine).get_foreign_keys(table)
    }


def _batch(c: sa.Connection, culture: str, batch: str) -> None:
    c.execute(
        sa.text(
            "INSERT INTO batches (id, culture_id, started_at, current_stage, stage_entered_at,"
            " outcome) VALUES (:id, :c, CURRENT_TIMESTAMP, 'x', CURRENT_TIMESTAMP, 'success')"
        ),
        {"id": batch, "c": culture},
    )


def _link(c: sa.Connection, batch: str, kind: str, key: str | None, **extra: str) -> None:
    columns = ", ".join(["batch_id", *extra])
    values = ", ".join([":b", *(f":{k}" for k in extra)])
    c.execute(
        sa.text(
            f"INSERT INTO recommendation_links ({columns}, source_kind, recipe_key, operators,"
            f" mode, temperature_c, window, targets, grid_version) VALUES ({values}, :kind,"
            " :key, '[]', 'experimental', 20.0, '{}', '[]', 'sha')"
        ),
        {"b": batch, "kind": kind, "key": key, **extra},
    )


def _links(engine: sa.Engine) -> dict[uuid.UUID, tuple[str | None, uuid.UUID | None]]:
    """batch_id -> (recipe_key, parent_batch_id)."""
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT * FROM recommendation_links")).mappings().all()
    return {
        uuid.UUID(str(r["batch_id"])): (
            r["recipe_key"],
            None if r.get("parent_batch_id") is None else uuid.UUID(str(r["parent_batch_id"])),
        )
        for r in rows
    }


def _recipe(c: sa.Connection, recipe: str, source_batch: str | None, status: str) -> None:
    c.execute(
        sa.text(
            "INSERT INTO community_recipes (id, owner_id, source_batch_id, pseudonym, title,"
            " fermentation_type, recipe, temperature_c, duration_h, status, created_at)"
            " VALUES (:id, 'alice', :b, 'Ana', 'Kraut', 'lacto_ferment', '[]', 20.0, 336.0,"
            " :status, CURRENT_TIMESTAMP)"
        ),
        {"id": recipe, "b": source_batch, "status": status},
    )


def test_0021_creates_the_model_s_tables_and_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0020")
    culture, batch = uuid.uuid4().hex, uuid.uuid4().hex
    with engine.begin() as c:  # a link written before 0021 survives the table copy both ways
        _culture_and_batch(c, culture, batch)
        _link(c, batch, "library", "milk_kefir_grains_5pct_24h")
    assert _columns(engine, "community_recipes") is None

    command.upgrade(cfg, "0021")
    for model in (CommunityRecipe, CommunityRecipeForecast, RecommendationLink):
        table = model.__table__
        assert _columns(engine, table.name) == {c.name for c in table.columns}, table.name
    assert _fks(engine, "recommendation_links") == {
        ("batch_id", "batches", "CASCADE"),
        ("community_recipe_id", "community_recipes", "SET NULL"),
        ("parent_batch_id", "batches", "SET NULL"),
    }
    assert _fks(engine, "community_recipes") == {("source_batch_id", "batches", "SET NULL")}
    assert _fks(engine, "community_recipe_forecasts") == {
        ("recipe_id", "community_recipes", "CASCADE")
    }
    pk = sa.inspect(engine).get_pk_constraint("community_recipe_forecasts")
    assert pk["constrained_columns"] == ["recipe_id", "temp_c"]  # one forecast per temperature
    indexes = {i["name"]: i for i in sa.inspect(engine).get_indexes("community_recipes")}
    assert set(indexes) == {i.name for i in CommunityRecipe.__table__.indexes}
    assert indexes["uq_community_recipes_source_batch"]["unique"]
    assert _links(engine) == {uuid.UUID(batch): ("milk_kefir_grains_5pct_24h", None)}

    command.downgrade(cfg, "0020")
    assert _columns(engine, "community_recipes") is None
    assert _columns(engine, "community_recipe_forecasts") is None
    assert "parent_batch_id" not in (_columns(engine, "recommendation_links") or set())
    assert _fks(engine, "recommendation_links") == {("batch_id", "batches", "CASCADE")}
    assert _links(engine) == {uuid.UUID(batch): ("milk_kefir_grains_5pct_24h", None)}
    command.upgrade(cfg, "0021")  # re-applies cleanly
    assert _columns(engine, "community_recipes") is not None


def test_0021_moves_legacy_parent_batches_into_parent_batch_id_and_back(db) -> None:  # noqa: F811
    """Own-batch links written before 0021 named the parent as recipe_key "batch:<id>"."""
    cfg, engine = db
    command.upgrade(cfg, "0020")
    culture, parent, moved, garbled, orphan, library = (uuid.uuid4().hex for _ in range(6))
    gone = uuid.uuid4()
    with engine.begin() as c:
        _culture_and_batch(c, culture, parent)
        for b in (moved, garbled, orphan, library):
            _batch(c, culture, b)
        _link(c, moved, "own_batch", f"batch:{uuid.UUID(parent)}")  # str(uuid), as B7 wrote it
        _link(c, garbled, "own_batch", "batch:not-a-uuid")
        _link(c, orphan, "own_batch", f"batch:{gone}")  # its parent batch was deleted
        _link(c, library, "library", "sauerkraut_dry_salted")
    command.upgrade(cfg, "0021")
    assert _links(engine) == {
        uuid.UUID(moved): (None, uuid.UUID(parent)),
        uuid.UUID(garbled): ("batch:not-a-uuid", None),
        uuid.UUID(orphan): (f"batch:{gone}", None),
        uuid.UUID(library): ("sauerkraut_dry_salted", None),
    }
    with engine.begin() as c:  # a link of 0021's own
        newer = uuid.uuid4().hex
        _batch(c, culture, newer)
        _link(c, newer, "own_batch", None, parent_batch_id=parent)
    command.downgrade(cfg, "0020")
    legacy = f"batch:{uuid.UUID(parent)}"
    assert _links(engine) == {
        uuid.UUID(moved): (legacy, None),
        uuid.UUID(garbled): ("batch:not-a-uuid", None),
        uuid.UUID(orphan): (f"batch:{gone}", None),
        uuid.UUID(library): ("sauerkraut_dry_salted", None),
        uuid.UUID(newer): (legacy, None),
    }


def test_0021_publishes_a_batch_once_until_rejected(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0021")
    culture, batch = uuid.uuid4().hex, uuid.uuid4().hex
    with engine.begin() as c:
        _culture_and_batch(c, culture, batch)
        _recipe(c, uuid.uuid4().hex, batch, "rejected")
        _recipe(c, uuid.uuid4().hex, batch, "rejected")  # rejections never conflict
        _recipe(c, uuid.uuid4().hex, batch, "pending")
        _recipe(c, uuid.uuid4().hex, None, "approved")  # detached recipes never conflict
        _recipe(c, uuid.uuid4().hex, None, "approved")
    for status in ("pending", "approved"):
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as c:
            _recipe(c, uuid.uuid4().hex, batch, status)


def test_0021_deletions_detach_or_cascade(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0021")
    culture, source, started, parent = (uuid.uuid4().hex for _ in range(4))
    recipe = uuid.uuid4().hex
    with engine.begin() as c:
        _culture_and_batch(c, culture, source)
        for b in (started, parent):
            _batch(c, culture, b)
        _recipe(c, recipe, source, "approved")
        c.execute(
            sa.text(
                "INSERT INTO community_recipe_forecasts (recipe_id, temp_c, grid_version, stats,"
                " created_at) VALUES (:r, 20.0, 'sha', '{}', CURRENT_TIMESTAMP)"
            ),
            {"r": recipe},
        )
        _link(c, started, "own_batch", None, community_recipe_id=recipe, parent_batch_id=parent)
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as c:  # one per temperature
        c.execute(
            sa.text(
                "INSERT INTO community_recipe_forecasts (recipe_id, temp_c, grid_version, stats,"
                " created_at) VALUES (:r, 20.0, 'other', '{}', CURRENT_TIMESTAMP)"
            ),
            {"r": recipe},
        )
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as c:
        _recipe(c, uuid.uuid4().hex, None, "published")  # not a status

    with engine.begin() as c:  # the source batch and the parent batch go: detached, kept
        c.execute(sa.text("DELETE FROM batches WHERE id IN (:a, :b)"), {"a": source, "b": parent})
    with engine.connect() as c:
        assert c.execute(sa.text("SELECT source_batch_id FROM community_recipes")).all() == [
            (None,)
        ]
        link = c.execute(sa.text("SELECT community_recipe_id, parent_batch_id FROM "
                                 "recommendation_links")).one()  # fmt: skip
        assert link[1] is None and uuid.UUID(str(link[0])) == uuid.UUID(recipe)

    with engine.begin() as c:  # the recipe goes: its forecasts with it, the link detached
        c.execute(sa.text("DELETE FROM community_recipes WHERE id = :r"), {"r": recipe})
    with engine.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM community_recipe_forecasts")).scalar() == 0
        assert c.execute(sa.text("SELECT community_recipe_id FROM recommendation_links")).all() == [
            (None,)
        ]
