"""GET /batches/{id}/preview — aggregate batch/recipe/timeline/safety payload.

No compound/microbial data in this endpoint by design — see
docs/superpowers/specs/2026-09-18-experiment-logging-design.md § 2.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Ingredient


@pytest.mark.asyncio
async def test_preview_unknown_batch_404s(client: AsyncClient) -> None:
    resp = await client.get("/batches/00000000-0000-0000-0000-000000000000/preview")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preview_empty_batch_has_no_recipe_or_events(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "Jun SCOBY", "type": "kombucha"})
    culture = resp.json()
    resp = await client.post("/batches", json={"culture_id": culture["id"], "target": "tart"})
    batch = resp.json()

    resp = await client.get(f"/batches/{batch['id']}/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["batch"]["id"] == batch["id"]
    assert body["culture"]["id"] == culture["id"]
    assert body["recipe"] == []
    assert body["timeline"] == []
    assert body["days_in_stage"] == pytest.approx(0.0, abs=0.01)
    assert "safety" in body
    assert "hard_stops" in body["safety"]


@pytest.mark.asyncio
async def test_preview_includes_recipe_and_timeline_and_safety(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ingredient = Ingredient(name="Cane sugar", default_role="base", fermentation_systems=["kombucha"])
    db_session.add(ingredient)
    await db_session.commit()
    await db_session.refresh(ingredient)

    resp = await client.post("/cultures", json={"name": "Jun SCOBY", "type": "kombucha"})
    culture = resp.json()
    resp = await client.post("/batches", json={"culture_id": culture["id"]})
    batch = resp.json()

    await client.post(
        f"/batches/{batch['id']}/ingredients",
        json={"ingredient_id": str(ingredient.id), "quantity": 100.0, "unit": "g"},
    )
    await client.post(f"/batches/{batch['id']}/measure", json={"type": "pH", "value_numeric": 3.2})
    await client.post(f"/batches/{batch['id']}/note", json={"text": "smells great"})

    resp = await client.get(f"/batches/{batch['id']}/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recipe"]) == 1
    assert body["recipe"][0]["role"] == "base"
    kinds = {e["kind"] for e in body["timeline"]}
    assert kinds == {"measurement", "note"}
    assert body["safety"]["rules_evaluated"] > 0


@pytest.mark.asyncio
async def test_preview_safety_matches_dedicated_safety_endpoint(client: AsyncClient) -> None:
    """The preview's safety block must be the exact same evaluation as
    GET /batches/{id}/safety, not a second, possibly-diverging computation."""
    resp = await client.post("/cultures", json={"name": "Sauerkraut #1", "type": "lacto_ferment"})
    culture = resp.json()
    resp = await client.post("/batches", json={"culture_id": culture["id"]})
    batch = resp.json()
    await client.post(f"/batches/{batch['id']}/measure", json={"type": "salt_pct", "value_numeric": 1.5})
    await client.post(f"/batches/{batch['id']}/measure", json={"type": "temperature", "value_numeric": 25.0})

    preview_resp = await client.get(f"/batches/{batch['id']}/preview")
    safety_resp = await client.get(f"/batches/{batch['id']}/safety")

    assert preview_resp.json()["safety"] == safety_resp.json()
