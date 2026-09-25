"""Migration 0012 (batches.expected_temperature_c) on a throwaway SQLite file, FKs enforced.

Reuses 0009's fixture: same SQLite harness.
"""

from __future__ import annotations

import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command


def _columns(engine: sa.Engine) -> set[str]:
    return {c["name"] for c in sa.inspect(engine).get_columns("batches")}


def test_0012_expected_temperature_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0011")
    assert "expected_temperature_c" not in _columns(engine)

    command.upgrade(cfg, "0012")
    assert "expected_temperature_c" in _columns(engine)

    command.downgrade(cfg, "0011")
    assert "expected_temperature_c" not in _columns(engine)

    command.upgrade(cfg, "0012")  # re-applies cleanly
    assert "expected_temperature_c" in _columns(engine)
