"""Offline evaluation of the Proven recommender on the committed grid (design § 13.1, build
plan B5). Each test prints its measured value and n (run with -s to see them).

- E1: a library recipe comes back in the top 3 when you ask for its core non-staple
  ingredients (target 90 %), over the recipes that have one (a recipe whose core is all
  staples has no ingredient query; those 9 are pinned).
- E3: the unclipped model window overlaps the documented duration (target 80 %), with and
  without the source-only and beyond-horizon recipes, which overlap by construction. Known
  miss, reported and not worked around: kimchi. The engine reaches pH 4.6 in only 1-11 % of
  kimchi members by the grid's 72 h end, so the window collapses at the safety milestone
  (B3's rule: never taste before modelled acidification).
- E4: 500 seeded random requests: every served card passes the gate at its served
  temperature and slider ends; served, slider, booked and planner temperatures stay inside
  the documented span within the safety limits (koji ≤ 35 °C with certified tane-koji as the
  only starter, else ≤ 33 °C); the model temperature stays inside the profile's range;
  source_only ⇔ served outside it; and the card carries its type's mandatory safety lines.
  Plus a fixed sweep: every active recipe at its edge temperatures, through the card, the
  live forecast's temperature and Start batch.
- E5: the same request and grid give byte-identical JSON.
- E6: POST /recommendations from a warm grid, locally (a proxy for the Render p95 target).

A target missed is reported and xfailed strictly with the measured number; it is not tuned.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import numpy as np
import pytest
from httpx import AsyncClient

from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import gate, grid, library
from fermenttrack.recommender import service as S
from fermenttrack.schemas import RecommendationsOut

SEED = 20261008
FORBIDDEN = ("tastes like", "smells like", "will taste")
PH_LINES = (gate.PH_DEADLINE_LINE, gate.PH_LOG_LINE)


def _query(recipe: library.Recipe) -> list[str]:
    core = (i.name for i in recipe.ingredients if i.required == "core")
    return list(dict.fromkeys(n for n in core if n not in library.STAPLES))


def _e1() -> tuple[int, int, list[str], list[str]]:
    """(hits, queryable, misses, recipes whose core is only staples)."""
    hits, n, misses, staples_only = 0, 0, [], []
    for recipe in library.active():
        query = _query(recipe)
        if not query:
            staples_only.append(recipe.key)
            continue
        n += 1
        cards, _ = S.proven_cards(query, (), None)
        if recipe.key in [c.recipe.key for c in cards]:
            hits += 1
        else:
            misses.append(recipe.key)
    return hits, n, misses, staples_only


def test_e1_a_recipe_comes_back_for_its_ingredients() -> None:
    """E1 is defined over the recipes with at least one non-staple core ingredient: a recipe
    whose core is all staples has no ingredient query (not a miss)."""
    hits, n, misses, _ = _e1()
    print(f"\nE1 = {hits}/{n} = {hits / n:.0%} over eligible recipes; misses {misses}")
    assert n == 11
    assert hits / n >= 0.9


def test_e1_ineligible_recipes_are_the_staples_only_ones() -> None:
    """Informational, pinned: the 7 sourdough styles and the 2 kombuchas have only staples
    (flour, water, starter; tea, sugar, SCOBY) as core ingredients."""
    _, _, _, staples_only = _e1()
    print(f"\nE1 ineligible ({len(staples_only)}, core is only staples): {staples_only}")
    sourdough = {r.key for r in library.active() if r.handoff == "planner"}
    assert sourdough == {
        "home_starter", "levain_liquide", "levain_dur", "lievito_madre", "san_francisco",
        "rye_sour", "type_ii",
    }  # fmt: skip
    assert set(staples_only) == sourdough | {"black_tea_kombucha_1f", "green_dominant_kombucha"}


def _reported_targets(recipe: library.Recipe) -> tuple[S.Target, ...]:
    aromas = [a for a in recipe.reported_aromas if a in S.AROMA_SERIES][: S.MAX_TARGETS]
    tastes = [a for a in recipe.reported_aromas if a in S.TASTES]
    return S.parse_targets(aromas, tastes[: S.MAX_TARGETS - len(aromas)])


def _e3() -> list[tuple[str, bool, bool]]:
    """(recipe, overlaps, by construction) per active recipe with a documented duration, at
    its served temperature, targets = its reported aromas and tastes."""
    rows = []
    for recipe in library.active():
        if recipe.duration_h is None:  # the four planner styles without a duration
            continue
        temp = S.resolve_temperature(recipe, None)
        stats = grid.interp_temp(recipe.key, temp.served_c)
        w = S.evaluate(recipe, stats, temp, _reported_targets(recipe), clip=False).window
        d = recipe.duration_h
        overlaps = w is not None and w.taste_from_h <= d.hi and w.stop_by_h >= d.lo
        by_construction = temp.source_only or "beyond_horizon" in recipe.model_scope
        rows.append((recipe.key, overlaps, by_construction))
    return rows


def test_e3_the_unclipped_window_overlaps_the_documented_duration() -> None:
    rows = _e3()
    hits = sum(o for _, o, _ in rows)
    misses = [k for k, o, _ in rows if not o]
    print(f"\nE3 (all) = {hits}/{len(rows)} = {hits / len(rows):.1%}; misses {misses}")
    assert len(rows) == 16
    assert hits / len(rows) >= 0.8


def test_e3_without_the_windows_that_overlap_by_construction() -> None:
    rows = [r for r in _e3() if not r[2]]
    hits = sum(o for _, o, _ in rows)
    print(f"\nE3 (without source-only and beyond-horizon) = {hits}/{len(rows)} = "
          f"{hits / len(rows):.1%}; misses {[k for k, o, _ in rows if not o]}")  # fmt: skip
    assert len(rows) == 9
    assert hits / len(rows) >= 0.8


# ── random requests ─────────────────────────────────────────────────────

_POOL = sorted(
    {i.name for r in library.active() for i in r.ingredients}
    | set(sorted(library.CATALOGUE_NAMES)[:8])
    | {"Not a catalogue name"}
)
_VOCAB = (*S.AROMA_SERIES, *S.TASTES)


def random_request(rng: np.random.Generator) -> dict[str, Any]:
    if rng.random() < 0.5:  # a subset of one recipe's rows: requests that serve cards
        recipe = library.active()[int(rng.integers(len(library.active())))]
        names = sorted({i.name for i in recipe.ingredients})
        k = int(rng.integers(1, min(3, len(names)) + 1))
        ingredients = [str(x) for x in rng.choice(names, size=k, replace=False)]
    else:
        k = int(rng.integers(0, 4))
        ingredients = [str(x) for x in rng.choice(_POOL, size=k, replace=False)]
    n_targets = int(rng.integers(0, S.MAX_TARGETS + 1))
    picks = [str(x) for x in rng.choice(_VOCAB, size=n_targets, replace=False)]
    if not ingredients and not picks:
        picks = [str(rng.choice(_VOCAB))]
    return {
        "ingredients": ingredients,
        "aromas": [p for p in picks if p in S.AROMA_SERIES],
        "tastes": [p for p in picks if p in S.TASTES],
        "mode": str(rng.choice(["proven", "experimental", "both"])),
        "temperature_c": None if rng.random() < 0.3 else round(float(rng.uniform(-5, 60)), 1),
        "batch_g": round(float(rng.uniform(50, 5000)), 1),
    }


def _mandatory_lines(card: dict[str, Any]) -> tuple[set[str], set[str]]:
    """(lines the card's type must carry, lines it must not), from the design's table (§ 7),
    independently of gate.safety_lines."""
    ft = card["fermentation_type"]
    must: set[str] = set()
    if ft in {"lacto_ferment", "kombucha", "kefir", "cheese", "vinegar"}:
        must |= set(PH_LINES)
    if ft == "vinegar":
        must |= set(gate.VINEGAR_LINES)
    if ft == "koji":
        must.add(gate.KOJI_TEMP_LINE)
        if gate.CERTIFIED_KOJI_STARTER in card["recipe"]["starters"]:
            must.add(gate.TANE_KOJI_LINE)
    if ft in {"miso", "garum"}:
        must.add(gate.SALT_BARRIER_LINE)
    must_not = set() if ft in {"lacto_ferment", "kombucha", "kefir", "cheese", "vinegar"} else set(
        PH_LINES
    )
    return must, must_not


def safe_range(recipe: library.Recipe, starters: list[str]) -> tuple[float, float]:
    """Where anything may be served, booked or put in a planner link (Q26 as agreed with the
    owner), from the design independently of the service: the documented span within the
    safety limits; koji 25 °C (KOJI-002) to 35 °C with certified tane-koji as the only starter
    ("up to 35 °C only with certified tane-koji"), else 33 °C (KOJI-001); TEMP-001's 45 °C
    for the lactic types. Not the profile range."""
    assert recipe.temp_c is not None
    lo, hi = recipe.temp_c.lo, recipe.temp_c.hi
    if recipe.fermentation_type == "koji":
        cap = 35.0 if starters == [gate.CERTIFIED_KOJI_STARTER] else 33.0
        return max(lo, 25.0), min(hi, cap)
    return lo, min(hi, gate.LACTIC_MAX_C)


def temperature_violations(
    recipe: library.Recipe, starters: list[str], what: str, temps: list[float]
) -> list[str]:
    lo, hi = safe_range(recipe, starters)
    return [f"{recipe.key}: {what} {t} °C outside {lo}-{hi} °C" for t in temps if not lo <= t <= hi]


def model_violations(recipe: library.Recipe, what: str, model_c: float) -> list[str]:
    """The model temperature stays inside the profile's range (Q26)."""
    p_lo, p_hi = PROFILES[recipe.fermentation_type].temp_range
    return [] if p_lo <= model_c <= p_hi else [f"{recipe.key}: {what} model {model_c} °C"]


def card_violations(card: dict[str, Any]) -> list[str]:
    key = card["recipe_key"]
    recipe = library.get(key)
    if recipe is None or recipe.status != "active":
        return [f"{key}: not an active library recipe"]
    out = []
    t = card["temperature"]
    temps = [t["served_c"], *((t["slider"]["min_c"], t["slider"]["max_c"]) if t["slider"] else ())]
    rows = tuple(
        gate.IngredientRow(i["name"], i["role"], i["grams"], i["required"])
        for i in card["recipe"]["ingredients"]
    )
    own = {c for _, c in card["recipe"]["temp_schedule"]} | {card["recipe"]["temperature_c"]}
    as_served = gate.RecipeLike(
        card["fermentation_type"], rows, tuple(card["recipe"]["starters"]), tuple(sorted(own))
    )
    for like in (as_served, gate.from_recipe(recipe)):
        result = gate.check(like, temps)
        if not result.ok:
            out.append(f"{key} @ {temps}: gate {result.reasons}")
    starters = list(card["recipe"]["starters"])
    out += temperature_violations(recipe, starters, "served/slider", temps)
    out += temperature_violations(recipe, starters, "booked", sorted(own))
    if card["planner_link"]:
        token = card["planner_link"].removeprefix("#/levain?p=")
        plan = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
        out += temperature_violations(
            recipe, starters, "planner", [plan["plan"]["levain"]["temperature_c"]]
        )
    out += model_violations(recipe, "card", t["model_c"])
    g = grid.temps(key)
    if not g[0] <= t["model_c"] <= g[-1]:
        out.append(f"{key}: card model {t['model_c']} °C outside the grid's {g[0]}-{g[-1]} °C")
    p_lo, p_hi = PROFILES[recipe.fermentation_type].temp_range
    if t["source_only"] != (not p_lo <= t["served_c"] <= p_hi):
        out.append(f"{key}: source_only {t['source_only']} at {t['served_c']} °C")
    window_notes = (card["window"] or {}).get("notes", [])
    named = any(n.startswith("timings from the source at") for n in window_notes)
    if t["source_only"] and not named:
        out.append(f"{key}: a source-only window without its temperatures")
    must, must_not = _mandatory_lines(card)
    lines = set(card["safety_lines"])
    if not must <= lines:
        out.append(f"{key}: missing safety lines {must - lines}")
    if must_not & lines:
        out.append(f"{key}: a pH deadline on a {card['fermentation_type']} card")
    if card["level"] not in {None, "Low", "Med", "High"}:
        out.append(f"{key}: level {card['level']!r}")
    words = " ".join(card["notes"] + window_notes).lower()
    if "does not cover" in words:
        out.append(f"{key}: claims the model does not cover a temperature it computes at")
    if "safety limit" in words and t["served_c"] not in safe_range(recipe, starters):
        out.append(f"{key}: a safety-limit note without a safety clamp")
    if any(f in words for f in FORBIDDEN):
        out.append(f"{key}: forbidden wording")
    return out


def test_e4_the_checker_catches_a_bad_card() -> None:
    """The property test is not vacuous: tampered cards are flagged."""
    [card] = S.recommend(["Napa cabbage"], [], [])["proven"]["cards"]
    assert card_violations(card) == []
    no_lines = card | {"safety_lines": []}
    assert any("missing safety lines" in v for v in card_violations(no_lines))
    hot = card | {"temperature": card["temperature"] | {"served_c": 50.0}}
    assert any("TEMP-001" in v for v in card_violations(hot))
    salty = card | {"recipe": card["recipe"] | {"ingredients": [
        i | {"grams": i["grams"] * 10} if i["name"] == "Salt" else i
        for i in card["recipe"]["ingredients"]
    ]}}  # fmt: skip
    assert any("SALT-002" in v for v in card_violations(salty))
    worded = card | {"notes": ["this tastes like apples"]}
    assert "napa_kimchi_room_temp: forbidden wording" in card_violations(worded)
    [koji] = S.recommend(["White rice"], [], [], temperature_c=30)["proven"]["cards"][:1]
    assert koji["recipe_key"] == "rice_koji_steamed_rice" and card_violations(koji) == []
    hot_koji = koji | {"temperature": koji["temperature"] | {"served_c": 39.0}}
    assert any("served/slider 39.0 °C outside" in v for v in card_violations(hot_koji))
    booked_hot = koji | {"recipe": koji["recipe"] | {"temperature_c": 36.0}}
    assert any("booked 36.0 °C outside" in v for v in card_violations(booked_hot))
    false_claim = card | {"notes": ["20 °C is above the safety limit for this recipe; shown at 20"]}
    assert any("safety-limit note without" in v for v in card_violations(false_claim))
    flipped = card | {"temperature": card["temperature"] | {"source_only": True}}
    assert any("source_only True" in v for v in card_violations(flipped))


def _sweep_temperatures(recipe: library.Recipe) -> list[float | None]:
    assert recipe.temp_c is not None
    return [None, recipe.temp_c.lo, recipe.temp_c.hi, *grid.temps(recipe.key), -5.0, 60.0]


def test_e4_sweep_every_recipe_at_its_edge_temperatures() -> None:
    """Every active recipe × {no temperature, documented lo and hi, each grid temperature,
    -5 and 60 °C}: the card, the batch Start batch would book and a sourdough planner link
    stay inside the documented span within the safety limits (koji ≤ 35 °C with certified
    tane-koji as the only starter, else ≤ 33 °C); the model and live-forecast temperatures
    stay inside the profile's range; source_only ⇔ served outside it."""
    cases, violations = 0, []
    for recipe in library.active():
        starters = [i.name for i in recipe.ingredients if i.role == "starter"]
        for temp_c in _sweep_temperatures(recipe):
            cases += 1
            card, result = S.build_card(recipe, (), temp_c)
            if card is None:
                violations.append(f"{recipe.key} @ {temp_c}: refused {result.reasons}")
                continue
            violations += card_violations(S.card_json(card))
            forecast_c = S.model_temperature(recipe, card.temperature.served_c)
            violations += model_violations(recipe, "live forecast", forecast_c)
            if recipe.handoff == "planner":
                continue
            plan = S.batch_plan(recipe.key, [], [], temp_c, 1000.0, "proven")
            booked = [plan.expected_temperature_c, plan.link["temperature_c"]]
            booked += [c for _, c in plan.link["temp_schedule"] or ()]
            violations += temperature_violations(recipe, starters, "Start batch", booked)
    print(f"\nE4 sweep: {len(violations)} violations over {cases} recipe × temperature cases")
    assert cases >= 20 * 6
    assert violations == []


def test_e4_every_served_card_passes_the_gate_and_carries_its_safety_lines() -> None:
    rng = np.random.default_rng(SEED)
    n_requests, n_cards, violations = 500, 0, []
    for _ in range(n_requests):
        req = random_request(rng)
        body = S.recommend(
            req["ingredients"], req["aromas"], req["tastes"], req["mode"], req["temperature_c"],
            req["batch_g"],
        )  # fmt: skip
        RecommendationsOut.model_validate(body)
        for card in body["proven"]["cards"]:
            n_cards += 1
            violations += card_violations(card)
    print(f"\nE4: {len(violations)} violations over {n_cards} served cards "
          f"from {n_requests} seeded requests")  # fmt: skip
    assert n_cards > 500  # the requests do serve cards
    assert violations == []


@pytest.mark.asyncio
async def test_e5_the_same_request_gives_byte_identical_json(client: AsyncClient) -> None:
    rng = np.random.default_rng(SEED + 5)
    requests = [random_request(rng) for _ in range(25)]
    first = [(await client.post("/recommendations", json=r)).content for r in requests]
    second = [(await client.post("/recommendations", json=r)).content for r in requests]
    grid.load.cache_clear()  # a fresh load of the same grid and library
    library.load_library.cache_clear()
    third = [(await client.post("/recommendations", json=r)).content for r in requests]
    same = sum(a == b == c for a, b, c in zip(first, second, third, strict=True))
    print(f"\nE5: {same}/{len(requests)} requests byte-identical across 3 calls (one after a "
          "grid and library reload)")  # fmt: skip
    assert b"created_at" not in b"".join(first)
    assert same == len(requests)


@pytest.mark.asyncio
async def test_e6_recommendations_are_fast_from_a_warm_grid(client: AsyncClient) -> None:
    rng = np.random.default_rng(SEED + 6)
    requests = [random_request(rng) for _ in range(40)]
    await client.post("/recommendations", json=requests[0])  # warm: the grid is loaded
    times = []
    for r in requests:
        started = time.perf_counter()
        resp = await client.post("/recommendations", json=r)
        times.append(time.perf_counter() - started)
        assert resp.status_code == 200
    p50, p95 = (float(np.percentile(times, q)) for q in (50, 95))
    print(f"\nE6 (local, warm, n={len(times)}): p50 {p50 * 1000:.0f} ms, p95 {p95 * 1000:.0f} ms, "
          f"max {max(times) * 1000:.0f} ms")  # fmt: skip
    assert p95 < 1.5
