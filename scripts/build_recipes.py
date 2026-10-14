"""Freeze the recipe library (design § 4): the research drafts plus every decision of the curation
spec (docs/superpowers/specs/2026-10-07-recipe-curation.md, "curation" below) ->
src/fermenttrack/recommender/recipes_v1.csv and recipe_ingredients_v1.csv.

The decisions are data in this file, each citing its curation section. Q25 widening,
`envelope_basis` and `model_scope` are derived from prediction/profiles.py.

Run: python scripts/build_recipes.py           (writes both files)
     python scripts/build_recipes.py --check   (exit 1 if the committed files differ from a build)
tests/test_recommender_library.py cross-checks the result against the curation tables.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.sourdough import STYLES

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "docs/superpowers/research/recipes"
OUT = ROOT / "src/fermenttrack/recommender"
RECIPES_V1 = OUT / "recipes_v1.csv"
INGREDIENTS_V1 = OUT / "recipe_ingredients_v1.csv"

RECIPE_FIELDS = (
    "key", "name", "fermentation_type", "style_region", "provenance",
    "temp_c_median", "temp_c_lo", "temp_c_hi", "duration_h_median", "duration_h_lo",
    "duration_h_hi", "salt_pct_median", "salt_pct_lo", "salt_pct_hi", "sugar_g_per_kg_median",
    "sugar_g_per_kg_lo", "sugar_g_per_kg_hi", "aerobic", "method", "stages", "safety_targets",
    "reported_aromas", "sources", "status", "notes",
    "temp_schedule", "envelope_basis", "model_scope", "handoff", "planner_style",
)  # fmt: skip
INGREDIENT_FIELDS = (
    "recipe_key", "ingredient", "catalogue_status", "role", "g_per_kg_median", "g_per_kg_lo",
    "g_per_kg_hi", "required", "source", "notes", "label",
)  # fmt: skip
TRIPLES = ("temp_c", "duration_h", "salt_pct", "sugar_g_per_kg", "g_per_kg")
Row = dict[str, str]

# Final status of every draft key (curation § 3, § 3a, § 4). A draft key missing here fails the
# build, so a new research row cannot reach v1 uncurated.
STATUS: dict[str, str] = {
    # § 2, § 3: the 13 curated recipes
    "sauerkraut_dry_salted": "active",
    "napa_kimchi_room_temp": "active",
    "black_tea_kombucha_1f": "active",
    "green_tea_kombucha_variant": "active",
    "rice_koji_steamed_rice": "active",
    "shiro_miso_kagawa_sweet": "active",
    "red_rice_miso_kagawa_long": "active",
    "pacific_sand_lance_rice_koji_fish_sauce": "active",  # § 4: kept active by the Q32 stand-in
    "milk_kefir_grains_5pct_24h": "active",
    "milk_kefir_grains_10pct_extended": "active",
    "lactic_fresh_cheese_curd": "active",
    "wine_orleans_surface": "active",
    "cider_vinegar_surface": "active",
    "dill_cucumber_pickles_brined": "draft",  # § 3: no dill mass; `Vinegar (5 %)` is new
    "carrot_sticks_wet_brined": "draft",  # § 3: no carrot-to-brine mass
    "barley_koji_single_grain": "draft",  # § 4: curators said active; spore dose missing
    "budu_traditional_anchovy_fish_sauce": "draft",  # § 4 (Q26): temperature not stated
    # § 3a (Q31): the 7 sourced catalogue styles, handed off to the sourdough planner; § 4 makes
    # the four without a fixed build time active (the planner sets the timing)
    "san_francisco": "active",
    "rye_sour": "active",
    "type_ii": "active",
    "home_starter": "active",
    "levain_liquide": "active",
    "levain_dur": "active",
    "lievito_madre": "active",
    # § 3a, § 4: not in v1 (commercial-yeast preferments; Type III has no dough formula)
    "poolish": "excluded",
    "biga": "excluded",
    "type_iii": "excluded",
}

RENAMES = {"green_tea_kombucha_variant": "green_dominant_kombucha"}  # § 3

RECIPE_EDITS: dict[str, Row] = {
    # § 3, § 4: the cider-specific Penn State leaflet (60-80 °F) takes precedence over NC State's
    # general 68-96 °F: (60-32)/1.8 = 15.6, (80-32)/1.8 = 26.7, median (70-32)/1.8 = 21.1 °C.
    "cider_vinegar_surface": {"temp_c_median": "21.1", "temp_c_lo": "15.6", "temp_c_hi": "26.7"},
    # § 3 (Q27): the 20 °C koji pretreatment (24-72 h, midpoint 48 h), then the 18 °C main stage
    "pacific_sand_lance_rice_koji_fish_sauce": {"temp_schedule": "0:20;48:18"},
}

CURATION_NOTES: dict[str, str] = {
    "napa_kimchi_room_temp": (
        "curation § 3: red pepper powder booked as Chilies until Gochugaru exists; Salted shrimp "
        "and Glutinous rice paste optional until catalogued; fridge stage unsourced, so no "
        "temp_schedule"
    ),
    "green_tea_kombucha_variant": "curation § 3: renamed from green_tea_kombucha_variant",
    "shiro_miso_kagawa_sweet": "curation § 3: rice koji split 15:17 into White rice and Water",
    "red_rice_miso_kagawa_long": "curation § 3: rice koji split 15:17 into White rice and Water",
    "pacific_sand_lance_rice_koji_fish_sauce": (
        "curation § 3 (Q32): fish booked as Anchovies stand-in; rice koji split 15:17 into White "
        "rice and Water; koji pretreatment as temp_schedule"
    ),
    "barley_koji_single_grain": (
        "curation § 4: draft until a barley-specific source gives the spore dose"
    ),
    "budu_traditional_anchovy_fish_sauce": (
        "curation § 4 (Q26): draft until a source states the fermentation temperature"
    ),
    "cider_vinegar_surface": (
        "curation § 4: the cider-specific 60-80 F takes precedence over the general 68-96 F"
    ),
    **{
        k: "curation § 3a (Q31): active; timing from the sourdough planner"
        for k in ("home_starter", "levain_liquide", "levain_dur", "lievito_madre")
    },
}

# § 3 (miso; sand lance "the same split"): finished rice koji booked as `White rice` becomes raw
# rice plus the water it absorbed, at Kagawa's 15 kg rice -> 17 kg koji, matching the engine's
# koji-ratio reference (DEFAULT_INGREDIENTS["miso"]). The role becomes `base`.
KOJI_SPLIT = (
    "shiro_miso_kagawa_sweet",
    "red_rice_miso_kagawa_long",
    "pacific_sand_lance_rice_koji_fish_sauce",
)
RICE_KG, KOJI_KG = 15, 17
KOJI_LABEL = "made into rice koji first: 15 g rice absorbs 2 g of the Water row -> 17 g koji"

# § 3, § 4 (Q32): a fish missing from the catalogue is booked as Anchovies (the garum route treats
# small whole fish alike), with a card label.
STAND_INS: dict[tuple[str, str], tuple[str, str]] = {
    ("pacific_sand_lance_rice_koji_fish_sauce", "Pacific sand lance"): (
        "Anchovies",
        "stand-in species: recipe uses Pacific sand lance",
    ),
}

# § 3 kimchi: the two `new` seasonings (1.5 % and 0.8 % of Jang 2024's formula, i.e. 14.7 and
# 7.8 g/kg) become optional, so the recipe stays active.
OPTIONAL = {
    ("napa_kimchi_room_temp", "Salted shrimp"),
    ("napa_kimchi_room_temp", "Glutinous rice paste"),
}

LABELS: dict[tuple[str, str], str] = {
    # § 3 kimchi: mass unchanged until `Gochugaru` (dried) exists (§ 6)
    ("napa_kimchi_room_temp", "Chilies"): (
        "dried powder booked as fresh chili: dry matter understated several-fold"
    ),
    ("napa_kimchi_room_temp", "Salted shrimp"): "not in the catalogue yet: optional",
    ("napa_kimchi_room_temp", "Glutinous rice paste"): "not in the catalogue yet: optional",
    # § 3 wine vinegar
    ("wine_orleans_surface", "Red wine"): (
        "stands for any base wine (White wine is the other modelled base)"
    ),
}


def _fmt(x: Decimal) -> str:
    s = format(x, "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _point(row: Row, name: str) -> Decimal | None:
    """The value of a single-value triple (lo = median = hi), else None."""
    vals = {row[f"{name}_{s}"] for s in ("median", "lo", "hi")}
    if len(vals) != 1 or "" in vals:
        return None
    return Decimal(vals.pop())


def _widen(row: Row) -> list[str]:
    """Curation § 1 rule 4 (Q25): a single duration d becomes [0.7 d, 1.3 d] and a single
    temperature T becomes [T - 3, T + 3], clipped to the profile's temp_range unless T itself lies
    outside it (then Q26 applies and the source's widened range stays)."""
    widened = []
    t = _point(row, "temp_c")
    if t is not None:
        r_lo, r_hi = (Decimal(str(v)) for v in PROFILES[row["fermentation_type"]].temp_range)
        lo, hi = t - 3, t + 3
        if r_lo <= t <= r_hi:
            lo, hi = max(lo, r_lo), min(hi, r_hi)
        row["temp_c_lo"], row["temp_c_hi"] = _fmt(lo), _fmt(hi)
        widened.append("temperature")
    d = _point(row, "duration_h")
    if d is not None:
        row["duration_h_lo"] = _fmt(Decimal("0.7") * d)
        row["duration_h_hi"] = _fmt(Decimal("1.3") * d)
        widened.append("duration")
    return widened


def _model_scope(row: Row) -> str:
    """Q26 (curation § 1 rule 5): where the source leaves the profile's range or horizon."""
    profile = PROFILES[row["fermentation_type"]]
    temps = [Decimal(row[f"temp_c_{s}"]) for s in ("lo", "median", "hi") if row[f"temp_c_{s}"]]
    temps += [Decimal(step.split(":")[1]) for step in row["temp_schedule"].split(";") if step]
    lo, hi = (Decimal(str(v)) for v in profile.temp_range)
    scope = []
    if temps and (min(temps) < lo or max(temps) > hi):
        scope.append("temp_outside_profile")
    if row["duration_h_hi"] and Decimal(row["duration_h_hi"]) > Decimal(str(profile.horizon_h)):
        scope.append("beyond_horizon")
    return ";".join(scope) or "in_range"


def _add_note(row: Row, note: str) -> None:
    row["notes"] = f"{row['notes']}; {note}" if row["notes"] else note


def _split_koji(rows: list[Row], key: str) -> None:
    """Curation § 3: rice koji -> White rice (15/17 of it) + Water (the rest), column by column."""
    rice = next(r for r in rows if r["recipe_key"] == key and r["ingredient"] == "White rice")
    water = next((r for r in rows if r["recipe_key"] == key and r["ingredient"] == "Water"), None)
    if water is None:
        water = {
            "recipe_key": key, "ingredient": "Water", "catalogue_status": "existing_no_aroma",
            "role": "liquid", "g_per_kg_median": "0", "g_per_kg_lo": "0", "g_per_kg_hi": "0",
            "required": "core", "source": rice["source"], "notes": "", "label": "",
        }  # fmt: skip
        rows.insert(rows.index(rice) + 1, water)
    for col in ("g_per_kg_median", "g_per_kg_lo", "g_per_kg_hi"):
        koji = Decimal(rice[col])
        raw = (koji * RICE_KG / KOJI_KG).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        rice[col] = _fmt(raw)
        water[col] = _fmt(Decimal(water[col]) + koji - raw)
    rice["role"], rice["label"] = "base", KOJI_LABEL
    _add_note(rice, "raw rice share of the rice koji (15:17 split, curation § 3)")
    _add_note(water, "includes the water the rice koji absorbed (15:17 split, curation § 3)")


def _read(pattern: str) -> list[Row]:
    rows: list[Row] = []
    for path in sorted(DRAFTS.glob(pattern)):
        with path.open(encoding="utf-8", newline="") as f:
            rows += [dict(r) for r in csv.DictReader(f)]
    return rows


def build() -> tuple[list[Row], list[Row]]:
    recipes = _read("recipes_draft_v0.*.csv")
    ingredients = _read("recipe_ingredients_draft_v0.*.csv")
    keys = [r["key"] for r in recipes]
    if len(keys) != len(set(keys)) or set(keys) != set(STATUS):
        raise ValueError(f"uncurated or duplicate draft keys: {sorted(set(keys) ^ set(STATUS))}")

    for r in ingredients:
        r.setdefault("label", "")
        swap = STAND_INS.get((r["recipe_key"], r["ingredient"]))
        if swap:
            _add_note(r, f"booked as {swap[0]} (Q32 stand-in, curation § 3)")
            r["ingredient"], r["catalogue_status"], r["label"] = swap[0], "existing", swap[1]
        if (r["recipe_key"], r["ingredient"]) in OPTIONAL:
            r["required"] = "optional"
        r["label"] = LABELS.get((r["recipe_key"], r["ingredient"]), r["label"])
    for key in KOJI_SPLIT:
        _split_koji(ingredients, key)

    out = []
    for r in recipes:
        key = r["key"]
        r["status"] = STATUS[key]
        if r["status"] == "excluded":
            continue
        r.update({"temp_schedule": "", "handoff": "", "planner_style": ""})
        r.update(RECIPE_EDITS.get(key, {}))
        if key in CURATION_NOTES:
            _add_note(r, CURATION_NOTES[key])
        if r["fermentation_type"] == "sourdough":
            if key not in STYLES:
                raise ValueError(f"{key}: not a sourdough catalogue style")
            r["handoff"], r["planner_style"] = "planner", key  # § 3a (Q31)
        widened = _widen(r)
        if widened:
            _add_note(r, f"curation § 1 rule 4 (Q25): widened single-value {' and '.join(widened)}")
        r["envelope_basis"] = "widened_single_value" if widened else "sourced"
        r["model_scope"] = _model_scope(r)
        r["key"] = RENAMES.get(key, key)
        out.append(r)

    kept = {k: STATUS[k] for k in keys if STATUS[k] != "excluded"}
    rows = [r for r in ingredients if r["recipe_key"] in kept]
    for r in rows:
        if kept[r["recipe_key"]] == "active" and r["required"] == "core":
            if r["catalogue_status"] == "new":  # curation § 1 rule 2
                raise ValueError(f"{r['recipe_key']}: core ingredient {r['ingredient']} is new")
        r["recipe_key"] = RENAMES.get(r["recipe_key"], r["recipe_key"])
    for key in {r["key"] for r in out}:
        total = sum(Decimal(r["g_per_kg_median"]) for r in rows
                    if r["recipe_key"] == key and r["g_per_kg_median"])  # fmt: skip
        if not 950 <= total <= 1050:  # curation § 3: medians sum to 1000 g/kg ± 5 %
            raise ValueError(f"{key}: ingredient medians sum to {total} g/kg")

    for r in out + rows:
        for name in TRIPLES:
            for s in ("median", "lo", "hi"):
                col = f"{name}_{s}"
                if r.get(col):
                    r[col] = _fmt(Decimal(r[col]))
    return out, rows


def render(rows: list[Row], fields: tuple[str, ...]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the frozen recipe library v1 files.")
    ap.add_argument("--check", action="store_true", help="fail if the committed files differ")
    args = ap.parse_args(argv)
    recipes, ingredients = build()
    files = {
        RECIPES_V1: render(recipes, RECIPE_FIELDS),
        INGREDIENTS_V1: render(ingredients, INGREDIENT_FIELDS),
    }
    if args.check:
        stale = [p for p, text in files.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != text]  # fmt: skip
        for p in stale:
            print(f"{p.name} is stale: run python scripts/build_recipes.py", file=sys.stderr)
        return 1 if stale else 0
    for p, text in files.items():
        p.write_text(text, encoding="utf-8", newline="")
    active = sum(r["status"] == "active" for r in recipes)
    print(f"{len(recipes)} recipes ({active} active), {len(ingredients)} ingredient rows -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
