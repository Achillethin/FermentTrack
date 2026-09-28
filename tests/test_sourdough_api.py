"""/sourdough planner endpoints and sourdough batches with a plan."""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Culture, Organism

LEVAIN = {"seed_g": 20, "flour_g": 100, "water_g": 100, "flour": {"t65": 1}, "temperature_c": 26}
PLAN = {
    "style": "levain_liquide",
    "levain": LEVAIN,
    "dough": {"flour_g": 900, "water_g": 630, "salt_g": 20, "flour": {"t65": 0.9, "t150": 0.1},
              "temperature_c": 25},
    "proof": {"temperature_c": 4, "hours": 12},
}  # fmt: skip


async def test_catalog_lists_styles_and_flours(client: AsyncClient) -> None:
    body = (await client.get("/sourdough/catalog")).json()
    keys = {s["key"] for s in body["styles"]}
    assert {"home_starter", "levain_liquide", "levain_dur", "rye_sour", "type_ii"} <= keys
    t65 = next(f for f in body["flours"] if f["key"] == "t65")
    assert t65["us_name"] == "Bread flour" and t65["ash_pct"] == 0.65


async def test_plan_forecast_has_phases_rise_and_acidity(client: AsyncClient) -> None:
    resp = await client.post("/sourdough/plan", json=PLAN)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [p["key"] for p in body["phases"]] == ["levain", "bulk", "proof"]
    groups = {s["key"]: s["group"] for s in body["series"]}
    assert groups["rise"] == "rise" and groups["tta"] == "acidity" and groups["fq"] == "acidity"
    ms = {m["key"] for m in body["milestones"]}
    assert {"levain_peak", "levain_doubled", "bulk_target"} <= ms
    assert abs(body["summary"]["salt_pct_of_flour"] - 2.0) < 0.05  # incl. the levain's flour
    assert body["status"] == "prior_only" and body["initial"]["source"] == "plan"


async def test_invalid_plans_are_422(client: AsyncClient) -> None:
    bad_flour = {**PLAN, "levain": {**LEVAIN, "flour": {"t999": 1}}}
    assert (await client.post("/sourdough/plan", json=bad_flour)).status_code == 422
    no_yeast = {"style": "type_iii", "dough": {**PLAN["dough"], "dried_sour_g": 20}}
    assert (await client.post("/sourdough/plan", json=no_yeast)).status_code == 422
    salty = {**PLAN, "dough": {**PLAN["dough"], "salt_g": 200}}
    assert (await client.post("/sourdough/plan", json=salty)).status_code == 422


async def test_feeding_chart_and_foreign_starter(client: AsyncClient, db_session: AsyncSession) -> None:
    resp = await client.post(
        "/sourdough/feeding-chart",
        json={"style": "home_starter", "temperature_c": 24, "ratios": [1, 5, 10]},
    )
    assert resp.status_code == 200, resp.text
    peaks = [r["peak_h"]["p50"] for r in resp.json()["rows"]]
    assert peaks == sorted(peaks)
    other = Culture(name="Not mine", type="sourdough", owner_id="someone-else")
    db_session.add(other)
    await db_session.commit()
    resp = await client.post("/sourdough/plan", json={**PLAN, "culture_id": str(other.id)})
    assert resp.status_code == 404


async def test_sourdough_batch_with_plan(client: AsyncClient, db_session: AsyncSession) -> None:
    for name, kingdom in (("Lactobacillus sanfranciscensis", "bacteria"),
                          ("Saccharomyces cerevisiae", "yeast"),
                          ("Kazachstania humilis", "yeast")):  # fmt: skip
        db_session.add(Organism(name=name, kingdom=kingdom, source_version="test"))
    await db_session.commit()
    c = await client.post("/cultures", json={"name": "Achille's classic levain",
                                             "type": "sourdough", "style": "levain_liquide"})  # fmt: skip
    assert c.status_code == 201 and c.json()["style"] == "levain_liquide"
    assert (await client.post("/cultures", json={"name": "x", "type": "sourdough",
                                                 "style": "nope"})).status_code == 422  # fmt: skip
    b = await client.post("/batches", json={"culture_id": c.json()["id"], "sourdough_plan": PLAN})
    assert b.status_code == 201, b.text
    batch = b.json()
    assert batch["sourdough_plan"]["style"] == "levain_liquide"

    # the style's organisms are the batch's defaults (no K. humilis in a levain liquide)
    bio = (await client.get(f"/batches/{batch['id']}/biochemistry")).json()
    names = {o["name"] for o in bio["organisms"]}
    assert names == {"Lactobacillus sanfranciscensis", "Saccharomyces cerevisiae"}

    await client.post(f"/batches/{batch['id']}/measure", json={"type": "rise", "value_numeric": 20})
    adv = await client.patch(f"/batches/{batch['id']}/stage", json={"stage": "bulk_ferment"})
    assert adv.status_code == 200
    timeline = (await client.get(f"/batches/{batch['id']}/timeline")).json()["events"]
    assert any(e["kind"] == "stage_change" and e["detail"]["value_text"] == "bulk_ferment"
               for e in timeline)  # fmt: skip

    pred = await client.get(f"/batches/{batch['id']}/prediction")
    assert pred.status_code == 200, pred.text
    body = pred.json()
    # the mix was logged just now: the bulk starts at ~now, not at the modelled peak
    bulk = next(p for p in body["phases"] if p["key"] == "bulk")
    assert abs(bulk["start_h"] - body["now_h"]) < 0.1
    assert body["status"] == "calibrated"  # the rise reading
    # a plan on a non-sourdough culture is refused; clearing a plan works
    k = await client.post("/cultures", json={"name": "Kraut", "type": "lacto_ferment"})
    bad = await client.post("/batches", json={"culture_id": k.json()["id"], "sourdough_plan": PLAN})
    assert bad.status_code == 422
    cleared = await client.patch(f"/batches/{batch['id']}", json={"sourdough_plan": None})
    assert cleared.status_code == 200 and cleared.json()["sourdough_plan"] is None
    assert uuid.UUID(batch["id"])
