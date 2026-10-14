"""Safety gate (design § 7, build plan B3): every rule at its boundaries, the mandatory card
lines, and the library's active recipes."""

from __future__ import annotations

import dataclasses
import math

import pytest

from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import gate as G
from fermenttrack.recommender import library as L
from fermenttrack.recommender.gate import IngredientRow, RecipeLike
from fermenttrack.safety.rule_catalog import RuleCatalog
from fermenttrack.safety.safety_types import RiskRule
from fermenttrack.safety.service import _scheme_for

SPORES = G.CERTIFIED_KOJI_STARTER
LACTIC_TYPES = sorted(k for k in PROFILES if k != "koji")


def _library(key: str) -> RecipeLike:
    recipe = L.get(key)
    assert recipe is not None
    return G.from_recipe(recipe)


def _salted(salt_g: float, ft: str = "lacto_ferment", temp: float = 20.0) -> RecipeLike:
    """A 1 kg batch with `salt_g` of salt."""
    rows = (
        IngredientRow("Cabbage", "base", 1000.0 - salt_g),
        IngredientRow("Salt", "additive", salt_g),
    )
    return RecipeLike(ft, rows, temperatures_c=(temp,))


def _koji(*temps: float, spores: bool) -> RecipeLike:
    rows = (IngredientRow("White rice", "base", 880.0), IngredientRow("Water", "liquid", 120.0))
    return RecipeLike("koji", rows, starters=(SPORES,) if spores else (), temperatures_c=temps)


def _rules(result: G.GateResult) -> set[str]:
    return {r.split(":")[0] for r in result.reasons}


# ── SALT-001 / SALT-002 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("salt_g", "rule"),
    [(20.0, None), (19.99, "SALT-001"), (100.0, None), (100.01, "SALT-002"), (0.0, "SALT-001")],
)
def test_salt_rules_at_their_boundaries(salt_g: float, rule: str | None) -> None:
    result = G.check(_salted(salt_g), [])
    assert result.ok is (rule is None)
    assert _rules(result) == ({rule} if rule else set())


def test_salt_is_percent_of_the_total_of_the_ingredient_rows() -> None:
    kimchi = _library("napa_kimchi_room_temp")
    assert G.salt_pct(kimchi) == pytest.approx(3.5, abs=0.005)  # optional rows included
    assert G.salt_pct(kimchi, with_optional=False) == pytest.approx(3.58, abs=0.005)
    assert G.check(kimchi, []).ok


def test_salt_must_pass_with_and_without_the_optional_rows() -> None:
    optional_salt = RecipeLike(
        "lacto_ferment",
        (
            IngredientRow("Cabbage", "base", 980.0),
            IngredientRow("Salt", "additive", 20.0, "optional"),
        ),
        temperatures_c=(20.0,),
    )
    result = G.check(optional_salt, [])
    assert not result.ok
    assert result.reasons == ("SALT-001: salt 0.00 % w/w < 2.0 % (core rows only)",)

    diluting = RecipeLike(
        "lacto_ferment",
        (
            IngredientRow("Cabbage", "base", 970.0),
            IngredientRow("Salt", "additive", 30.0),
            IngredientRow("Radish", "base", 600.0, "optional"),
        ),
        temperatures_c=(20.0,),
    )
    result = G.check(diluting, [])
    assert not result.ok
    assert result.reasons == ("SALT-001: salt 1.88 % w/w < 2.0 % (all rows)",)


def test_missing_mass_fails_the_salt_rule_closed() -> None:
    rows = (
        IngredientRow("Cabbage", "base", 980.0),
        IngredientRow("Dill", "flavoring", None),
        IngredientRow("Salt", "additive", 20.0),
    )
    unknown = RecipeLike("lacto_ferment", rows, temperatures_c=(20.0,))
    assert G.salt_pct(unknown) is None
    result = G.check(unknown, [])
    assert not result.ok and _rules(result) == {"SALT-001"}
    assert G.check(dataclasses.replace(unknown, fermentation_type="kombucha"), []).ok


@pytest.mark.parametrize(
    ("row", "mass"),
    [("Salt", math.inf), ("Salt", math.nan), ("Cabbage", math.nan), ("Cabbage", math.inf)],
)
def test_non_finite_mass_fails_the_salt_rule_closed(row: str, mass: float) -> None:
    masses = {"Cabbage": 980.0, "Salt": 20.0, row: mass}
    rows = tuple(IngredientRow(n, "base", m) for n, m in masses.items())
    recipe = RecipeLike("lacto_ferment", rows, temperatures_c=(20.0,))
    assert G.salt_pct(recipe) is None
    result = G.check(recipe, [])
    assert not result.ok and _rules(result) == {"SALT-001"}


def test_negative_mass_fails_the_salt_rule_closed() -> None:
    rows = (
        IngredientRow("Cabbage", "base", 980.0),
        IngredientRow("Salt", "additive", 20.0),
        IngredientRow("Water", "liquid", -100.0),  # would make the salt 2.22 %
    )
    recipe = RecipeLike("lacto_ferment", rows, temperatures_c=(20.0,))
    assert G.salt_pct(recipe) is None
    result = G.check(recipe, [])
    assert not result.ok
    assert result.reasons == ("SALT-001: salt % unknown, a mass is missing or invalid (all rows)",)


@pytest.mark.parametrize("ft", ["miso", "garum", "kombucha", "kefir", "cheese", "sourdough"])
@pytest.mark.parametrize("salt_g", [0.0, 119.0, 216.0])
def test_salt_rules_apply_to_lacto_ferment_only(ft: str, salt_g: float) -> None:
    result = G.check(_salted(salt_g, ft), [])
    assert not {"SALT-001", "SALT-002"} & _rules(result)
    assert result.ok is (ft not in G.SALT_BARRIER_MIN_PCT or salt_g > 0)  # miso, garum: a minimum


# ── SALT-BARRIER: the salt-barrier types' minimum (B9) ─────────────────────────────────────


@pytest.mark.parametrize(
    ("ft", "salt_g", "ok"),
    [
        ("miso", 39.9, False), ("miso", 40.0, True),  # BCCDC: at least 4 %
        ("garum", 82.9, False), ("garum", 83.0, True),  # the sourced recipes' lowest, 8.3 %
        ("miso", 216.0, True), ("garum", 300.0, True),  # no maximum
    ],
)  # fmt: skip
def test_salt_barrier_minimum_at_its_boundary(ft: str, salt_g: float, ok: bool) -> None:
    result = G.check(_salted(salt_g, ft), [])
    assert result.ok is ok
    assert _rules(result) == (set() if ok else {"SALT-BARRIER"})
    if not ok:
        pct = 100.0 * salt_g / 1000.0
        assert result.reasons == (
            f"SALT-BARRIER: salt {pct:.2f} % w/w < {G.SALT_BARRIER_MIN_PCT[ft]} % (all rows)",
        )


@pytest.mark.parametrize("ft", ["miso", "garum"])
def test_salt_barrier_fails_closed_on_unknown_salt(ft: str) -> None:
    rows = (
        IngredientRow("Soybeans", "base", 880.0),
        IngredientRow("White rice", "base", None),  # no mass: the salt % is unknown
        IngredientRow("Salt", "additive", 120.0),
    )
    result = G.check(RecipeLike(ft, rows, temperatures_c=(25.0,)), [])
    assert not result.ok
    assert result.reasons == (
        "SALT-BARRIER: salt % unknown, a mass is missing or invalid (all rows)",
    )
    no_salt = RecipeLike(ft, rows[:1], temperatures_c=(25.0,))
    assert _rules(G.check(no_salt, [])) == {"SALT-BARRIER"}  # no Salt row: 0 %


def test_salt_barrier_must_hold_without_the_optional_rows() -> None:
    rows = (
        IngredientRow("Soybeans", "base", 950.0),
        IngredientRow("Salt", "additive", 50.0, "optional"),
    )
    result = G.check(RecipeLike("miso", rows, temperatures_c=(25.0,)), [])
    assert result.reasons == ("SALT-BARRIER: salt 0.00 % w/w < 4.0 % (core rows only)",)


def test_every_active_salt_barrier_recipe_passes_its_minimum() -> None:
    """The minimums remove no library recipe: miso 6.1 and 11.9 %, the sand lance 12.0 %."""
    barrier = [r for r in L.active() if r.fermentation_type in G.SALT_BARRIER_MIN_PCT]
    assert {r.fermentation_type for r in barrier} == set(G.SALT_BARRIER_MIN_PCT)
    for recipe in barrier:
        like = G.from_recipe(recipe)
        pct = G.salt_pct(like)
        assert pct is not None and pct >= G.SALT_BARRIER_MIN_PCT[recipe.fermentation_type]
        assert G.check(like, []).ok, recipe.key


# ── TEMP-001, KOJI-002, KOJI-001 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ft", LACTIC_TYPES)
def test_temp_001_at_its_boundary_for_every_lactic_type(ft: str) -> None:
    salted = _salted(90.0, ft, temp=20.0)  # 9 %: passes every salt rule (SALT-*, SALT-BARRIER)
    assert G.check(salted, [G.LACTIC_MAX_C]).ok
    result = G.check(salted, [45.01])
    assert not result.ok and result.reasons == ("TEMP-001: 45.01 °C > 45 °C",)


def test_temp_001_does_not_apply_to_koji() -> None:
    assert "TEMP-001" not in _rules(G.check(_koji(46.0, spores=True), []))


@pytest.mark.parametrize("spores", [False, True])
def test_koji_002_at_its_boundary(spores: bool) -> None:
    assert G.check(_koji(G.KOJI_MIN_C, spores=spores), []).ok
    result = G.check(_koji(24.99, spores=spores), [])
    assert not result.ok and _rules(result) == {"KOJI-002"}


def test_koji_001_at_its_boundary_without_certified_spores() -> None:
    assert G.check(_koji(G.KOJI_MAX_C, spores=False), []).ok
    result = G.check(_koji(30.0, spores=False), [33.01])
    assert not result.ok
    assert result.reasons == (f"KOJI-001: 33.01 °C > 33 °C without {SPORES} as the only starter",)


def test_koji_001_certified_tane_koji_exception() -> None:
    result = G.check(_koji(30.0, spores=True), [33.01, 35.0])
    assert result.ok
    assert G.TANE_KOJI_LINE in result.safety_lines


def test_koji_001_exception_needs_the_certified_strain_as_the_only_starter() -> None:
    mixed = dataclasses.replace(_koji(30.0, spores=True), starters=(SPORES, "Starter/levain"))
    assert G.check(mixed, [33.0]).ok
    assert _rules(G.check(mixed, [35.0])) == {"KOJI-001"}
    assert G.TANE_KOJI_LINE in G.check(mixed, [33.0]).safety_lines  # the strain is present


def test_rice_koji_capped_at_33_unless_it_keeps_its_certified_spores() -> None:
    rice = _library("rice_koji_steamed_rice")
    assert rice.starters == (SPORES,)
    lo, hi = PROFILES["koji"].temp_range
    assert G.check(rice, [lo, 33.0, 34.0, hi]).ok
    no_spores = dataclasses.replace(rice, starters=())
    assert G.check(no_spores, [lo, 33.0]).ok
    assert _rules(G.check(no_spores, [lo, 34.0, hi])) == {"KOJI-001"}
    assert G.TANE_KOJI_LINE not in G.check(no_spores, [lo]).safety_lines


def test_the_recipes_own_temperatures_are_always_checked() -> None:
    result = G.check(_koji(34.0, spores=False), [30.0])
    assert not result.ok
    assert result.reasons == (f"KOJI-001: 34 °C > 33 °C without {SPORES} as the only starter",)


def test_every_temperature_is_checked_and_reported() -> None:
    result = G.check(_koji(30.0, spores=False), [24.0, 34.0, 36.0])
    assert _rules(result) == {"KOJI-001", "KOJI-002"}
    assert len(result.reasons) == 3


# ── fails closed ────────────────────────────────────────────────────────────────────────────


def test_no_temperature_fails() -> None:
    result = G.check(dataclasses.replace(_salted(30.0), temperatures_c=()), [])
    assert not result.ok and result.reasons == ("no temperature to check",)


def test_non_finite_temperature_fails() -> None:
    assert not G.check(_salted(30.0), [math.nan]).ok
    assert not G.check(_koji(30.0, spores=True), [math.inf]).ok


def test_unknown_fermentation_type_fails() -> None:
    result = G.check(_salted(30.0, "mead"), [])
    assert not result.ok and result.reasons == ("unknown fermentation type 'mead'",)


# ── mandatory card lines, by safety barrier ─────────────────────────────────────────────────

PH = (G.PH_DEADLINE_LINE, G.PH_LOG_LINE)
LINES_BY_TYPE = {
    "lacto_ferment": PH,
    "kombucha": PH,
    "kefir": PH,
    "cheese": PH,
    "vinegar": (*PH, *G.VINEGAR_LINES),
    "koji": (G.KOJI_TEMP_LINE,),
    "miso": (G.SALT_BARRIER_LINE,),
    "garum": (G.SALT_BARRIER_LINE,),
    "sourdough": (),  # planner hand-off; baking is its barrier
}


def test_line_sets_cover_every_profile() -> None:
    assert set(LINES_BY_TYPE) == set(PROFILES)


@pytest.mark.parametrize(("ft", "lines"), sorted(LINES_BY_TYPE.items()))
def test_safety_lines_per_type(ft: str, lines: tuple[str, ...]) -> None:
    assert G.check(_salted(30.0, ft), []).safety_lines == lines
    assert G.needs_ph_reminder(ft) is (G.PH_DEADLINE_LINE in lines)


def test_certified_koji_adds_the_tane_koji_line() -> None:
    lines = G.check(_koji(30.0, spores=True), []).safety_lines
    assert lines == (G.KOJI_TEMP_LINE, G.TANE_KOJI_LINE)


def test_acid_safety_types_are_the_profiles_with_a_ph_safety_line() -> None:
    assert {k for k, p in PROFILES.items() if p.ph_safety_line} == G.ACID_SAFETY_TYPES


def test_line_wording() -> None:
    assert "≤ 4.6 within 48 h" in G.PH_DEADLINE_LINE
    koji_hi = PROFILES["koji"].temp_range[1]
    assert f"{G.KOJI_MIN_C:g}–{G.KOJI_MAX_C:g} °C" in G.KOJI_TEMP_LINE
    assert f"up to {koji_hi:g} °C only with certified tane-koji" in G.KOJI_TEMP_LINE
    assert "do not reduce the salt" in G.SALT_BARRIER_LINE


def test_vinegar_acidity_lines_follow_the_curation_spec() -> None:
    for key in ("wine_orleans_surface", "cider_vinegar_surface"):
        lines = G.check(_library(key), []).safety_lines
        assert "≥ 5 % acetic acid" in lines[2]
        assert "canning or room-temperature storage unless verified" in lines[3]


def test_safety_lines_are_returned_even_when_the_gate_fails() -> None:
    result = G.check(_salted(5.0), [])
    assert not result.ok and result.safety_lines == (G.PH_DEADLINE_LINE, G.PH_LOG_LINE)


# ── consistency with the batch safety layer and the library ────────────────────────────────


def test_scheme_matches_the_batch_safety_service() -> None:
    for ft in PROFILES:
        assert G.scheme(ft) == _scheme_for(ft)


def test_thresholds_match_risk_rules_yaml() -> None:
    catalog = RuleCatalog()

    def rule(rule_id: str) -> RiskRule:
        r = catalog.get_rule(rule_id)
        assert r is not None
        return r

    assert rule("SALT-001").condition == f"salt_pct < {G.SALT_MIN_PCT}"
    assert rule("SALT-002").condition == f"salt_pct > {G.SALT_MAX_PCT}"
    assert rule("TEMP-001").condition == f"temperature_c > {G.LACTIC_MAX_C:g}"
    assert rule("KOJI-002").condition == f"temperature_c < {G.KOJI_MIN_C:g}"
    assert f"temperature_c > {G.KOJI_MAX_C:g}" in rule("KOJI-001").condition
    assert "certified tane-koji" in rule("KOJI-001").exceptions[0]
    for rule_id in ("SALT-001", "SALT-002", "TEMP-001"):
        assert rule(rule_id).fermentation_schemes == ["lactic"]
    for rule_id in ("KOJI-001", "KOJI-002"):
        assert rule(rule_id).fermentation_schemes == ["enzymatic_koji"]


def test_from_recipe_reads_the_served_recipe() -> None:
    sand_lance = _library("pacific_sand_lance_rice_koji_fish_sauce")
    assert sand_lance.fermentation_type == "garum"
    assert sand_lance.temperatures_c == (18.0, 20.0)  # median 18 plus the 0:20;48:18 schedule
    assert [(i.name, i.g_per_kg) for i in sand_lance.ingredients][0] == ("Anchovies", 800.0)
    assert sand_lance.starters == ()
    dill = _library("dill_cucumber_pickles_brined")
    assert {i.name: i.g_per_kg for i in dill.ingredients}["Dill"] is None


@pytest.mark.parametrize("recipe", L.active(), ids=lambda r: r.key)
def test_every_active_recipe_passes_at_its_own_temperatures(recipe: L.Recipe) -> None:
    result = G.check(G.from_recipe(recipe), [])
    assert result.ok, result.reasons
    expected = LINES_BY_TYPE[recipe.fermentation_type]  # rice koji adds the tane-koji line
    assert result.safety_lines[: len(expected)] == expected


def test_garum_profile_range_runs_past_temp_001() -> None:
    """Known conflict for the grid and the slider (B4/B5): garum's profile range reaches 60 °C,
    but TEMP-001 caps every lactic-scheme type, garum included, at 45 °C."""
    sand_lance = _library("pacific_sand_lance_rice_koji_fish_sauce")
    lo, hi = PROFILES["garum"].temp_range
    assert G.check(sand_lance, [lo, G.LACTIC_MAX_C]).ok
    assert _rules(G.check(sand_lance, [hi])) == {"TEMP-001"}
