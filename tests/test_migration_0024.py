"""Migration 0024 (Lactobacillus sakei, a default lacto_ferment organism) on a throwaway
SQLite file. Reuses 0009's fixture."""

from __future__ import annotations

import sqlalchemy as sa
from test_migration_0009 import db  # noqa: F401

from alembic import command


def _lacto_defaults(engine: sa.Engine) -> set[str]:
    with engine.connect() as c:
        return {
            r[0]
            for r in c.execute(
                sa.text(
                    "SELECT o.name FROM fermentation_type_organisms l"
                    " JOIN organisms o ON o.id = l.organism_id"
                    " WHERE l.fermentation_type = 'lacto_ferment' AND l.is_default"
                )
            )
        }


def _has_sakei(engine: sa.Engine) -> bool:
    with engine.connect() as c:
        n = c.execute(sa.text("SELECT COUNT(*) FROM organisms WHERE name = 'Lactobacillus sakei'"))
        return n.scalar_one() == 1


def test_0024_adds_sakei_as_lacto_default_and_is_reversible(db) -> None:  # noqa: F811
    cfg, engine = db
    command.upgrade(cfg, "0023")
    before = _lacto_defaults(engine)
    assert "Lactobacillus sakei" not in before and not _has_sakei(engine)

    command.upgrade(cfg, "0024")
    assert _lacto_defaults(engine) == before | {"Lactobacillus sakei"}

    command.downgrade(cfg, "0023")
    assert _lacto_defaults(engine) == before and not _has_sakei(engine)

    command.upgrade(cfg, "0024")  # re-applies cleanly
    assert _has_sakei(engine) and "Lactobacillus sakei" in _lacto_defaults(engine)
