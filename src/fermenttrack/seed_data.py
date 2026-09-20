"""Reference ingredient seed data (docs/superpowers/specs/2026-09-18-experiment-logging-design.md
§ 1, "Seed data — all documented substrates"). Single-sourced here so both the
Alembic migration (alembic/versions/0002_ingredients.py) and any future
re-seed tooling use the same list.
"""

from __future__ import annotations

# (name, default_role, fermentation_systems)
INGREDIENT_SEED_DATA: list[tuple[str, str, list[str]]] = [
    ("Black/green tea", "base", ["kombucha"]),
    ("Water", "base", ["kombucha", "sourdough"]),
    ("Cane sugar", "base", ["kombucha", "kefir"]),
    ("SCOBY / starter liquid", "starter", ["kombucha"]),
    ("Fresh ginger", "flavoring", ["kombucha", "kefir"]),
    ("Fruit", "flavoring", ["kombucha", "kefir"]),
    ("Herbs", "flavoring", ["kombucha", "kefir"]),
    ("Spices", "flavoring", ["kombucha", "kefir"]),
    ("Flour", "base", ["sourdough"]),
    ("Starter/levain", "starter", ["sourdough"]),
    ("Rice/grain/soybean", "base", ["koji", "miso"]),
    ("Koji spores (A. oryzae)", "starter", ["koji", "miso"]),
    ("Milk", "base", ["cheese", "kefir"]),
    ("Rennet", "starter", ["cheese"]),
    ("Starter/cheese culture", "starter", ["cheese"]),
    ("Kefir grains", "starter", ["kefir"]),
    ("Wine/cider/base alcohol", "base", ["vinegar"]),
    ("Mother of vinegar (Acetobacter)", "starter", ["vinegar"]),
    ("Salt", "additive", ["cheese", "koji", "miso", "sourdough"]),
    ("Calcium chloride", "additive", ["cheese"]),
]

# Added 2026-09-20 for lacto_ferment/garum substrate support (migration
# 0003). Kept as a separate list rather than appended to INGREDIENT_SEED_DATA
# above: migration 0002 already applied that list's exact rows to any
# database that ran it, so mutating it now wouldn't retroactively reach an
# already-migrated database, and 0002 should stay a historically accurate
# record of what it actually inserted. New substrates get new rows via a new
# migration instead.
INGREDIENT_SEED_DATA_V2: list[tuple[str, str, list[str]]] = [
    ("Cabbage", "base", ["lacto_ferment"]),
    ("Chilies", "base", ["lacto_ferment"]),
    ("Fish", "base", ["garum"]),
]
