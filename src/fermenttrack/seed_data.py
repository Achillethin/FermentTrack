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

# Added 2026-09-23 (migration 0005): generic rows were too vague to attach
# reference nutrients to (docs/superpowers/specs/2026-09-23-ingredient-
# nutrients-design.md § 2). The generic rows are retired (is_active=False),
# never deleted — historical batch_ingredients keep pointing at them.
FLOURS = frozenset({"White wheat flour", "Whole wheat flour", "Rye flour"})

INGREDIENT_SEED_DATA_V3: list[tuple[str, str, list[str]]] = [
    ("White rice", "base", ["koji", "miso"]),
    ("Pearl barley", "base", ["koji", "miso"]),
    ("Soybeans", "base", ["koji", "miso"]),
    ("White wheat flour", "base", ["sourdough"]),
    ("Whole wheat flour", "base", ["sourdough"]),
    ("Rye flour", "base", ["sourdough"]),
    ("Lemon", "flavoring", ["kombucha", "kefir"]),
    ("Strawberries", "flavoring", ["kombucha", "kefir"]),
    ("Raspberries", "flavoring", ["kombucha", "kefir"]),
    ("Apple", "flavoring", ["kombucha", "kefir"]),
    ("Mint", "flavoring", ["kombucha", "kefir"]),
    ("Basil", "flavoring", ["kombucha", "kefir"]),
    ("Cinnamon", "flavoring", ["kombucha", "kefir"]),
    ("Turmeric", "flavoring", ["kombucha", "kefir"]),
    ("Cardamom", "flavoring", ["kombucha", "kefir"]),
    ("Red wine", "base", ["vinegar"]),
    ("White wine", "base", ["vinegar"]),
    ("Hard cider", "base", ["vinegar"]),
    ("Black tea leaves", "base", ["kombucha"]),
    ("Green tea leaves", "base", ["kombucha"]),
    ("Anchovies", "base", ["garum"]),
    ("Mackerel", "base", ["garum"]),
]

RETIRED_V3: list[str] = [
    "Rice/grain/soybean",
    "Flour",
    "Fruit",
    "Herbs",
    "Spices",
    "Wine/cider/base alcohol",
    "Black/green tea",
    "Fish",
]

# Added 2026-10-06 (migration 0017): ingredients whose aroma precursors are curated (aroma
# increment B6), groundwork for building recipes from aromas. Their nutrients come from the
# bundled USDA catalogue (fdc_catalog_v1, loaded by 0007) via migration 0018: see
# INGREDIENT_FDC_IDS_V4.
INGREDIENT_SEED_DATA_V4: list[tuple[str, str, list[str]]] = [
    ("Napa cabbage", "base", ["lacto_ferment"]),
    ("Cucumber", "base", ["lacto_ferment"]),
    ("Radish", "base", ["lacto_ferment"]),
    ("Carrot", "base", ["lacto_ferment"]),
    ("Garlic", "flavoring", ["lacto_ferment"]),
    ("Onion", "flavoring", ["lacto_ferment"]),
    ("Caraway seeds", "flavoring", ["lacto_ferment"]),
    ("Dill", "flavoring", ["lacto_ferment"]),
    ("Lemongrass", "flavoring", ["kombucha", "kefir", "lacto_ferment"]),
]

# The USDA catalogue food behind each V4 ingredient (SR Legacy, fdc_catalog_v1): migration
# 0018 copies its nutrients to ingredient_nutrients exactly as a USDA-search pick would.
INGREDIENT_FDC_IDS_V4: dict[str, int] = {
    "Napa cabbage": 169979,  # Cabbage, chinese (pe-tsai), raw
    "Cucumber": 168409,  # Cucumber, with peel, raw
    "Radish": 169276,  # Radishes, raw
    "Carrot": 170393,  # Carrots, raw
    "Garlic": 169230,  # Garlic, raw
    "Onion": 170000,  # Onions, raw
    "Caraway seeds": 170918,  # Spices, caraway seed
    "Dill": 172233,  # Dill weed, fresh
    "Lemongrass": 168573,  # Lemon grass (citronella), raw
}

# Brine ferments (e.g. chilies in brine) log water as a base ingredient.
WATER_SYSTEMS_V3: list[str] = ["kombucha", "sourdough", "lacto_ferment"]

# Ingredient name -> exact USDA FDC SR Legacy description (docs/superpowers/
# specs/2026-09-23-ingredient-nutrients-design.md § 2). Resolved to an fdcId
# by scripts/fetch_fdc_snapshot.py, which fails loudly unless exactly one
# search hit matches. Deliberately absent: retired generic rows (RETIRED_V3),
# starters/cultures (no FDC entry; levain etc. can be real mass, lowering
# coverage), tea leaves (FDC has brewed tea, not dry leaves), calcium
# chloride, and hard cider unless FDC SR Legacy has an exact entry. They show
# up as "unmapped" in composition.
INGREDIENT_FDC_MAP: dict[str, str] = {
    "Water": "Beverages, water, tap, drinking",
    "Cane sugar": "Sugars, granulated",
    "Fresh ginger": "Ginger root, raw",
    "Milk": "Milk, whole, 3.25% milkfat, with added vitamin D",
    "Salt": "Salt, table",
    "Cabbage": "Cabbage, raw",
    "Chilies": "Peppers, hot chili, red, raw",
    "White rice": "Rice, white, short-grain, raw, unenriched",
    "Pearl barley": "Barley, pearled, raw",
    "Soybeans": "Soybeans, mature seeds, raw",
    "White wheat flour": "Wheat flour, white, bread, enriched",
    "Whole wheat flour": (
        "Wheat flour, whole-grain (Includes foods for USDA's Food Distribution Program)"
    ),
    "Rye flour": "Rye flour, dark",
    "Lemon": "Lemons, raw, without peel",
    "Strawberries": "Strawberries, raw",
    "Raspberries": "Raspberries, raw",
    "Apple": "Apples, raw, with skin (Includes foods for USDA's Food Distribution Program)",
    "Mint": "Spearmint, fresh",
    "Basil": "Basil, fresh",
    "Cinnamon": "Spices, cinnamon, ground",
    "Turmeric": "Spices, turmeric, ground",
    "Cardamom": "Spices, cardamom",
    "Red wine": "Alcoholic beverage, wine, table, red",
    "White wine": "Alcoholic beverage, wine, table, white",
    "Anchovies": "Fish, anchovy, european, raw",
    "Mackerel": "Fish, mackerel, Atlantic, raw",
}

# Recipe round 2, Noma and Katz (curation spec § 9, 2026-10-26): the ingredients of the recipes
# it activates. FDC matches from docs/superpowers/research/recipes/02-noma-katz.md § D, checked
# offline in fdc_catalog_v1; no aroma data yet (tier T1, or T0 where FDC has no row).
INGREDIENT_SEED_DATA_V5: list[tuple[str, str, list[str]]] = [
    ("Blueberries", "base", ["lacto_ferment"]),
    ("Plums", "base", ["lacto_ferment"]),
    ("Blackberries", "base", ["lacto_ferment"]),
    ("Mulberries", "base", ["lacto_ferment"]),
    ("White currants", "base", ["lacto_ferment"]),
    ("Mushrooms", "base", ["lacto_ferment", "garum"]),
    ("Apple juice (unfiltered)", "base", ["kombucha"]),
    ("Lemon verbena (dried)", "flavoring", ["kombucha"]),
    ("Coffee (ground)", "flavoring", ["kombucha"]),
    ("Yellow split peas (cooked)", "base", ["miso"]),
    ("Elderflower", "flavoring", ["miso"]),
    ("Chicken wings (roasted)", "base", ["garum"]),
    ("Chicken stock", "base", ["garum"]),
    ("Lamb tongue", "base", ["garum"]),
]
# Migration 0025 copies their nutrients as 0018 did for V4. No FDC row: lemon verbena, ground
# coffee, elderflower (T0, like tea leaves).
INGREDIENT_FDC_IDS_V5: dict[str, int] = {
    "Blueberries": 171711,  # Blueberries, raw
    "Plums": 169949,  # Plums, raw
    "Blackberries": 173946,  # Blackberries, raw
    "Mulberries": 169913,  # Mulberries, raw
    "White currants": 173964,  # Currants, red and white, raw
    "Mushrooms": 169251,  # Mushrooms, white, raw (also the ceps stand-in)
    "Apple juice (unfiltered)": 173933,  # Apple juice, canned or bottled, unsweetened, ... (proxy)
    "Yellow split peas (cooked)": 172429,  # Peas, split, mature seeds, cooked, boiled, without salt
    "Chicken wings (roasted)": 173630,  # Chicken, broilers or fryers, wing, meat and skin, ...
    "Chicken stock": 172884,  # Soup, stock, chicken, home-prepared
    "Lamb tongue": 174366,  # Lamb, variety meats and by-products, tongue, raw
}
