"""The recommender's API (build plans B5 and B7; design §§ 5, 6, 7, 8.5, 10.1, 11): the service's
temperature, gate, window and ranking rules, POST /recommendations (Proven and Experimental),
the live POST /recommendations/forecast (and a variant's confirmation), Start batch (POST
/batches/from-recommendation) for library recipes and variants, and your own batch as an
Experimental parent (Q16)."""

from __future__ import annotations

import base64
import dataclasses
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.config import settings
from fermenttrack.main import app
from fermenttrack.models import (
    SAFETY_REMINDER,
    Batch,
    BatchIngredient,
    Culture,
    FdcFood,
    FdcFoodNutrient,
    Ingredient,
    RecommendationLink,
    Reminder,
)
from fermenttrack.prediction import service as engine
from fermenttrack.prediction.sourdough import plan_from_dict
from fermenttrack.recommender import gate, grid, library, operators, run, score
from fermenttrack.recommender import service as S
from fermenttrack.routers.recommendations import PH_REMINDER, _own_parent
from fermenttrack.schemas import RecommendationsOut, SourdoughPlanIn
from fermenttrack.seed_data import (
    INGREDIENT_SEED_DATA,
    INGREDIENT_SEED_DATA_V2,
    INGREDIENT_SEED_DATA_V3,
    INGREDIENT_SEED_DATA_V4,
    RETIRED_V3,
)
from tests.conftest import TEST_USER_ID

KIMCHI = "napa_kimchi_room_temp"
GARUM = "pacific_sand_lance_rice_koji_fish_sauce"
KOJI = "rice_koji_steamed_rice"
KRAUT = "sauerkraut_dry_salted"
PERSIMMON = 169941  # USDA FDC: Persimmons, japanese, raw
SOURCE_ONLY_AT_MEDIAN = {
    "black_tea_kombucha_1f",
    "lactic_fresh_cheese_curd",
    "cider_vinegar_surface",
    GARUM,
    "type_ii",
}
FORBIDDEN = ("tastes like", "smells like", "will taste")


def _recipe(key: str) -> library.Recipe:
    recipe = library.get(key)
    assert recipe is not None
    return recipe


def _strings(x: Any) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [s for v in x.values() for s in _strings(v)]
    if isinstance(x, list):
        return [s for v in x for s in _strings(v)]
    return []


def _decode(link: str) -> dict[str, Any]:
    token = link.removeprefix("#/levain?p=")
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    doc = json.loads(raw.decode("utf-8"))
    assert doc["v"] == 1
    return dict(doc["plan"])


@pytest_asyncio.fixture
async def catalogue(db_session: AsyncSession) -> None:
    """Every live catalogue ingredient, as the migrations seed them."""
    seen: set[str] = set()
    for seed in (
        INGREDIENT_SEED_DATA, INGREDIENT_SEED_DATA_V2, INGREDIENT_SEED_DATA_V3,
        INGREDIENT_SEED_DATA_V4,
    ):  # fmt: skip
        for name, role, systems in seed:
            if name in seen or name in RETIRED_V3:
                continue
            seen.add(name)
            db_session.add(Ingredient(name=name, default_role=role, fermentation_systems=systems))
    await db_session.commit()


@pytest_asyncio.fixture
async def anonymous() -> AsyncIterator[AsyncClient]:
    """A client with no auth override: the real bearer-token check runs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── service: temperature, source-only, gate ─────────────────────────────


def test_source_only_is_set_for_exactly_five_recipes_at_their_median() -> None:
    """Q26, pinned (B3 handoff): these five are served at their source temperature, outside
    the model's range, so their window comes from the source alone."""
    got = {r.key for r in library.active() if S.resolve_temperature(r, None).source_only}
    assert got == SOURCE_ONLY_AT_MEDIAN
    for r in library.active():
        assert r.temp_c is not None
        temp = S.resolve_temperature(r, None)
        assert temp.served_c == r.temp_c.median  # the source's own temperature, never moved
        assert S.source_only(r, r.temp_c.median) == (r.key in got)
    type_ii, _ = S.build_card(_recipe("type_ii"), (), None)  # documented 34-40, profile 22-30
    assert type_ii is not None
    assert _decode(S.card_json(type_ii)["planner_link"])["levain"]["temperature_c"] == 37


def test_source_only_follows_the_served_temperature() -> None:
    kombucha = _recipe("black_tea_kombucha_1f")  # documented 27-33 °C, profile 20-28 °C
    assert S.resolve_temperature(kombucha, None).source_only
    assert S.resolve_temperature(kombucha, None).slider_c == (27.0, 33.0)
    assert not S.resolve_temperature(kombucha, 27.5).source_only  # slid into the profile
    card, _ = S.build_card(kombucha, (), 27.5)
    assert card is not None and card.evaluation.basis == "model"


def test_a_temperature_outside_the_documented_span_is_served_at_the_nearest() -> None:
    kraut = _recipe("sauerkraut_dry_salted")  # documented 21.1-23.9 °C
    hot = S.resolve_temperature(kraut, 30.0)
    assert hot.served_c == 23.9
    assert hot.notes == (
        "your temperature is outside this recipe's documented range; shown at 23.9 °C",
    )
    assert S.resolve_temperature(kraut, 10.0).served_c == 21.1
    inside = S.resolve_temperature(kraut, 22.04)
    assert inside.served_c == 22.0 and inside.notes == ()
    assert S.resolve_temperature(kraut, None).served_c == 22.5  # the recipe's median


def test_the_slider_is_the_documented_span_within_the_safety_limits() -> None:
    # certified tane-koji as the only starter: up to the card's own 35 °C, not the source's 40
    assert S.resolve_temperature(_recipe(KOJI), None).slider_c == (27.0, 35.0)
    two_starters = gate.RecipeLike(
        "koji", (gate.IngredientRow("White rice", "base", 1000.0),),
        starters=(gate.CERTIFIED_KOJI_STARTER, "Starter/levain"),
    )  # fmt: skip
    assert S._safe_span(two_starters, 27.0, 40.0) == (27.0, 33.0)  # KOJI-001
    garum = gate.RecipeLike(
        "garum", (gate.IngredientRow("Anchovies", "base", 880.0),
                  gate.IngredientRow("Salt", "additive", 120.0)),  # 12 %: the salt barrier holds
    )  # fmt: skip
    assert S._safe_span(garum, 20.0, 60.0) == (20.0, 45.0)  # TEMP-001
    # not limited to the profile: cheese 21-22 °C (profile 28-32), sand lance 18-20 (20-60)
    assert S.resolve_temperature(_recipe("lactic_fresh_cheese_curd"), None).slider_c == (
        21.0, 22.0,
    )  # fmt: skip
    assert S.resolve_temperature(_recipe(GARUM), None).slider_c == (18.0, 20.0)
    assert gate.KOJI_TEMP_LINE.endswith(f"up to {S.CERTIFIED_KOJI_MAX_C:g} °C only with "
                                        "certified tane-koji.")  # fmt: skip


def test_a_gate_failure_removes_the_card(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "LACTIC_MAX_C", 22.0)  # sauerkraut is served at 22.5 °C
    body = S.recommend(["Cabbage"], [], [])
    assert body["proven"]["cards"] == []
    assert body["proven"]["message"] == "No proven recipe passes the safety checks here."
    [refused] = body["debug"]["gated_out"]
    assert refused["recipe_key"] == "sauerkraut_dry_salted"
    assert any(r.startswith("TEMP-001: 22.5 °C") for r in refused["reasons"])


def test_a_staged_recipe_keeps_its_source_stages() -> None:
    sand_lance = _recipe(GARUM)  # profile 20-60 °C, documented 18-20 °C
    assert sand_lance.temp_schedule == ((0.0, 20.0), (48.0, 18.0))
    default = S.resolve_temperature(sand_lance, None)
    assert (default.served_c, default.source_only) == (18.0, True)
    assert S.card_schedule(sand_lance, default, None) == sand_lance.temp_schedule
    asked = S.resolve_temperature(sand_lance, 19.0)
    assert S.card_schedule(sand_lance, asked, 19.0) == ((0.0, 19.0), (48.0, 18.0))
    assert not S.resolve_temperature(sand_lance, 20.0).source_only


def test_certified_koji_is_never_served_above_35_c() -> None:
    """KOJI-001 sets no ceiling for certified tane-koji, but the card's own line says "up to
    35 °C": the documented 40 °C is never served or booked."""
    koji = _recipe(KOJI)  # documented 27-40 °C, certified spores as the only starter
    hot = S.resolve_temperature(koji, 39.0)
    assert hot.served_c == 35.0
    assert hot.notes == ("39 °C is above the safety limit for this recipe; shown at 35 °C",)
    beyond = S.resolve_temperature(koji, 50.0)
    assert beyond.served_c == 35.0
    assert beyond.notes == ("50 °C is above the safety limit for this recipe; shown at 35 °C",)
    two_starters = dataclasses.replace(
        koji, ingredients=(*koji.ingredients, dataclasses.replace(
            koji.ingredients[-1], name="Starter/levain"
        )),
    )  # fmt: skip
    assert S.resolve_temperature(two_starters, 34.0).served_c == 33.0  # KOJI-001
    assert S.resolve_temperature(two_starters, None).slider_c == (27.0, 33.0)
    # the ceiling holds even where the gate alone would pass: check_gate refuses above it
    over = dataclasses.replace(S.resolve_temperature(koji, None), served_c=36.0)
    assert not S.check_gate(koji, over).ok


def test_a_source_only_card_names_its_temperatures() -> None:
    cheese = _recipe("lactic_fresh_cheese_curd")  # documented 21-22 °C, profile 28-32 °C
    card, _ = S.build_card(cheese, (), None)
    assert card is not None
    body = S.card_json(card)
    t = body["temperature"]
    assert (t["served_c"], t["model_c"], t["source_only"]) == (21.5, 28, True)
    assert body["recipe"]["temperature_c"] == 21.5
    assert body["window"]["basis"] == "source"
    assert (body["window"]["taste_from_h"], body["window"]["stop_by_h"]) == (10, 21)
    assert body["window"]["notes"] == [
        "timings from the source at 21–22 °C (the model covers 28–32 °C); aroma levels are "
        "computed at 28 °C"
    ]
    words = " ".join(_strings(body)).lower()
    assert "does not cover" not in words and "safety limit" not in words
    assert body["notes"] == []  # no clamp: 21.5 °C is documented and passes the gate


def test_a_card_reports_the_grid_temperature_it_used() -> None:
    """Cards read the grid: sauerkraut's grid stops at 22.5 °C inside its 16-24 °C profile."""
    kraut = _recipe("sauerkraut_dry_salted")
    assert grid.temps(kraut.key)[-1] == 22.5
    card, _ = S.build_card(kraut, (), 30.0)
    assert card is not None
    body = S.card_json(card)
    t = body["temperature"]
    assert (t["served_c"], t["model_c"], t["source_only"]) == (23.9, 22.5, False)
    assert body["notes"] == [
        "your temperature is outside this recipe's documented range; shown at 23.9 °C",
        "aroma, taste and timings computed at 22.5 °C, the nearest precomputed temperature",
    ]


def test_a_koji_source_only_note_names_the_safe_span() -> None:
    koji = _recipe(KOJI)  # documented 27-40 °C, safe 27-35 °C, profile 28-35 °C
    card, _ = S.build_card(koji, (), 27.0)
    assert card is not None and card.temperature.source_only
    assert S.card_json(card)["window"]["notes"] == [
        "timings from the source at 27–35 °C (the model covers 28–35 °C); aroma levels are "
        "computed at 28 °C"
    ]


@pytest.mark.parametrize(
    ("key", "asked", "served", "model_c"),
    [
        ("sauerkraut_dry_salted", 30.0, 23.9, 23.9),  # grid ends at 22.5, the profile at 24
        ("wine_orleans_surface", 22.0, 22.0, 24.0),  # source-only; grid starts at 25
    ],
)
def test_the_live_forecast_runs_at_the_nearest_profile_temperature(
    monkeypatch: pytest.MonkeyPatch, key: str, asked: float, served: float, model_c: float
) -> None:
    calls: list[tuple[str, float, int]] = []

    def fake_live(recipe_key: str, temp_c: float, members: int) -> grid.Entry:
        calls.append((recipe_key, temp_c, members))
        return dataclasses.replace(grid.interp_temp(recipe_key, temp_c), temp_c=temp_c)

    monkeypatch.setattr(S, "_live", fake_live)
    body = S.forecast(key, [], [], asked)
    assert calls == [(key, model_c, S.FORECAST_MEMBERS)]
    assert (body["temperature"]["served_c"], body["temperature"]["model_c"]) == (served, model_c)
    assert body["temperature"]["source_only"] == (served != model_c)
    assert "nearest precomputed" not in " ".join(body["notes"])


# ── service: statistics, targets, links ─────────────────────────────────


def test_the_live_path_runs_recipes_through_the_shared_run_module() -> None:
    """No copy of the recipe-to-run logic in the service: a bad schedule fails in run's
    validation before anything is solved."""
    bad = dataclasses.replace(_recipe(GARUM), temp_schedule=((0.0, 20.0), (0.0, 18.0)))
    with pytest.raises(run.RecipeError, match="increasing"):
        S.live_statistics(bad, 20.0, S.FORECAST_MEMBERS)
    assert not hasattr(S, "prediction_inputs") and not hasattr(S, "_per_100g")


@pytest.mark.parametrize(("key", "temp"), [(KIMCHI, 16.0), (GARUM, 20.0)])
def test_live_statistics_reproduce_the_grid(key: str, temp: float) -> None:
    """With the grid's ensemble (members=None) and cold caches, the live path computes the
    committed entry (stored as float16)."""
    engine.clear_caches()
    live = S.live_statistics(_recipe(key), temp, None)
    stored = grid.entry(key, temp)
    assert set(live.e) == set(stored.e)
    for s in stored.e:
        for mine, kept in ((live.e, stored.e), (live.u, stored.u), (live.p, stored.p)):
            got = np.asarray(mine[s], dtype=np.float16).astype(np.float64)
            np.testing.assert_allclose(got, kept[s], rtol=0.0, atol=2.0**-10)
    assert set(live.milestones) == set(stored.milestones)
    for name, m in stored.milestones.items():
        np.testing.assert_allclose(
            [live.milestones[name].p10, live.milestones[name].p50, live.milestones[name].p90],
            [m.p10, m.p50, m.p90], rtol=1e-5,
        )  # fmt: skip


def test_targets_are_validated_and_low_resolution_series_flagged() -> None:
    assert S.LOW_RESOLUTION == {"phenolic", "vinegary", "fishy"}
    got = S.parse_targets(["fruity", "fruity"], ["sour"])
    assert [(t.key, t.kind) for t in got] == [("fruity", "aroma"), ("sour", "taste")]
    with pytest.raises(ValueError, match="at most 3"):
        S.parse_targets(["fruity", "green", "floral"], ["sour"])
    with pytest.raises(ValueError, match="unknown aroma"):
        S.parse_targets(["funky"], [])
    with pytest.raises(ValueError, match="unknown taste"):
        S.parse_targets([], ["bitter"])


def test_a_target_the_ferment_does_not_produce_is_not_modelled() -> None:
    kombucha = _recipe("green_dominant_kombucha")
    assert "fishy" not in grid.entry(kombucha.key, 25.0).e
    card, _ = S.build_card(kombucha, S.parse_targets(["fishy"], ["sour"]), None)
    assert card is not None
    fishy, sour = card.evaluation.targets
    assert (fishy.modelled, fishy.e, fishy.level) == (False, 0.0, None)
    assert sour.modelled and sour.level in {"Low", "Med", "High"}
    assert "fishy: not modelled for this ferment" in card.notes


def test_ranking_without_targets_follows_the_tie_keys() -> None:
    """§ 5.4: nothing to buy first; then institutional before peer-reviewed; then the key."""
    cards, _ = S.proven_cards(["White rice"], (), None)
    assert [c.recipe.key for c in cards] == [
        KOJI, "red_rice_miso_kagawa_long", "shiro_miso_kagawa_sweet",
    ]  # fmt: skip
    assert [c.to_buy for c in cards] == [(), ("Soybeans",), ("Soybeans",)]


def test_ranking_with_targets_is_by_e_at_the_peak() -> None:
    targets = S.parse_targets(["fruity"], ["sour"])
    cards = [
        c for r in library.active() if (c := S.build_card(r, targets, None)[0]) is not None
    ]
    best, _ = S.proven_cards([], targets, None)
    ranked = sorted(cards, key=S.rank_key)
    assert [c.recipe.key for c in best] == [c.recipe.key for c in ranked[:3]]
    es = [c.evaluation.e or 0.0 for c in ranked]
    assert es == sorted(es, reverse=True)


def test_the_planner_link_is_the_planner_s_share_format() -> None:
    style = _recipe("levain_liquide")
    link = S.planner_link(style, 26.0, 500.0)
    assert link.startswith("#/levain?p=") and "=" not in link.removeprefix("#/levain?p=")
    plan = _decode(link)
    assert list(plan) == ["style", "starter", "culture_id", "levain", "dough", "proof"]
    assert plan["style"] == "levain_liquide" and plan["culture_id"] is None
    assert plan["levain"]["temperature_c"] == 26  # whole numbers as JavaScript writes them
    assert plan["levain"]["seed_g"] == pytest.approx(142.9 / 2, abs=0.05)
    SourdoughPlanIn.model_validate(plan)
    plan_from_dict(plan)


# ── POST /recommendations ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_recommender_needs_a_session_the_library_does_not(
    anonymous: AsyncClient,
) -> None:
    body = {"recipe_key": KIMCHI}
    assert (await anonymous.post("/recommendations", json={"tastes": ["sour"]})).status_code == 401
    assert (await anonymous.post("/recommendations/forecast", json=body)).status_code == 401
    assert (await anonymous.post("/batches/from-recommendation", json=body)).status_code == 401
    assert (await anonymous.get("/recipes")).status_code == 200


@pytest.mark.asyncio
async def test_a_proven_card(client: AsyncClient) -> None:
    resp = await client.post(
        "/recommendations",
        json={"ingredients": ["Napa cabbage"], "aromas": ["pungent"], "tastes": ["sour"],
              "batch_g": 2000},
    )  # fmt: skip
    assert resp.status_code == 200
    body = resp.json()
    assert body["grid_version"] == grid.version() and body["experimental"] is None
    assert body["targets"] == [
        {"key": "pungent", "kind": "aroma", "low_resolution": False},
        {"key": "sour", "kind": "taste", "low_resolution": False},
    ]
    [card] = body["proven"]["cards"]
    assert card["id"] == f"library:{KIMCHI}" and card["section"] == "proven"
    assert card["recipe"]["batch_g"] == 2000
    grams = {i["name"]: i["grams"] for i in card["recipe"]["ingredients"]}
    assert grams["Napa cabbage"] == pytest.approx(2 * 788.5)
    assert card["recipe"]["salt_pct"] == pytest.approx(3.5, abs=0.01)
    assert card["temperature"]["served_c"] == 20 and card["temperature"]["slider"] == {
        "min_c": 17, "max_c": 23,
    }  # fmt: skip
    assert card["safety_lines"] == [gate.PH_DEADLINE_LINE, gate.PH_LOG_LINE]
    assert card["level"] in {"Low", "Med", "High"}
    for t in card["targets"]:  # Low / Med / High, never a number, before the calibration gate
        assert set(t) == {"key", "kind", "level", "modelled", "low_resolution", "top_compound"}
    assert card["targets"][0]["top_compound"]["tier"] in {"calibrated", "reported", "plausible"}
    assert card["trust"]["labels"][:2] == ["Model-guided idea", "model estimate, not validated"]
    assert card["trust"]["provenance"] == "peer_reviewed" and card["trust"]["sources"]
    assert card["window"]["basis"] == "model" and card["handoff"] is None
    assert not [s for s in _strings(body) if any(f in s.lower() for f in FORBIDDEN)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ingredients", "expected"),
    [
        (["Milk", "Salt"], {
            "milk_kefir_grains_5pct_24h", "milk_kefir_grains_10pct_extended",
            "lactic_fresh_cheese_curd",
        }),
        (["Cabbage", "Water"], {"sauerkraut_dry_salted"}),
    ],
)  # fmt: skip
async def test_listed_staples_never_exclude_a_recipe(
    client: AsyncClient, ingredients: list[str], expected: set[str]
) -> None:
    """Design § 5.2 "staples aside", Q3 "staples are always allowed"."""
    body = (await client.post("/recommendations", json={"ingredients": ingredients})).json()
    assert {c["recipe_key"] for c in body["proven"]["cards"]} == expected


def test_a_sourdough_card_hands_off_to_the_planner() -> None:
    card, _ = S.build_card(_recipe("rye_sour"), (), 26.0)
    assert card is not None
    body = S.card_json(card)
    assert body["recipe_key"] == "rye_sour" and body["handoff"] == "planner"
    assert body["safety_lines"] == []  # baking is the barrier (design § 7)
    assert body["window"]["basis"] == "planner"
    plan = _decode(body["planner_link"])
    assert plan["style"] == "rye_sour" and plan["levain"]["temperature_c"] == 26


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"aromas": ["fruity", "green", "floral"], "tastes": ["sour"]},
        {"aromas": ["funky"]},
        {"tastes": ["sour"], "temperature_c": 75},
        {"tastes": ["sour"], "mode": "wild"},
        {"tastes": ["sour"], "batch_g": 0},
    ],
)
async def test_bad_requests_are_422(client: AsyncClient, payload: dict[str, Any]) -> None:
    assert (await client.post("/recommendations", json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_mode_both_returns_both_sections(client: AsyncClient) -> None:
    body = (await client.post("/recommendations", json={"tastes": ["sour"], "mode": "both"})).json()
    assert body["mode"] == "both" and body["notes"] == []
    assert len(body["proven"]["cards"]) == S.CARDS_PER_SECTION
    experimental = body["experimental"]["cards"]
    assert 1 <= len(experimental) <= S.CARDS_PER_SECTION
    assert all(c["section"] == "experimental" and c["operators"] for c in experimental)
    parents = [c["parent"]["recipe_key"] for c in experimental]
    assert len(set(parents)) == len(parents)  # one card per parent
    assert body["targets"] == [{"key": "sour", "kind": "taste", "low_resolution": False}]
    only = (
        await client.post("/recommendations", json={"tastes": ["sour"], "mode": "experimental"})
    ).json()
    assert only["proven"] is None and only["experimental"] == body["experimental"]
    proven = (await client.post("/recommendations", json={"tastes": ["sour"]})).json()
    assert proven["experimental"] is None and proven["proven"] == body["proven"]


@pytest.mark.asyncio
async def test_no_match_says_so(client: AsyncClient) -> None:
    body = (await client.post("/recommendations", json={"ingredients": ["Milk", "Cabbage"]})).json()
    assert body["proven"] == {
        "cards": [], "message": "No proven recipe contains all of: Milk, Cabbage.",
    }  # fmt: skip


# ── POST /recommendations/forecast ──────────────────────────────────────


@pytest.mark.asyncio
async def test_the_live_forecast(client: AsyncClient) -> None:
    S._live.cache_clear()
    payload = {"recipe_key": KIMCHI, "aromas": ["sulfurous"], "tastes": ["sour"],
               "temperature_c": 22}  # fmt: skip
    resp = await client.post("/recommendations/forecast", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["members"] == S.FORECAST_MEMBERS
    assert body["temperature"]["served_c"] == 22 and body["temperature"]["model_c"] == 22
    w = body["window"]
    assert w["taste_from_h"] <= w["peak_h"] <= w["stop_by_h"]
    assert 0.0 <= body["e_peak"] <= 1.0 and body["level"] in {"Low", "Med", "High"}
    assert [t["key"] for t in body["targets"]] == ["sulfurous", "sour"]
    assert body["targets"][0]["top_compound"]["tier"] in {"calibrated", "reported", "plausible"}
    band = body["bands"][0]
    assert band["key"] == "sulfurous" and len(band["t_h"]) == len(band["e"]) == len(band["u"])
    assert body["safety_lines"] == [gate.PH_DEADLINE_LINE, gate.PH_LOG_LINE]
    again = await client.post("/recommendations/forecast", json=payload)
    assert again.content == resp.content  # a slider position asked twice answers the same


@pytest.mark.asyncio
async def test_the_forecast_hands_sourdough_to_the_planner(client: AsyncClient) -> None:
    resp = await client.post(
        "/recommendations/forecast", json={"recipe_key": "lievito_madre", "temperature_c": 40}
    )
    body = resp.json()
    assert resp.status_code == 200 and body["handoff"] == "planner" and body["members"] is None
    assert _decode(body["planner_link"])["levain"]["temperature_c"] == 30  # documented max
    assert body["notes"][0].startswith("your temperature is outside this recipe's documented")


@pytest.mark.asyncio
@pytest.mark.parametrize("draft", [False, True])
async def test_the_forecast_serves_active_recipes_only(client: AsyncClient, draft: bool) -> None:
    drafts = [r.key for r in library.load_library().values() if r.status == "draft"]
    key = drafts[0] if draft else "no_such_recipe"
    resp = await client.post("/recommendations/forecast", json={"recipe_key": key})
    assert resp.status_code == 404


# ── POST /batches/from-recommendation ───────────────────────────────────


@pytest.mark.asyncio
async def test_start_batch_books_the_card(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    resp = await client.post(
        "/batches/from-recommendation",
        json={"recipe_key": KIMCHI, "aromas": ["pungent"], "tastes": ["sour"],
              "temperature_c": 22, "batch_g": 500},
    )  # fmt: skip
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["culture"]["type"] == "lacto_ferment"
    assert body["culture"]["name"] == _recipe(KIMCHI).name
    assert body["batch"]["expected_temperature_c"] == 22
    assert body["skipped_ingredients"] == ["Salted shrimp", "Glutinous rice paste"]
    rows = (
        await db_session.execute(
            select(Ingredient.name, BatchIngredient.quantity, BatchIngredient.role)
            .join(Ingredient, BatchIngredient.ingredient_id == Ingredient.id)
            .where(BatchIngredient.batch_id == uuid.UUID(body["batch"]["id"]))
        )
    ).all()
    booked = {n: (q, r) for n, q, r in rows}
    assert booked["Napa cabbage"] == (pytest.approx(394.2, abs=0.05), "base")
    assert booked["Water"][1] == "base"  # liquid is booked as base, the batch vocabulary
    assert set(booked) == {
        i.name for i in _recipe(KIMCHI).ingredients if i.name in library.CATALOGUE_NAMES
    }
    [ph] = [r for r in body["reminders"] if r["action"] == PH_REMINDER]
    assert ph["urgency"] == "critical"
    due, started = (
        datetime.fromisoformat(x).replace(tzinfo=None)
        for x in (ph["due_at"], body["batch"]["started_at"])
    )
    assert due - started == timedelta(hours=48)
    link = body["link"]
    assert link["source_kind"] == "library" and link["recipe_key"] == KIMCHI
    assert link["mode"] == "proven" and link["operators"] == [] and link["temperature_c"] == 22
    assert link["grid_version"] == grid.version() and link["temp_schedule"] is None
    assert set(link["window"]) == {"taste_from_h", "peak_h", "stop_by_h", "basis", "notes"}
    assert [(t["key"], t["kind"]) for t in link["targets"]] == [
        ("pungent", "aroma"), ("sour", "taste"),
    ]  # fmt: skip
    assert all(0.0 <= t["e"] <= 1.0 and 0.0 <= t["u"] <= 1.0 for t in link["targets"])
    stored = await db_session.get(RecommendationLink, uuid.UUID(link["batch_id"]))
    assert stored is not None and stored.window == link["window"]


@pytest.mark.asyncio
async def test_start_batch_for_a_staged_salt_barrier_recipe(
    client: AsyncClient, catalogue: None
) -> None:
    resp = await client.post("/batches/from-recommendation", json={"recipe_key": GARUM})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["batch"]["expected_temperature_c"] == 20  # the first stage
    assert body["link"]["temp_schedule"] == [[0, 20], [48, 18]]  # the source's stages
    assert body["link"]["temperature_c"] == 18  # served: the source's median, below the model
    assert all(r["action"] != PH_REMINDER for r in body["reminders"])  # salt, not acidity


@pytest.mark.asyncio
async def test_start_batch_never_books_certified_koji_above_35_c(
    client: AsyncClient, catalogue: None
) -> None:
    """Clamped, not refused: the card the user saw at 40 °C said "shown at 35 °C"."""
    resp = await client.post(
        "/batches/from-recommendation", json={"recipe_key": KOJI, "temperature_c": 40}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["batch"]["expected_temperature_c"] == 35
    assert body["link"]["temperature_c"] == 35
    cards = (
        await client.post("/recommendations", json={"ingredients": ["White rice"],
                                                    "temperature_c": 40})
    ).json()["proven"]["cards"]  # fmt: skip
    [koji] = [c for c in cards if c["recipe_key"] == KOJI]
    assert koji["temperature"]["served_c"] == 35 and koji["recipe"]["temperature_c"] == 35
    assert koji["temperature"]["slider"] == {"min_c": 27, "max_c": 35}
    assert koji["notes"][0] == "40 °C is above the safety limit for this recipe; shown at 35 °C"


@pytest.mark.asyncio
async def test_start_batch_books_a_source_only_recipe_at_its_source_temperature(
    client: AsyncClient, catalogue: None
) -> None:
    """Q26: lactic cheese sets at 21-22 °C; that is booked, not the model's 28 °C."""
    resp = await client.post(
        "/batches/from-recommendation", json={"recipe_key": "lactic_fresh_cheese_curd"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["batch"]["expected_temperature_c"] == 21.5
    assert body["link"]["temperature_c"] == 21.5
    assert body["link"]["window"]["basis"] == "source"


@pytest.mark.asyncio
async def test_start_batch_sends_sourdough_to_the_planner(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    resp = await client.post("/batches/from-recommendation", json={"recipe_key": "home_starter"})
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["handoff"] == "planner"
    assert _decode(detail["planner_link"])["style"] == "home_starter"
    assert (await db_session.execute(select(func.count()).select_from(Batch))).scalar() == 0


@pytest.mark.asyncio
async def test_start_batch_uses_only_an_owned_culture_of_the_type(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    theirs = Culture(name="theirs", type="koji", owner_id="someone-else")
    db_session.add(theirs)
    await db_session.commit()
    payload: dict[str, Any] = {"recipe_key": KOJI, "culture_id": str(theirs.id)}
    assert (await client.post("/batches/from-recommendation", json=payload)).status_code == 404
    kefir = (await client.post("/cultures", json={"name": "grains", "type": "kefir"})).json()
    payload["culture_id"] = kefir["id"]
    assert (await client.post("/batches/from-recommendation", json=payload)).status_code == 422
    mine = (await client.post("/cultures", json={"name": "my koji", "type": "koji"})).json()
    payload["culture_id"] = mine["id"]
    resp = await client.post("/batches/from-recommendation", json=payload)
    assert resp.status_code == 201
    assert resp.json()["culture"]["id"] == mine["id"]
    assert all(r["action"] != PH_REMINDER for r in resp.json()["reminders"])  # koji: no pH line


@pytest.mark.asyncio
async def test_start_batch_writes_nothing_when_the_catalogue_is_missing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.post("/batches/from-recommendation", json={"recipe_key": KIMCHI})
    assert resp.status_code == 503
    for model in (Culture, Batch, RecommendationLink, Reminder):
        count = await db_session.execute(select(func.count()).select_from(model))
        assert count.scalar() == 0, model.__name__


@pytest.mark.asyncio
async def test_deleting_the_account_deletes_its_links(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    resp = await client.post("/batches/from-recommendation", json={"recipe_key": KOJI})
    assert resp.status_code == 201
    assert (await client.delete("/me")).status_code == 204
    count = await db_session.execute(select(func.count()).select_from(RecommendationLink))
    assert count.scalar() == 0


@pytest.mark.asyncio
async def test_a_stage_change_leaves_the_ph_reminder_open(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    """The pH check is a safety reminder: advance_stage supersedes stage timers only; the
    user closes it explicitly."""
    body = (await client.post("/batches/from-recommendation", json={"recipe_key": KIMCHI})).json()
    [ph] = [r for r in body["reminders"] if r["action"] == PH_REMINDER]
    stage_timers = [r["id"] for r in body["reminders"] if r["action"] != PH_REMINDER]
    assert stage_timers  # kimchi's first stage has a timer, so the test means something
    batch_id = body["batch"]["id"]

    async def open_ids() -> set[str]:
        rows = await db_session.execute(
            select(Reminder.id).where(
                Reminder.batch_id == uuid.UUID(batch_id), Reminder.completed_at.is_(None)
            )
        )
        return {str(i) for i in rows.scalars()}

    assert (await client.patch(f"/batches/{batch_id}/stage", json={})).status_code == 200
    still_open = await open_ids()
    assert ph["id"] in still_open and not set(stage_timers) & still_open
    stored = await db_session.get(Reminder, uuid.UUID(ph["id"]))
    assert stored is not None and stored.kind == SAFETY_REMINDER
    assert (await client.patch(f"/reminders/{ph['id']}/done")).status_code == 200
    assert ph["id"] not in await open_ids()


@pytest.mark.asyncio
async def test_a_staged_batch_forecasts_on_its_schedule(
    client: AsyncClient, catalogue: None
) -> None:
    """Sand lance: the batch keeps the first stage as its expected temperature and its forecast
    runs on the stored schedule (B2's planned_temperature)."""
    body = (await client.post("/batches/from-recommendation", json={"recipe_key": GARUM})).json()
    resp = await client.get(f"/batches/{body['batch']['id']}/prediction")
    assert resp.status_code == 200, resp.text
    forecast = resp.json()
    assert forecast["temperature"]["source"] == "expected"
    assert "Temperature: your plan: 20 °C from the start, then 18 °C from hour 48." in forecast[
        "assumptions"
    ]


@pytest.mark.asyncio
async def test_a_library_recipe_the_engine_cannot_run_is_a_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(recipe: library.Recipe, temp_c: float) -> None:
        raise run.RecipeError("temp_schedule ((0, 20), (0, 18)): start hours must be increasing")

    S._live.cache_clear()
    monkeypatch.setattr(run, "prediction_inputs", broken)
    resp = await client.post("/recommendations/forecast", json={"recipe_key": GARUM})
    assert resp.status_code == 500
    assert resp.json()["detail"].startswith("This library recipe cannot be run: temp_schedule")


# ── Experimental (B7): variants, screening, own batch ───────────────────


def _labels(card: dict[str, Any]) -> list[str]:
    return list(card["trust"]["labels"])


def _by_parent(body: dict[str, Any]) -> dict[str | None, dict[str, Any]]:
    return {c["parent"]["recipe_key"]: c for c in body["experimental"]["cards"]}


def _fake_live(calls: list[tuple[str, float, int]]) -> Any:
    """A stand-in for a live forecast (seconds each): sauerkraut's grid statistics at that
    temperature on the requested time axis."""

    def fake(
        recipe: library.Recipe, model_c: float, members: int, t_dst: Any, end_h: float
    ) -> tuple[grid.Entry, str, bool]:
        calls.append((recipe.key, model_c, members))
        src = grid.interp_temp(KRAUT, model_c)

        def on(m: Any) -> Any:
            return type(src.e)({s: np.interp(t_dst, src.t_h, v) for s, v in m.items()})

        entry = dataclasses.replace(
            src, recipe_key=recipe.key, temp_c=model_c, t_h=np.asarray(t_dst), e=on(src.e),
            u=on(src.u), p=on(src.p), members=members,
        )  # fmt: skip
        names = "|".join(sorted(i.name for i in recipe.ingredients))  # like the engine's: content
        return entry, f"fake:{names}:{model_c}", True

    return fake


async def _own_batch(
    db: AsyncSession,
    ferment_type: str,
    rows: list[tuple[str, float]],
    *,
    owner: str = TEST_USER_ID,
    temp_c: float = 20.0,
    hours: float | None = None,
    culture: Culture | None = None,
    started: datetime | None = None,
) -> Batch:
    if culture is None:
        culture = Culture(name=f"my {ferment_type}", type=ferment_type, owner_id=owner)
        db.add(culture)
        await db.flush()
    start = started or datetime(2026, 9, 1, 12, 0)
    batch = Batch(
        culture_id=culture.id, started_at=start, current_stage="ferment", stage_entered_at=start,
        expected_temperature_c=temp_c, outcome="in_progress" if hours is None else "success",
        ended_at=None if hours is None else start + timedelta(hours=hours),
    )  # fmt: skip
    db.add(batch)
    await db.flush()
    by_name = {i.name: i for i in (await db.execute(select(Ingredient))).scalars()}
    for name, grams in rows:
        ingredient = by_name[name]
        db.add(BatchIngredient(
            batch_id=batch.id, ingredient_id=ingredient.id, quantity=grams, unit="g",
            role=ingredient.default_role,
        ))  # fmt: skip
    await db.commit()
    return batch


def test_an_experimental_card_adds_a_t3_flavouring_and_keeps_the_salt() -> None:
    body = S.recommend(["Fresh ginger"], [], [], "experimental")
    RecommendationsOut.model_validate(body)
    assert body["proven"] is None
    card = _by_parent(body)[KRAUT]
    kraut = _recipe(KRAUT)
    assert card["id"] == f"variant:{KRAUT}:add:Fresh ginger"
    assert (card["section"], card["source_kind"], card["recipe_key"]) == (
        "experimental", "variant", KRAUT,
    )  # fmt: skip
    assert card["parent"] == {
        "kind": "library", "recipe_key": KRAUT, "batch_id": None, "community_recipe_id": None,
        "name": kraut.name, "label": kraut.name,
    }  # fmt: skip
    assert card["operators"] == [{
        "op": "add", "key": "add:Fresh ginger", "ingredient": "Fresh ginger", "replaces": None,
        "share": 0.0078, "from_c": None, "to_c": None, "fdc_id": None, "label": None,
    }]  # fmt: skip
    assert card["screened"] is False and card["interaction_detected"] is None
    grams = {i["name"]: i["grams"] for i in card["recipe"]["ingredients"]}
    assert grams["Fresh ginger"] == pytest.approx(7.8) and grams["Salt"] == 21.1
    proven = S.card_json(S.build_card(kraut, (), None)[0])  # type: ignore[arg-type]
    assert card["recipe"]["salt_pct"] == proven["recipe"]["salt_pct"]
    assert _labels(card)[:3] == [*S.CARD_LABELS, f"Experimental — departs from {kraut.name}"]
    assert card["safety_lines"] == [gate.PH_DEADLINE_LINE, gate.PH_LOG_LINE]
    assert card["to_buy"] == ["Cabbage"]
    assert kraut.duration_h is not None
    assert card["window"]["taste_from_h"] >= kraut.duration_h.lo
    assert card["window"]["stop_by_h"] <= 1.5 * kraut.duration_h.hi


def test_a_must_include_ingredient_missing_from_a_parent_is_added_by_operator_v() -> None:
    body = S.recommend(["Garlic", "Cabbage"], ["sulfurous"], [], "both")
    for card in body["experimental"]["cards"]:  # every variant holds both
        names = {i["name"] for i in card["recipe"]["ingredients"]}
        assert {"Garlic", "Cabbage"} <= names, card["id"]
    card = _by_parent(body)[KRAUT]
    [garlic] = [o for o in card["operators"] if o["op"] == "usda"]
    assert garlic | {"key": None} == {
        "op": "usda", "key": None, "ingredient": "Garlic", "replaces": None, "share": 0.05,
        "from_c": None, "to_c": None, "fdc_id": None, "label": "aroma effect unknown",
    }  # fmt: skip
    assert card["screened"] and S.SCREENED in _labels(card)
    assert operators.AROMA_UNKNOWN in _labels(card) and S.SCREENED_NOTE in card["notes"]
    row = next(i for i in card["recipe"]["ingredients"] if i["name"] == "Garlic")
    assert row["label"] == operators.AROMA_UNKNOWN and row["grams"] == 50


def test_variants_rank_by_u_minus_the_penalty_one_per_parent() -> None:
    targets = S.parse_targets(["fruity"], ["sour"])
    cards = S.experimental_cards([], targets, None)
    assert len(cards) == S.CARDS_PER_SECTION
    keys = [S.experimental_rank_key(c) for c in cards]
    assert keys == sorted(keys)
    assert len({c.variant.parent.recipe.key for c in cards if c.variant}) == len(cards)
    for card, key in zip(cards, keys, strict=True):
        ev = card.evaluation
        assert ev.u is not None and -key[0] == pytest.approx(ev.u - ev.penalty)
        assert card.variant is not None and 1 <= len(card.variant.operators) <= 3


def test_the_off_note_penalty_is_relative_to_the_parent() -> None:
    kimchi = _recipe(KIMCHI)
    temp = S.resolve_temperature(kimchi, None)
    stats = grid.interp_temp(KIMCHI, temp.served_c)
    targets = S.parse_targets(["fruity"], [])

    def penalty(ref: S.Reference) -> S.Evaluation:
        return S.evaluate(kimchi, stats, temp, targets, mode="experimental", reference=ref)

    assert penalty(S.Reference(frozenset(), stats.p)).penalty == 0.0  # the parent itself
    clean = S.Reference(frozenset(), {s: np.zeros_like(v) for s, v in stats.p.items()})
    ev = penalty(clean)
    offs = sorted(score.OFF_NOTES & set(stats.p))
    want = score.LAMBDA * sum(float(np.interp(ev.peak_h, stats.t_h, stats.p[o])) for o in offs)
    assert ev.penalty == pytest.approx(want) and ev.penalty > 0
    assert set(ev.rising) <= set(offs) and ev.rising
    assert penalty(S.Reference(frozenset(score.OFF_NOTES), clean.p)).penalty == 0.0  # character
    assert S.evaluate(kimchi, stats, temp, targets).penalty == 0.0  # Proven has none


def test_the_experimental_window_may_run_to_one_and_a_half_d_hi() -> None:
    kraut = _recipe(KRAUT)
    temp = S.resolve_temperature(kraut, None)
    stats = grid.interp_temp(KRAUT, temp.served_c)
    targets = S.parse_targets([], ["sour"])
    proven = S.evaluate(kraut, stats, temp, targets).window
    variant = S.evaluate(
        kraut, stats, temp, targets, mode="experimental", reference=S.library_reference(kraut, None)
    ).window
    assert kraut.duration_h is not None and proven is not None and variant is not None
    d = kraut.duration_h
    assert proven.stop_by_h <= d.hi < variant.stop_by_h <= 1.5 * d.hi
    assert variant.taste_from_h >= d.lo


def test_a_temperature_variant_is_served_at_its_temperature_without_a_slider() -> None:
    parent = S.library_parent("lactic_fresh_cheese_curd")  # 21-22 °C, profile 28-32 °C
    ops = {op.key: op for op in operators.grid_operators(parent.recipe)}
    v = S.make_variant(parent, [ops["temp:28"]])
    card, _ = S.variant_card(v, (), None, 1000.0, (), S.library_reference(parent.recipe, None))
    assert card is not None
    body = S.card_json(card)
    t = body["temperature"]
    assert (t["served_c"], t["slider"], t["source_only"], t["model_c"]) == (28, None, False, 28)
    assert body["recipe"]["temperature_c"] == 28 and body["window"]["basis"] == "model"
    assert body["operators"][0] | {"key": None} == {
        "op": "temperature", "key": None, "ingredient": None, "replaces": None, "share": None,
        "from_c": 21.5, "to_c": 28, "fdc_id": None, "label": None,
    }  # fmt: skip
    assert library.OUTSIDE_RANGE_LABEL not in _labels(body)  # served inside the model's range


def test_a_card_s_temperature_label_follows_its_served_temperature() -> None:
    """Carried from B5: the label "source temperature outside the model's range" only when
    the card is served outside it."""
    kombucha = _recipe("black_tea_kombucha_1f")  # documented 27-33 °C, profile 20-28 °C
    at_median, _ = S.build_card(kombucha, (), None)
    slid, _ = S.build_card(kombucha, (), 27.5)
    assert at_median is not None and slid is not None
    assert library.OUTSIDE_RANGE_LABEL in _labels(S.card_json(at_median))
    labels = _labels(S.card_json(slid))
    assert library.OUTSIDE_RANGE_LABEL not in labels and library.PARTLY_OUTSIDE_LABEL in labels


@pytest.mark.asyncio
async def test_usda_picks_need_experimental_mode_and_a_known_food(client: AsyncClient) -> None:
    ask = {"aromas": ["fruity"], "usda_fdc_ids": [PERSIMMON]}
    assert (await client.post("/recommendations", json=ask)).status_code == 422  # proven
    unknown = ask | {"mode": "experimental", "usda_fdc_ids": [1]}
    assert (await client.post("/recommendations", json=unknown)).status_code == 422
    resp = await client.post("/recommendations", json=ask | {"mode": "experimental"})
    assert resp.status_code == 200
    combos = S._combos(S.library_parent(KRAUT), [], None, [PERSIMMON])
    assert any(op.key == f"usda:fdc:{PERSIMMON}" for c in combos for op in c)


# ── your own batch as a parent (Q16) ────────────────────────────────────


@pytest.mark.asyncio
async def test_someone_else_s_batch_is_404(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    theirs = await _own_batch(
        db_session, "lacto_ferment", [("Cabbage", 979.0), ("Salt", 21.0)], owner="someone-else"
    )
    pid = str(theirs.id)
    temp = [{"op": "temperature", "to_c": 16}]
    ask = {"tastes": ["sour"], "mode": "experimental", "parent_batch_id": pid}
    assert (await client.post("/recommendations", json=ask)).status_code == 404
    forecast = {"parent_batch_id": pid, "operators": temp}
    assert (await client.post("/recommendations/forecast", json=forecast)).status_code == 404
    start = {"parent_batch_id": pid, "operators": temp}
    assert (await client.post("/batches/from-recommendation", json=start)).status_code == 404
    assert (await client.post("/recommendations", json=ask | {"mode": "proven"})).status_code == 422


@pytest.mark.asyncio
async def test_variants_of_your_batch_run_live_and_lead_the_section(
    client: AsyncClient, db_session: AsyncSession, catalogue: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, float, int]] = []
    monkeypatch.setattr(S, "live_variant_statistics", _fake_live(calls))
    rows = [("Cabbage", 979.0), ("Salt", 21.0)]
    first = await _own_batch(db_session, "lacto_ferment", rows)
    culture = await db_session.get(Culture, first.culture_id)
    mine = await _own_batch(
        db_session, "lacto_ferment", rows, culture=culture, started=datetime(2026, 9, 5)
    )
    ask = {"tastes": ["sour"], "mode": "experimental", "parent_batch_id": str(mine.id)}
    resp = await client.post("/recommendations", json=ask)
    assert resp.status_code == 200, resp.text
    cards = resp.json()["experimental"]["cards"]
    own, *library_cards = cards
    assert own["source_kind"] == "own_batch" and own["recipe_key"] is None
    assert own["parent"] | {"name": None} == {
        "kind": "own_batch", "recipe_key": None, "batch_id": str(mine.id),
        "community_recipe_id": None, "name": None, "label": "your batch #2",
    }  # fmt: skip
    assert own["id"].startswith(f"own_batch:{mine.id}:")
    assert "Experimental — departs from your batch #2" in _labels(own)
    assert not own["screened"] and own["safety_lines"] == [gate.PH_DEADLINE_LINE, gate.PH_LOG_LINE]
    assert 2 <= len(calls) <= 1 + S.OWN_BATCH_VARIANTS  # the batch itself, then its variants
    assert {m for _, _, m in calls} == {S.FORECAST_MEMBERS}
    assert all(c["source_kind"] == "variant" for c in library_cards) and len(cards) <= 3
    assert "no end time yet: timings typical of lacto_ferment recipes in the library" in own[
        "notes"
    ]


@pytest.mark.asyncio
async def test_a_sourdough_batch_is_not_a_parent(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    starter = await _own_batch(
        db_session, "sourdough", [("White wheat flour", 500.0), ("Water", 500.0)]
    )
    ask = {"mode": "experimental", "parent_batch_id": str(starter.id)}
    resp = await client.post("/recommendations", json=ask)
    assert resp.status_code == 422 and "levain planner" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_an_own_batch_candidate_record_identifies_no_one(
    client: AsyncClient, db_session: AsyncSession, catalogue: None,
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:  # fmt: skip
    """Review round 1: the candidates log holds no batch or owner id and no culture name."""
    log = tmp_path / "candidates.jsonl"
    monkeypatch.setattr(settings, "candidates_path", str(log))
    monkeypatch.setattr(S, "live_variant_statistics", _fake_live([]))
    mine = await _own_batch(db_session, "lacto_ferment", [("Cabbage", 979.0), ("Salt", 21.0)])
    culture = await db_session.get(Culture, mine.culture_id)
    assert culture is not None
    ask = {"tastes": ["sour"], "mode": "experimental", "parent_batch_id": str(mine.id)}
    assert (await client.post("/recommendations", json=ask)).status_code == 200
    forecast = {"parent_batch_id": str(mine.id), "operators": [{"op": "temperature", "to_c": 16}]}
    assert (await client.post("/recommendations/forecast", json=forecast)).status_code == 200
    text = log.read_text(encoding="utf-8")
    records = [json.loads(line) for line in text.splitlines()]
    assert records and all(r["parent"] == "own_batch" for r in records)
    assert all(r["parent_kind"] == "own_batch" and r["grid_version"] is None for r in records)
    for secret in (str(mine.id), mine.id.hex, str(culture.id), culture.name, TEST_USER_ID):
        assert secret not in text, secret
    # the real fingerprint hashes the engine's inputs, which carry no key, id or name
    parent = await _own_parent(db_session, mine.id, TEST_USER_ID)
    inputs = json.dumps(dataclasses.asdict(run.prediction_inputs(parent.recipe, 20.0)), default=str)
    for secret in (str(mine.id), culture.name, TEST_USER_ID):
        assert secret not in inputs, secret


@pytest.mark.asyncio
async def test_a_retired_ingredient_leaves_your_batch_s_salt_unknown(
    client: AsyncClient, db_session: AsyncSession, catalogue: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """Review round 1: Cabbage 500 g + Fruit (retired) 480 g + Salt 15 g is 1.5 % salt. Left
    out, the rest would read 15 / 515 = 2.9 % and pass SALT-001; kept without a mass, like a
    row with an unknown unit, the salt is unknown and the gate fails closed."""
    calls: list[tuple[str, float, int]] = []
    monkeypatch.setattr(S, "live_variant_statistics", _fake_live(calls))
    db_session.add(Ingredient(
        name="Fruit", default_role="flavoring", fermentation_systems=["kombucha", "kefir"],
        is_active=False,
    ))  # fmt: skip
    await db_session.commit()
    mine = await _own_batch(
        db_session, "lacto_ferment", [("Cabbage", 500.0), ("Fruit", 480.0), ("Salt", 15.0)]
    )
    parent = await _own_parent(db_session, mine.id, TEST_USER_ID)
    fruit = next(i for i in parent.recipe.ingredients if i.name == "Fruit")
    assert fruit.g_per_kg is None
    assert gate.salt_pct(gate.from_recipe(parent.recipe)) is None
    refused = S.check_gate(parent.recipe, S.resolve_temperature(parent.recipe, None))
    assert not refused.ok and any("salt % unknown" in r for r in refused.reasons)
    assert "Fruit" in parent.recipe.notes  # named on the card
    pid = str(mine.id)
    ask = {"tastes": ["sour"], "mode": "experimental", "parent_batch_id": pid}
    body = (await client.post("/recommendations", json=ask)).json()
    assert all(c["source_kind"] != "own_batch" for c in body["experimental"]["cards"])
    assert calls == []  # nothing ran: no variant passed the gate
    temp = {"parent_batch_id": pid, "operators": [{"op": "temperature", "to_c": 16}]}
    assert (await client.post("/recommendations/forecast", json=temp)).status_code == 422
    assert (await client.post("/batches/from-recommendation", json=temp)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "staple"),
    [("black_tea_kombucha_1f", "Salt"), (KIMCHI, "Cane sugar"), (KIMCHI, "Starter/levain")],
)
async def test_a_staple_is_never_a_usda_food(
    client: AsyncClient, catalogue: None, key: str, staple: str
) -> None:
    """Review round 1: on every route (the catalogue, the forecast, Start batch)."""
    recipe = _recipe(key)
    assert library.ingredient_tier(staple, recipe.fermentation_type) in (0, 1)  # (v)'s tiers
    assert staple not in {op.ingredient for op in operators.singles(recipe, must_include=[staple])}
    assert any("staple" in why for why in operators.bounds_reasons(
        recipe, [operators.Operator("usda", staple, share=operators.USDA_SHARE)]
    ))  # fmt: skip
    payload = {"recipe_key": key, "operators": [{"op": "usda", "ingredient": staple}]}
    assert (await client.post("/recommendations/forecast", json=payload)).status_code == 422
    assert (await client.post("/batches/from-recommendation", json=payload)).status_code == 422
    body = S.recommend([staple], [], ["sour"], "experimental")
    assert all(o["ingredient"] != staple or o["op"] != "usda"
               for c in body["experimental"]["cards"] for o in c["operators"])  # fmt: skip


@pytest.mark.asyncio
async def test_a_sourdough_variant_hand_off_is_gated(
    client: AsyncClient, catalogue: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review round 1: the planner link of a variant goes through variant_gate too."""
    monkeypatch.setattr(gate, "LACTIC_MAX_C", 20.0)  # rye sour is documented at 25-30 °C
    swap = [{"op": "swap", "ingredient": "White wheat flour", "replaces": "Rye flour"}]
    resp = await client.post(
        "/batches/from-recommendation", json={"recipe_key": "rye_sour", "operators": swap}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_a_variant_of_your_batch_runs_through_the_engine(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    """The real path, end to end: a finished kefir batch (22 °C, 30 h) as a parent; its one
    variant here moves it to 18 °C, outside its own ±3 °C span and inside the profile."""
    kefir = await _own_batch(
        db_session, "kefir", [("Milk", 950.0), ("Kefir grains", 50.0)], temp_c=22.0, hours=30.0
    )
    ask = {"tastes": ["sour"], "mode": "experimental", "parent_batch_id": str(kefir.id)}
    resp = await client.post("/recommendations", json=ask)
    assert resp.status_code == 200, resp.text
    card = resp.json()["experimental"]["cards"][0]
    assert card["id"] == f"own_batch:{kefir.id}:temp:18"
    t = card["temperature"]
    assert (t["served_c"], t["slider"], t["source_only"]) == (18, None, False)
    assert card["safety_lines"] == [gate.PH_DEADLINE_LINE, gate.PH_LOG_LINE]
    assert card["window"]["taste_from_h"] >= 0.7 * 30.0 - 0.05  # d_lo of the widened 30 h


# ── the variant's live forecast: confirmation (design §§ 8.5, 10.1) ─────


def _kraut_pair() -> list[S.OperatorRequest]:
    return [
        S.OperatorRequest("add", "Fresh ginger"),
        S.OperatorRequest("swap", "Napa cabbage", "Cabbage"),
    ]


@pytest.mark.parametrize("confirmed", ["low", "screened"])
def test_interaction_detected_below_0_8_times_the_screened_e(
    monkeypatch: pytest.MonkeyPatch, confirmed: str
) -> None:
    parent = S.library_parent(KRAUT)
    v = S.make_variant(parent, S.resolve_operators(parent, _kraut_pair()))
    screened = S.screened_statistics(v, S.variant_temperature(v, None))

    def live(*_: Any) -> tuple[grid.Entry, str, bool]:
        if confirmed == "screened":
            return screened, "fp", False
        zero = type(screened.e)({s: np.zeros_like(x) for s, x in screened.e.items()})
        return dataclasses.replace(screened, e=zero, u=zero), "fp", False

    monkeypatch.setattr(S, "live_variant_statistics", live)
    body = S.forecast(KRAUT, ["pungent"], ["sour"], None, ops=_kraut_pair())
    assert body["screened"] and body["screened_e_peak"] is not None
    assert body["interaction_detected"] is (confirmed == "low")
    assert (S.INTERACTION in " ".join(body["notes"])) is (confirmed == "low")


@pytest.mark.asyncio
async def test_a_screened_variant_is_confirmed_live_cached_and_logged(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "candidates.jsonl"
    monkeypatch.setattr(settings, "candidates_path", str(log))
    S._LIVE.clear()
    ops = [
        {"op": "add", "ingredient": "Fresh ginger", "share": 0.5, "key": "ignored"},
        {"op": "swap", "ingredient": "Napa cabbage", "replaces": "Cabbage"},
    ]
    payload = {"recipe_key": KRAUT, "operators": ops, "aromas": ["pungent"], "tastes": ["sour"]}
    resp = await client.post("/recommendations/forecast", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["source_kind"], body["screened"], body["members"]) == ("variant", True, 64)
    keys = [o["key"] for o in body["operators"]]
    assert keys == ["add:Fresh ginger", "swap:Cabbage>Napa cabbage"]
    assert body["operators"][0]["share"] == 0.0078  # the server's share, not the client's
    assert body["screened_e_peak"] is not None and isinstance(body["interaction_detected"], bool)
    if abs(body["e_peak"] - 0.8 * body["screened_e_peak"]) > 0.005:  # clear of the rounding
        assert body["interaction_detected"] is (body["e_peak"] < 0.8 * body["screened_e_peak"])
    [line] = log.read_text(encoding="utf-8").splitlines()
    record = json.loads(line)
    assert record["kind"] == "variant" and record["parent"] == KRAUT
    assert record["operators"] == ["add:Fresh ginger", "swap:Cabbage>Napa cabbage"]
    assert record["members"] == 64 and record["model_version"] == engine.MODEL_VERSION
    assert {"pungent", "sour"} <= set(record["series"])
    again = await client.post("/recommendations/forecast", json=payload)
    assert again.content == resp.content  # kept by fingerprint
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1  # logged once


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"recipe_key": KRAUT, "operators": [{"op": "add", "ingredient": "Dill"}]},  # no use level
        {"recipe_key": KRAUT, "operators": [{"op": "temperature", "to_c": 22}]},  # documented
        {"recipe_key": "lactic_fresh_cheese_curd",
         "operators": [{"op": "usda", "ingredient": "Garlic"}]},  # cheese: not (v)
        {"recipe_key": "rye_sour", "operators": [{"op": "add", "ingredient": "Fresh ginger"}]},
        {"recipe_key": KRAUT, "operators": [{"op": "temperature", "to_c": 16}] * 4},  # > 3
        {"recipe_key": KRAUT, "operators": [{"op": "temperature", "to_c": 16},
                                            {"op": "temperature", "to_c": 24}]},  # two moves
        {"operators": [{"op": "temperature", "to_c": 16}]},  # no parent
        {"recipe_key": KRAUT, "operators": [{"op": "swap", "ingredient": "Dill"}]},  # incomplete
    ],
)  # fmt: skip
async def test_operators_a_recipe_does_not_allow_are_422(
    client: AsyncClient, payload: dict[str, Any]
) -> None:
    assert (await client.post("/recommendations/forecast", json=payload)).status_code == 422


@pytest.mark.asyncio
async def test_a_sourdough_variant_starts_in_the_planner_with_its_flour(
    client: AsyncClient, catalogue: None
) -> None:
    swap = [{"op": "swap", "ingredient": "White wheat flour", "replaces": "Rye flour"}]
    resp = await client.post(
        "/batches/from-recommendation", json={"recipe_key": "rye_sour", "operators": swap}
    )
    assert resp.status_code == 409
    assert _decode(resp.json()["detail"]["planner_link"])["levain"]["flour"] == {"t65": 1}
    forecast = (
        await client.post("/recommendations/forecast",
                          json={"recipe_key": "rye_sour", "operators": swap})
    ).json()  # fmt: skip
    assert forecast["handoff"] == "planner" and forecast["source_kind"] == "variant"
    assert _decode(forecast["planner_link"])["levain"]["flour"] == {"t65": 1}


# ── Start batch for a variant ───────────────────────────────────────────


async def _booked(db: AsyncSession, batch_id: str) -> dict[str, tuple[float, str, int | None]]:
    columns = (Ingredient.name, BatchIngredient.quantity, BatchIngredient.role, Ingredient.fdc_id)
    rows = (
        await db.execute(
            select(*columns)
            .join(Ingredient, BatchIngredient.ingredient_id == Ingredient.id)
            .where(BatchIngredient.batch_id == uuid.UUID(batch_id))
        )
    ).all()  # fmt: skip
    return {n: (q, r, f) for n, q, r, f in rows}


@pytest.mark.asyncio
async def test_start_batch_books_a_variant(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    ops = [{"op": "add", "ingredient": "Fresh ginger", "share": 0.5},
           {"op": "temperature", "to_c": 16}]  # fmt: skip
    resp = await client.post(
        "/batches/from-recommendation",
        json={"recipe_key": KRAUT, "operators": ops, "tastes": ["sour"], "mode": "experimental",
              "batch_g": 2000},
    )  # fmt: skip
    assert resp.status_code == 201, resp.text
    body = resp.json()
    link = body["link"]
    assert (link["source_kind"], link["recipe_key"], link["mode"]) == (
        "variant", KRAUT, "experimental",
    )  # fmt: skip
    assert [o["key"] for o in link["operators"]] == ["add:Fresh ginger", "temp:16"]
    assert link["temperature_c"] == 16 and body["batch"]["expected_temperature_c"] == 16
    assert body["culture"]["name"] == f"{_recipe(KRAUT).name} (variant)"
    booked = await _booked(db_session, body["batch"]["id"])
    assert booked["Fresh ginger"][:2] == (pytest.approx(15.6), "flavoring")  # 0.0078 × 2000 g
    assert booked["Salt"][0] == pytest.approx(42.2)  # the parent's 21.1 g/kg: salt kept
    assert sum(q for q, _, _ in booked.values()) == pytest.approx(2000.0, abs=0.2)
    assert any(r["action"] == PH_REMINDER for r in body["reminders"])
    stored = await db_session.get(RecommendationLink, uuid.UUID(link["batch_id"]))
    assert stored is not None and stored.operators == link["operators"]


@pytest.mark.asyncio
async def test_start_batch_books_a_usda_food_like_a_usda_pick(
    client: AsyncClient, db_session: AsyncSession, catalogue: None
) -> None:
    db_session.add(FdcFood(
        fdc_id=PERSIMMON, data_type="SR Legacy", description="Persimmons, japanese, raw",
        category="Fruits and Fruit Juices",
        nutrients=[FdcFoodNutrient(nutrient="water", amount_per_100g=80.32)],
    ))  # fmt: skip
    await db_session.commit()
    usda = [{"op": "usda", "fdc_id": PERSIMMON, "label": "aroma effect unknown"}]
    resp = await client.post(
        "/batches/from-recommendation", json={"recipe_key": KRAUT, "operators": usda}
    )
    assert resp.status_code == 201, resp.text
    booked = await _booked(db_session, resp.json()["batch"]["id"])
    assert booked["Persimmons, japanese, raw"] == (pytest.approx(50.0), "flavoring", PERSIMMON)
    assert resp.json()["link"]["operators"][0]["fdc_id"] == PERSIMMON


@pytest.mark.asyncio
async def test_start_batch_from_a_variant_of_your_batch(
    client: AsyncClient, db_session: AsyncSession, catalogue: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(S, "live_variant_statistics", _fake_live([]))
    mine = await _own_batch(db_session, "lacto_ferment", [("Cabbage", 979.0), ("Salt", 21.0)])
    payload = {"parent_batch_id": str(mine.id), "operators": [{"op": "temperature", "to_c": 16}],
               "mode": "experimental"}  # fmt: skip
    resp = await client.post("/batches/from-recommendation", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["link"]["source_kind"] == "own_batch"
    assert (body["link"]["recipe_key"], body["link"]["parent_batch_id"]) == (None, str(mine.id))
    assert body["link"]["community_recipe_id"] is None
    assert body["batch"]["expected_temperature_c"] == 16
    booked = await _booked(db_session, body["batch"]["id"])
    assert {n: q for n, (q, _, _) in booked.items()} == {"Cabbage": 979.0, "Salt": 21.0}
    assert body["batch"]["id"] != str(mine.id)
    no_ops = {"parent_batch_id": str(mine.id), "operators": []}
    assert (await client.post("/batches/from-recommendation", json=no_ops)).status_code == 422
