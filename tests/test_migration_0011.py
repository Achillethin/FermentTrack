"""Migration 0011 (unique organisms.name) on a throwaway SQLite file, FKs enforced.

Reuses 0009's fixture: same SQLite harness.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command
from fermenttrack.models import Organism


def _has_unique_name_index(engine: sa.Engine) -> bool:
    return any(
        ix["name"] == "ix_organisms_name" and ix["unique"] and ix["column_names"] == ["name"]
        for ix in sa.inspect(engine).get_indexes("organisms")
    )


def _add_dup(engine: sa.Engine) -> None:
    with engine.begin() as c:
        c.execute(sa.insert(Organism).values(
            id=uuid.uuid4(), name="Aspergillus oryzae", kingdom="mold",
            source_version="dup",
        ))  # fmt: skip


def _remove_dups(engine: sa.Engine) -> None:
    with engine.begin() as c:
        c.execute(sa.delete(Organism).where(Organism.source_version == "dup"))


def test_0011_unique_organism_name_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0010")
    assert not _has_unique_name_index(engine)

    command.upgrade(cfg, "0011")
    assert _has_unique_name_index(engine)
    try:
        _add_dup(engine)
    except sa.exc.IntegrityError:
        pass
    else:
        raise AssertionError("duplicate organism name was accepted")

    command.downgrade(cfg, "0010")
    assert not _has_unique_name_index(engine)
    _add_dup(engine)  # allowed again
    _remove_dups(engine)

    command.upgrade(cfg, "0011")  # re-applies cleanly
    assert _has_unique_name_index(engine)
