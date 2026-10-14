"""Migration 0023 (calibration_reports) on a throwaway SQLite file. Reuses 0009's fixture."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401
from test_migration_0019 import _culture_and_batch
from test_migration_0021 import _columns, _link
from test_migration_0022 import _count, _tasting

from alembic import command
from fermenttrack.models import CalibrationReport


def _report(c: sa.Connection, passed: bool = False) -> None:
    c.execute(
        sa.text(
            "INSERT INTO calibration_reports (id, computed_at, passed, n_batches, report)"
            " VALUES (:id, CURRENT_TIMESTAMP, :passed, 0, '{\"n_batches\": 0}')"
        ),
        {"id": uuid.uuid4().hex, "passed": passed},
    )


def test_0023_creates_calibration_reports_and_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0022")
    culture, batch = uuid.uuid4().hex, uuid.uuid4().hex
    with engine.begin() as c:  # what the gate reads stays as it is
        _culture_and_batch(c, culture, batch)
        _link(c, batch, "library", "milk_kefir_grains_5pct_24h")
        _tasting(c, batch)
    assert _columns(engine, "calibration_reports") is None

    command.upgrade(cfg, "0023")
    assert _columns(engine, "calibration_reports") == {
        c.name for c in CalibrationReport.__table__.columns
    }
    indexes = {i["name"] for i in sa.inspect(engine).get_indexes("calibration_reports")}
    assert indexes == {i.name for i in CalibrationReport.__table__.indexes} == {
        "ix_calibration_reports_computed_at"
    }
    assert sa.inspect(engine).get_foreign_keys("calibration_reports") == []  # no user, no batch
    with engine.begin() as c:
        _report(c)
        _report(c, passed=True)
    assert _count(engine, "calibration_reports") == 2

    command.downgrade(cfg, "0022")
    assert _columns(engine, "calibration_reports") is None
    assert _count(engine, "tastings") == 1 and _count(engine, "recommendation_links") == 1
    command.upgrade(cfg, "0023")  # re-applies cleanly
    assert _count(engine, "calibration_reports") == 0
