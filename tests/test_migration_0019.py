"""Migration 0019 (recommendation_links) on a throwaway SQLite file, FKs enforced. Reuses 0009's
fixture."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command
from fermenttrack.models import RecommendationLink


def _columns(engine: sa.Engine) -> set[str] | None:
    insp = sa.inspect(engine)
    if not insp.has_table("recommendation_links"):
        return None
    return {c["name"] for c in insp.get_columns("recommendation_links")}


def _reminder_columns(engine: sa.Engine) -> set[str]:
    return {c["name"] for c in sa.inspect(engine).get_columns("reminders")}


def test_0019_existing_reminders_are_stage_reminders(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0018")
    culture, batch = uuid.uuid4().hex, uuid.uuid4().hex
    with engine.begin() as c:
        _culture_and_batch(c, culture, batch)
        c.execute(
            sa.text(
                "INSERT INTO reminders (id, batch_id, action, due_at, urgency)"
                " VALUES (:id, :b, 'taste', CURRENT_TIMESTAMP, 'medium')"
            ),
            {"id": uuid.uuid4().hex, "b": batch},
        )
    command.upgrade(cfg, "0019")
    with engine.connect() as c:
        assert c.execute(sa.text("SELECT kind FROM reminders")).scalars().all() == ["stage"]


def _culture_and_batch(c: sa.Connection, culture: str, batch: str) -> None:
    c.execute(
        sa.text(
            "INSERT INTO cultures (id, name, type, status, created_at)"
            " VALUES (:id, 'k', 'kefir', 'active', CURRENT_TIMESTAMP)"
        ),
        {"id": culture},
    )
    c.execute(
        sa.text(
            "INSERT INTO batches (id, culture_id, started_at, current_stage,"
            " stage_entered_at, outcome) VALUES (:id, :c, CURRENT_TIMESTAMP, 'in_progress',"
            " CURRENT_TIMESTAMP, 'in_progress')"
        ),
        {"id": batch, "c": culture},
    )


def test_0019_creates_the_model_s_table_and_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0018")
    assert _columns(engine) is None
    assert "kind" not in _reminder_columns(engine)
    command.upgrade(cfg, "0019")
    assert _columns(engine) == {c.name for c in RecommendationLink.__table__.columns}
    assert "kind" in _reminder_columns(engine)
    fks = sa.inspect(engine).get_foreign_keys("recommendation_links")
    assert [(fk["referred_table"], fk["options"].get("ondelete")) for fk in fks] == [
        ("batches", "CASCADE")
    ]
    command.downgrade(cfg, "0018")
    assert _columns(engine) is None
    assert "kind" not in _reminder_columns(engine)
    command.upgrade(cfg, "0019")  # re-applies cleanly
    assert _columns(engine) is not None


def test_0019_a_link_goes_with_its_batch(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0019")
    culture, batch = uuid.uuid4().hex, uuid.uuid4().hex
    with engine.begin() as c:
        _culture_and_batch(c, culture, batch)
        c.execute(
            sa.text(
                "INSERT INTO recommendation_links (batch_id, source_kind, recipe_key, operators,"
                " mode, temperature_c, window, targets, grid_version) VALUES (:b, 'library',"
                " 'milk_kefir_grains_5pct_24h', '[]', 'proven', 22.0, '{}', '[]', 'sha')"
            ),
            {"b": batch},
        )
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM batches WHERE id = :id"), {"id": batch})
        assert c.execute(sa.text("SELECT count(*) FROM recommendation_links")).scalar() == 0
