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
