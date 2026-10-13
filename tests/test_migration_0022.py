"""Migration 0022 (tastings; recommendation_links.p_series) on a throwaway SQLite file, FKs
enforced. Reuses 0009's fixture."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401
from test_migration_0019 import _culture_and_batch
from test_migration_0021 import _columns, _fks, _link

from alembic import command
from fermenttrack.models import RecommendationLink, Tasting

LINK_FKS = {
    ("batch_id", "batches", "CASCADE"),
    ("community_recipe_id", "community_recipes", "SET NULL"),
    ("parent_batch_id", "batches", "SET NULL"),
}


def _tasting(c: sa.Connection, batch: str, t_h: float = 30.0, liking: int | None = 4) -> None:
    c.execute(
        sa.text(
            "INSERT INTO tastings (id, batch_id, t_h, ratings, liking, make_again, notes,"
            " created_at) VALUES (:id, :b, :t, '{\"sour\": 2}', :liking, 1, 'mine',"
            " CURRENT_TIMESTAMP)"
        ),
        {"id": uuid.uuid4().hex, "b": batch, "t": t_h, "liking": liking},
    )


def _count(engine: sa.Engine, table: str) -> int:
    with engine.connect() as c:
        return int(c.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one())


def test_0022_creates_tastings_and_p_series_and_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0021")
    culture, batch = uuid.uuid4().hex, uuid.uuid4().hex
    with engine.begin() as c:  # a link written before 0022 keeps p_series null
        _culture_and_batch(c, culture, batch)
        _link(c, batch, "library", "milk_kefir_grains_5pct_24h")
    assert _columns(engine, "tastings") is None

    command.upgrade(cfg, "0022")
    assert _columns(engine, "tastings") == {c.name for c in Tasting.__table__.columns}
    assert _columns(engine, "recommendation_links") == {
        c.name for c in RecommendationLink.__table__.columns
    }
    assert _fks(engine, "tastings") == {("batch_id", "batches", "CASCADE")}
    assert _fks(engine, "recommendation_links") == LINK_FKS
    indexes = {i["name"] for i in sa.inspect(engine).get_indexes("tastings")}
    assert indexes == {i.name for i in Tasting.__table__.indexes} == {"ix_tastings_batch_id"}
    with engine.connect() as c:
        row = c.execute(sa.text("SELECT recipe_key, p_series FROM recommendation_links")).one()
    assert tuple(row) == ("milk_kefir_grains_5pct_24h", None)  # nothing backfilled

    with engine.begin() as c:
        _tasting(c, batch)
    command.downgrade(cfg, "0021")
    assert _columns(engine, "tastings") is None
    assert "p_series" not in (_columns(engine, "recommendation_links") or set())
    assert _fks(engine, "recommendation_links") == LINK_FKS  # the table copy keeps them
    with engine.connect() as c:
        keys = c.execute(sa.text("SELECT recipe_key FROM recommendation_links")).scalars().all()
    assert keys == ["milk_kefir_grains_5pct_24h"]
    command.upgrade(cfg, "0022")  # re-applies cleanly
    assert _columns(engine, "tastings") is not None


def test_0022_tastings_go_with_their_batch_and_are_checked(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0022")
    culture, batch, other = uuid.uuid4().hex, uuid.uuid4().hex, uuid.uuid4().hex
    with engine.begin() as c:
        _culture_and_batch(c, culture, batch)
        _culture_and_batch(c, uuid.uuid4().hex, other)
        _tasting(c, batch)
        _tasting(c, batch, t_h=0.0, liking=None)  # ratings only, at the start
        _tasting(c, other)
    for t_h, liking in ((-0.5, 4), (30.0, 0), (30.0, 6)):
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as c:
            _tasting(c, batch, t_h, liking)
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as c:
        _tasting(c, uuid.uuid4().hex)  # no such batch
    assert _count(engine, "tastings") == 3

    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM batches WHERE id = :id"), {"id": batch})
    with engine.connect() as c:
        left = c.execute(sa.text("SELECT batch_id FROM tastings")).scalars().all()
    assert [uuid.UUID(str(b)) for b in left] == [uuid.UUID(other)]
