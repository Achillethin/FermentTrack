"""Recipe library R0 (design § 4, docs/superpowers/specs/2026-10-07-recipe-curation.md): the frozen
v1 files match the curation, pass the library rules, and ingredient tiers derive (design § 12)."""

from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path
from types import ModuleType

import pytest

from fermenttrack.prediction.aroma_data import AROMA_INGREDIENTS
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.sourdough import STYLES
from fermenttrack.recommender import library as L
from fermenttrack.recommender.library import Recipe, Span
from fermenttrack.seed_data import (
    INGREDIENT_SEED_DATA,
    INGREDIENT_SEED_DATA_V2,
    INGREDIENT_SEED_DATA_V3,
    INGREDIENT_SEED_DATA_V4,
    RETIRED_V3,
)

ROOT = Path(__file__).resolve().parents[1]
CURATION = ROOT / "docs/superpowers/specs/2026-10-07-recipe-curation.md"
RESEARCH = ROOT / "docs/superpowers/research/recipes"

SOURDOUGH = {
    "san_francisco", "rye_sour", "type_ii", "home_starter", "levain_liquide", "levain_dur",
    "lievito_madre",
}  # fmt: skip
ACTIVE = SOURDOUGH | {
    "sauerkraut_dry_salted", "napa_kimchi_room_temp", "black_tea_kombucha_1f",
    "green_dominant_kombucha", "rice_koji_steamed_rice", "shiro_miso_kagawa_sweet",
    "red_rice_miso_kagawa_long", "pacific_sand_lance_rice_koji_fish_sauce",
    "milk_kefir_grains_5pct_24h", "milk_kefir_grains_10pct_extended", "lactic_fresh_cheese_curd",
    "wine_orleans_surface", "cider_vinegar_surface",
}  # fmt: skip
DRAFT = {
    "dill_cucumber_pickles_brined", "carrot_sticks_wet_brined", "barley_koji_single_grain",
    "budu_traditional_anchovy_fish_sauce",
}  # fmt: skip
SALTED_TYPES = {"lacto_ferment", "miso", "garum"}
_NUM = r"\d+(?:\.\d+)?"
_SCOPE = r"in_range|temp_outside_profile|beyond_horizon"


def _builder() -> ModuleType:
    path = ROOT / "scripts/build_recipes.py"
    spec = importlib.util.spec_from_file_location("build_recipes", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _recipe(key: str) -> Recipe:
    recipe = L.get(key)
    assert recipe is not None, key
    return recipe


def _grams(recipe: Recipe, name: str) -> Span:
    span = next(i.g_per_kg for i in recipe.ingredients if i.name == name)
    assert span is not None
    return span


# ── the build ────────────────────────────────────────────────────────────────


def test_committed_files_match_a_fresh_build() -> None:
    assert _builder().main(["--check"]) == 0


def test_check_fails_on_a_stale_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    b = _builder()
    for attr in ("RECIPES_V1", "INGREDIENTS_V1"):
        copy = tmp_path / getattr(b, attr).name
        shutil.copy(getattr(b, attr), copy)
        monkeypatch.setattr(b, attr, copy)
    assert b.main(["--check"]) == 0
    text = b.INGREDIENTS_V1.read_text(encoding="utf-8")
    b.INGREDIENTS_V1.write_text(text.replace("414.4", "414.3", 1), encoding="utf-8", newline="")
    assert b.main(["--check"]) == 1
    assert "recipe_ingredients_v1.csv is stale" in capsys.readouterr().err


def test_build_rejects_an_uncurated_draft_key() -> None:
    b = _builder()
    del b.STATUS["budu_traditional_anchovy_fish_sauce"]
    with pytest.raises(ValueError, match="uncurated or duplicate draft keys"):
        b.build()


def test_build_rejects_a_new_core_ingredient_in_an_active_recipe() -> None:
    b = _builder()
    b.OPTIONAL.discard(("napa_kimchi_room_temp", "Salted shrimp"))
    with pytest.raises(ValueError, match="core ingredient Salted shrimp is new"):
        b.build()


def test_build_rejects_medians_outside_1000_g_per_kg(tmp_path: Path) -> None:
    b = _builder()
    for path in b.DRAFTS.glob("*_draft_v0.*.csv"):
        shutil.copy(path, tmp_path / path.name)
    lacto = tmp_path / "recipe_ingredients_draft_v0.lacto-kombucha.csv"
    text = lacto.read_text(encoding="utf-8")
    lacto.write_text(text.replace("Cabbage,existing,base,978.9", "Cabbage,existing,base,920"),
                     encoding="utf-8", newline="")  # fmt: skip
    b.DRAFTS = tmp_path
    with pytest.raises(ValueError, match=r"sauerkraut_dry_salted: .* sum to 941\.1 g/kg"):
        b.build()


# ── status sets (curation § 2, § 3a, § 4) ────────────────────────────────────


def test_twenty_active_four_draft_and_no_excluded_styles() -> None:
    lib = L.load_library()
    assert len(L.active()) == 20 and {r.key for r in L.active()} == ACTIVE
    assert {k for k, r in lib.items() if r.status == "draft"} == DRAFT
    assert set(lib) == ACTIVE | DRAFT  # poolish, biga, type_iii are not in v1


def _table(text: str, start: str, end: str) -> list[list[str]]:
    section = text.split(start, 1)[1].split(end, 1)[0]
    return [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in section.splitlines()
        if line.startswith("| ") and not line.startswith("| key")
    ]


def _cell(cell: str) -> tuple[float | None, tuple[float, float] | None]:
    """'22.5 (21.1–23.9)' -> (22.5, (21.1, 23.9)); '—' -> (None, None)."""
    cell = cell.replace("*", "")
    if cell.startswith("—"):
        return None, None
    m, r = re.match(_NUM, cell), re.search(rf"({_NUM})–({_NUM})", cell)
    assert m, cell
    return float(m.group()), (float(r[1]), float(r[2])) if r else None


def test_v1_matches_the_curated_recipe_table() -> None:
    """Curation § 3: status, model_scope, and the T, duration and salt envelopes per row."""
    renames: dict[str, str] = _builder().RENAMES
    rows = _table(CURATION.read_text(encoding="utf-8"), "## 3. Curated recipes", "## 3a.")
    assert len(rows) == 17
    for key, _type, _prov, t, d, salt, basis, scope, status, _note in rows:
        r = _recipe(renames.get(key.strip("`"), key.strip("`")))
        assert r.status == status.replace("*", "").split()[0], r.key
        assert set(r.model_scope) == set(re.findall(_SCOPE, scope)), r.key
        expected_basis = "widened_single_value" if "widened" in basis else "sourced"
        assert r.envelope_basis == expected_basis, r.key
        widened_t = re.search(rf"T widened → ({_NUM})–({_NUM})", basis)
        for name, cell, span, tol in (("T", t, r.temp_c, 0.05), ("d", d, r.duration_h, 0.5),
                                      ("salt", salt, r.salt_pct, 0.005)):  # fmt: skip
            median, rng = _cell(cell)
            if name == "T" and widened_t:
                rng = float(widened_t[1]), float(widened_t[2])
            if median is None:
                assert span is None, (r.key, name)
                continue
            assert span is not None and span.median == pytest.approx(median, abs=tol), r.key
            if rng:
                assert (span.lo, span.hi) == pytest.approx(rng, abs=tol), (r.key, name)


def test_v1_matches_the_sourdough_table() -> None:
    """Curation § 3a (Q31): seven styles active with the catalogue T and build time; three out."""
    rows = _table(CURATION.read_text(encoding="utf-8"), "## 3a.", "## 4.")
    seen = set()
    for keys, _sources, temps, hours, status, note in rows:
        for key, temp in zip(re.findall(r"`(\w+)`", keys), re.findall(_NUM, temps), strict=True):
            seen.add(key)
            if "excluded" in status:
                assert L.get(key) is None, key
                continue
            r = _recipe(key)
            assert r.status == "active" and r.temp_c and r.temp_c.median == float(temp), key
            assert (r.duration_h.median if r.duration_h else "planner") == (
                "planner" if hours == "planner" else float(hours)
            ), key
            assert set(r.model_scope) == (set(re.findall(_SCOPE, note)) or {"in_range"}), key
    assert seen == SOURDOUGH | {"poolish", "biga", "type_iii"}


# ── library rules (curation § 1, design § 4.2) ───────────────────────────────


def test_fermentation_type_is_a_profile_key() -> None:
    for r in L.load_library().values():
        assert r.fermentation_type in PROFILES, r.key


def test_ingredients_resolve_to_the_catalogue() -> None:
    for r in L.load_library().values():
        for i in r.ingredients:
            tier = L.ingredient_tier(i.name, r.fermentation_type)
            assert (tier >= 0) == (i.catalogue_status != "new"), (r.key, i.name)
            if r.status == "active" and i.required == "core":
                assert tier >= 0, (r.key, i.name)


def test_ingredient_medians_sum_to_1000_g_per_kg() -> None:
    for r in L.load_library().values():  # sourdough levain builds included
        total = sum(i.g_per_kg.median for i in r.ingredients if i.g_per_kg)
        assert 950 <= total <= 1050, (r.key, total)


def test_spans_are_ordered() -> None:
    for r in L.load_library().values():
        spans = [r.temp_c, r.duration_h, r.salt_pct, r.sugar_g_per_kg]
        for s in spans + [i.g_per_kg for i in r.ingredients]:
            assert s is None or s.lo <= s.median <= s.hi, r.key


def test_active_recipes_have_no_missing_values() -> None:
    for r in L.active():
        assert r.temp_c is not None, r.key
        # curation § 3a (Q31): the planner sets the timing of the four styles without build hours
        assert r.duration_h is not None or r.handoff == "planner", r.key
        assert all(i.g_per_kg for i in r.ingredients if i.required == "core"), r.key
        if r.fermentation_type in SALTED_TYPES:
            assert r.salt_pct is not None, r.key
            # the gate reads salt from the ingredient rows: they must agree with the envelope
            assert _grams(r, "Salt").median / 10 == pytest.approx(r.salt_pct.median, abs=0.05)


def test_every_source_key_is_defined_in_the_research_files() -> None:
    text = "".join(p.read_text(encoding="utf-8") for p in RESEARCH.glob("01-*.md"))
    for r in L.load_library().values():
        assert r.sources, r.key
        for key in r.sources:
            assert f"**{key}**" in text, (r.key, key)


# ── curation fixes (§ 3) ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "key,koji,rice,water",
    [  # draft rice koji -> White rice at 15/17, the rest joins Water (g/kg)
        ("shiro_miso_kagawa_sweet", 469.6, 414.4, 55.2 + 55.2),
        ("red_rice_miso_kagawa_long", 311.9, 275.2, 18.3 + 36.7),
        ("pacific_sand_lance_rice_koji_fish_sauce", 80.0, 70.6, 9.4),
    ],
)
def test_rice_koji_is_split_15_to_17(key: str, koji: float, rice: float, water: float) -> None:
    r = _recipe(key)
    assert rice == pytest.approx(koji * 15 / 17, abs=0.05)
    assert _grams(r, "White rice").median == rice
    assert _grams(r, "Water").median == pytest.approx(water)
    row = next(i for i in r.ingredients if i.name == "White rice")
    assert row.role == "base" and row.label and "rice koji" in row.label


def test_sand_lance_books_anchovies_as_a_labelled_stand_in() -> None:
    r = _recipe("pacific_sand_lance_rice_koji_fish_sauce")
    fish = next(i for i in r.ingredients if i.name == "Anchovies")
    assert fish.label == "stand-in species: recipe uses Pacific sand lance"
    assert fish.g_per_kg == Span(800.0, 769.2, 833.3)
    assert "Pacific sand lance" not in {i.name for i in r.ingredients}
    assert r.status == "active" and r.temp_schedule == ((0.0, 20.0), (48.0, 18.0))


def test_kimchi_keeps_chilies_labelled_and_new_seasonings_optional() -> None:
    r = _recipe("napa_kimchi_room_temp")
    optional = {i.name for i in r.ingredients if i.required == "optional"}
    assert optional == {"Salted shrimp", "Glutinous rice paste"}
    chilies = next(i for i in r.ingredients if i.name == "Chilies")
    assert chilies.label and chilies.label.startswith("dried powder booked as fresh chili")
    assert chilies.g_per_kg == Span(29.4, 29.4, 29.4)
    assert r.temp_schedule == ()  # the fridge stage is not sourced yet


def test_rename_and_cider_temperature() -> None:
    assert L.get("green_tea_kombucha_variant") is None
    assert _recipe("green_dominant_kombucha").fermentation_type == "kombucha"
    assert _recipe("cider_vinegar_surface").temp_c == Span(21.1, 15.6, 26.7)


@pytest.mark.parametrize(
    "key,temp,duration",
    [
        ("black_tea_kombucha_1f", Span(30, 27, 33), Span(336, 235.2, 436.8)),  # T outside 20-28
        ("green_dominant_kombucha", Span(25, 22, 28), Span(240, 168, 312)),
        ("milk_kefir_grains_5pct_24h", Span(25, 22, 25), Span(24, 16.8, 31.2)),  # clipped at 25
        ("milk_kefir_grains_10pct_extended", Span(25, 22, 25), Span(48, 24, 72)),
        ("napa_kimchi_room_temp", Span(20, 17, 23), Span(36, 24, 48)),
        ("pacific_sand_lance_rice_koji_fish_sauce", Span(18, 18, 20), Span(7200, 5040, 9360)),
        ("type_ii", Span(37, 34, 40), Span(18, 12.6, 23.4)),  # T outside 22-30
        ("rye_sour", Span(28, 25, 30), Span(16, 11.2, 20.8)),  # clipped at 30
    ],
)
def test_q25_widens_single_values_and_clips_in_range_temperatures(
    key: str, temp: Span, duration: Span
) -> None:
    r = _recipe(key)
    assert (r.temp_c, r.duration_h, r.envelope_basis) == (temp, duration, "widened_single_value")


def test_ranged_sources_stay_sourced() -> None:
    for key in ("sauerkraut_dry_salted", "rice_koji_steamed_rice", "lactic_fresh_cheese_curd"):
        assert _recipe(key).envelope_basis == "sourced", key


def test_sourdough_styles_hand_off_to_the_planner_with_catalogue_builds() -> None:
    for r in L.load_library().values():
        if r.fermentation_type != "sourdough":
            assert r.handoff is None and r.planner_style is None, r.key
            continue
        assert r.handoff == "planner" and r.planner_style == r.key
        style = STYLES[r.planner_style]
        assert style.seed == "starter" and style.sources and r.temp_c
        assert r.temp_c.median == style.temperature_c
        assert (r.duration_h.median if r.duration_h else None) == style.hours
        # seed 1 : flour seed_ratio : water seed_ratio x hydration, per kg of the build
        total = 1 + style.seed_ratio * (1 + style.hydration_pct / 100)
        grams = {i.role: i.g_per_kg.median for i in r.ingredients if i.g_per_kg}
        assert grams["starter"] == pytest.approx(1000 / total, abs=0.1), r.key
        assert grams["base"] == pytest.approx(1000 * style.seed_ratio / total, abs=0.1), r.key


def test_trust_labels() -> None:
    outside = "source temperature outside the model's range: forecasts use the nearest in-range "
    partly = "part of the documented temperature range is outside the model's range"
    assert L.trust_labels(_recipe("sauerkraut_dry_salted")) == ()
    labels = L.trust_labels(_recipe("pacific_sand_lance_rice_koji_fish_sauce"))  # 18 < 20 °C
    assert labels == (
        "single-value source, widened",
        outside + "temperature",
        "aroma estimate covers the first 180 days only",
    )
    assert L.trust_labels(_recipe("milk_kefir_grains_10pct_extended"))[-1].endswith("2 days only")
    for key in ("black_tea_kombucha_1f", "cider_vinegar_surface", "lactic_fresh_cheese_curd"):
        assert outside + "temperature" in L.trust_labels(_recipe(key)), key
    # the served median is in range; only part of the documented span leaves it
    for key in ("wine_orleans_surface", "rice_koji_steamed_rice"):
        assert L.trust_labels(_recipe(key)) == (partly,), key


# ── staples, aliases and tiers (design Q3, § 12) ─────────────────────────────


def test_staples_are_catalogue_names_and_cover_every_starter_culture() -> None:
    seeds = INGREDIENT_SEED_DATA + INGREDIENT_SEED_DATA_V2 + INGREDIENT_SEED_DATA_V3
    starters = {n for n, role, _s in seeds + INGREDIENT_SEED_DATA_V4 if role == "starter"}
    assert L.STAPLES <= L.CATALOGUE_NAMES
    assert starters - set(RETIRED_V3) - L.STAPLES == {"Rennet"}  # a coagulant, not a culture


def test_aroma_ingredient_keys_are_catalogue_names_or_aliases() -> None:
    for name in AROMA_INGREDIENTS:
        assert name in L.CATALOGUE_NAMES or name in L.ALIASES, name
    assert L.ALIASES <= set(AROMA_INGREDIENTS) and not L.ALIASES & L.CATALOGUE_NAMES


@pytest.mark.parametrize(
    "name,tier",
    [
        ("Salted shrimp", -1),  # `new`
        ("Fish", -1),  # retired
        ("Napa cabbage (salted)", -1),  # an aroma alias, not a catalogue row
        ("Kefir grains", 0),
        ("Rennet", 0),
        ("Salt", 1),  # INGREDIENT_FDC_MAP
        ("Garlic", 1),  # INGREDIENT_FDC_IDS_V4
        ("Black tea leaves", 2),  # aroma data, no FDC link
        ("Napa cabbage", 2),
    ],
)
def test_ingredient_tier(name: str, tier: int) -> None:
    assert L.ingredient_tier(name, "lacto_ferment") == tier


def test_t3_needs_a_use_level_row_for_that_type_and_aroma_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    levels = tmp_path / "ingredient_use_levels_v1.csv"
    levels.write_text(
        "# rows come from active library recipes and the lacto-ingredients research round\n"
        "ingredient,fermentation_type,role,share_median,share_lo,share_hi,source,notes\n"
        "Fresh ginger,kombucha,flavoring,0.02,0.01,0.03,test,\n"
        "Garlic,lacto_ferment,flavoring,0.02,0.01,0.04,test,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(L, "USE_LEVELS_CSV", levels)
    L._use_levels.cache_clear()
    try:
        assert L.ingredient_tier("Fresh ginger", "kombucha") == 3
        assert L.ingredient_tier("Fresh ginger", "kefir") == 2  # no row for this type
        assert L.ingredient_tier("Garlic", "lacto_ferment") == 1  # a row, but no aroma data
    finally:
        L._use_levels.cache_clear()
