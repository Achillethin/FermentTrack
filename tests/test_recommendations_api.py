"""The recommender's Proven API (build plan B5; design §§ 5, 6, 7, 10.1, 11): the service's
temperature, gate, window and ranking rules, POST /recommendations, the live
POST /recommendations/forecast, and Start batch (POST /batches/from-recommendation)."""

from __future__ import annotations

import base64
import dataclasses
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.main import app
from fermenttrack.models import (
    SAFETY_REMINDER,
    Batch,
    BatchIngredient,
    Culture,
    Ingredient,
    RecommendationLink,
    Reminder,
)
from fermenttrack.prediction import service as engine
from fermenttrack.prediction.sourdough import plan_from_dict
from fermenttrack.recommender import gate, grid, library, run
from fermenttrack.recommender import service as S
from fermenttrack.routers.recommendations import PH_REMINDER
from fermenttrack.schemas import SourdoughPlanIn
from fermenttrack.seed_data import (
    INGREDIENT_SEED_DATA,
    INGREDIENT_SEED_DATA_V2,
    INGREDIENT_SEED_DATA_V3,
    INGREDIENT_SEED_DATA_V4,
    RETIRED_V3,
)

KIMCHI = "napa_kimchi_room_temp"
GARUM = "pacific_sand_lance_rice_koji_fish_sauce"
KOJI = "rice_koji_steamed_rice"
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
    garum = gate.RecipeLike("garum", (gate.IngredientRow("Anchovies", "base", 1000.0),))
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
async def test_experimental_mode_serves_proven_until_b7(client: AsyncClient) -> None:
    body = (await client.post("/recommendations", json={"tastes": ["sour"], "mode": "both"})).json()
    assert body["mode"] == "both" and body["experimental"] is None
    assert len(body["proven"]["cards"]) == S.CARDS_PER_SECTION
    assert body["notes"] == [
        "Experimental ideas are not available yet: showing Proven recipes only."
    ]
    assert body["targets"] == [{"key": "sour", "kind": "taste", "low_resolution": False}]


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
