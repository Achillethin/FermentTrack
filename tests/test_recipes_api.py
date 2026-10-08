"""GET /recipes and GET /recipes/{key}: the public, read-only recipe library (design Q17)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from fermenttrack.main import app


@pytest_asyncio.fixture
async def anon() -> AsyncIterator[AsyncClient]:
    """A client with no token and no auth override, as an anonymous visitor."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def test_library_needs_no_auth(anon: AsyncClient) -> None:
    assert (await anon.get("/batches")).status_code == 401  # this client is anonymous
    resp = await anon.get("/recipes")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 20 and {r["status"] for r in body} == {"active"}


async def test_filters_by_type_and_status(anon: AsyncClient) -> None:
    kombucha = (await anon.get("/recipes", params={"type": "kombucha"})).json()
    assert {r["key"] for r in kombucha} == {"black_tea_kombucha_1f", "green_dominant_kombucha"}
    drafts = (await anon.get("/recipes", params={"status": "draft"})).json()
    assert {r["key"] for r in drafts} == {
        "dill_cucumber_pickles_brined", "carrot_sticks_wet_brined", "barley_koji_single_grain",
        "budu_traditional_anchovy_fish_sauce",
    }  # fmt: skip
    assert (await anon.get("/recipes", params={"type": "no_such_type"})).json() == []
    assert (await anon.get("/recipes", params={"status": "excluded"})).status_code == 422


async def test_recipe_carries_envelope_provenance_sources_labels_and_scope(
    anon: AsyncClient,
) -> None:
    resp = await anon.get("/recipes/pacific_sand_lance_rice_koji_fish_sauce")
    assert resp.status_code == 200
    r = resp.json()
    assert r["provenance"] == "peer_reviewed" and r["sources"] == ["Jung-koji-fish-sauce-2022"]
    env = r["envelope"]
    assert env["temp_c"] == {"median": 18, "lo": 18, "hi": 20}
    assert env["duration_h"] == {"median": 7200, "lo": 5040, "hi": 9360}
    assert env["salt_pct"] == {"median": 12, "lo": 8.3, "hi": 15.4}
    assert env["temp_schedule"] == [[0, 20], [48, 18]]
    assert env["basis"] == "widened_single_value"
    assert r["model_scope"] == ["temp_outside_profile", "beyond_horizon"]
    assert r["labels"][0] == "single-value source, widened"
    assert r["labels"][-1] == "aroma estimate covers the first 180 days only"
    assert r["handoff"] is None and r["planner_style"] is None
    fish = next(i for i in r["ingredients"] if i["name"] == "Anchovies")
    assert fish["label"] == "stand-in species: recipe uses Pacific sand lance"
    assert fish["g_per_kg"] == {"median": 800, "lo": 769.2, "hi": 833.3}
    assert fish["required"] == "core" and fish["role"] == "base"
    assert sum(i["g_per_kg"]["median"] for i in r["ingredients"]) == pytest.approx(1000)


async def test_sourdough_recipe_hands_off_to_the_planner(anon: AsyncClient) -> None:
    r = (await anon.get("/recipes/home_starter")).json()
    assert r["handoff"] == "planner" and r["planner_style"] == "home_starter"
    assert r["envelope"]["duration_h"] is None


async def test_draft_recipe_detail_is_library_data_marked_draft(anon: AsyncClient) -> None:
    resp = await anon.get("/recipes/budu_traditional_anchovy_fish_sauce")
    assert resp.status_code == 200
    r = resp.json()
    assert r["status"] == "draft" and r["envelope"]["temp_c"] is None


async def test_unknown_or_excluded_recipe_is_404(anon: AsyncClient) -> None:
    assert (await anon.get("/recipes/poolish")).status_code == 404
    assert (await anon.get("/recipes/green_tea_kombucha_variant")).status_code == 404
