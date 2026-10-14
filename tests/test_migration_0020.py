"""Migration 0020 (recommendation_jobs) on a throwaway SQLite file. Reuses 0009's fixture."""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command
from fermenttrack.models import RecommendationJob


def _columns(engine: sa.Engine) -> set[str] | None:
    insp = sa.inspect(engine)
    if not insp.has_table("recommendation_jobs"):
        return None
    return {c["name"] for c in insp.get_columns("recommendation_jobs")}


def _insert(c: sa.Connection, owner: str | None, status: str) -> None:
    c.execute(
        sa.text(
            "INSERT INTO recommendation_jobs (id, owner_id, kind, request, fingerprint, status,"
            " done, total, results, attempts, created_at) VALUES (:id, :owner, 'deep_search',"
            " '{}', 'fp', :status, 0, 0, '[]', 0, CURRENT_TIMESTAMP)"
        ),
        {"id": uuid.uuid4().hex, "owner": owner, "status": status},
    )


def test_0020_creates_the_model_s_table_and_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0019")
    assert _columns(engine) is None
    command.upgrade(cfg, "0020")
    assert _columns(engine) == {c.name for c in RecommendationJob.__table__.columns}
    indexes = {i["name"]: i for i in sa.inspect(engine).get_indexes("recommendation_jobs")}
    model = {i.name: i for i in RecommendationJob.__table__.indexes}
    assert set(indexes) == set(model)
    assert indexes["uq_recommendation_jobs_one_active"]["unique"]
    command.downgrade(cfg, "0019")
    assert _columns(engine) is None
    command.upgrade(cfg, "0020")  # re-applies cleanly
    assert _columns(engine) is not None


def test_0020_one_queued_or_running_job_per_owner(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0020")
    with engine.begin() as c:
        _insert(c, "alice", "queued")
        _insert(c, "alice", "done")  # finished jobs never conflict
        _insert(c, "alice", "failed")
        _insert(c, "bob", "running")
        _insert(c, None, "queued")  # system jobs (no owner) never conflict
        _insert(c, None, "queued")
    for status in ("queued", "running"):
        with pytest.raises(sa.exc.IntegrityError), engine.begin() as c:
            _insert(c, "alice", status)
    with engine.begin() as c:
        done = "UPDATE recommendation_jobs SET status = 'done' WHERE owner_id = 'alice'"
        c.execute(sa.text(done))
        _insert(c, "alice", "running")  # free again once the active one finished
