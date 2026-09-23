"""POST /batches/{id}/ingredients with fdc_id — promote a USDA catalog food to an Ingredient."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import FdcFood, FdcFoodNutrient, Ingredient

MANGO = 9001


async def _batch(client: AsyncClient, ferment: str) -> str:
    culture = (
        await client.post("/cultures", json={"name": f"{ferment} c", "type": ferment})
    ).json()
    return (await client.post("/batches", json={"culture_id": culture["id"]})).json()["id"]


@pytest.fixture
async def mango(db_session: AsyncSession) -> None:
    db_session.add(
        FdcFood(
            fdc_id=MANGO, data_type="SR Legacy", description="Mangos, raw", category="Fruits",
            nutrients=[
                FdcFoodNutrient(nutrient="sugars_total", amount_per_100g=13.66),
                FdcFoodNutrient(nutrient="water", amount_per_100g=83.46),
            ],
        )
    )
    await db_session.commit()


async def _mango_ingredients(db: AsyncSession) -> list[Ingredient]:
    db.expire_all()
    return list((await db.execute(select(Ingredient).where(Ingredient.fdc_id == MANGO))).scalars())


@pytest.mark.asyncio
async def test_first_pick_creates_tagged_ingredient_with_nutrients(
    client: AsyncClient, db_session: AsyncSession, mango: None
) -> None:
    batch_id = await _batch(client, "kombucha")
    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"fdc_id": MANGO, "quantity": 200, "unit": "g", "role": "flavoring"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "flavoring"

    [ing] = await _mango_ingredients(db_session)
    assert (ing.name, ing.default_role, ing.fermentation_systems) == (
        "Mangos, raw",
        "flavoring",
        ["kombucha"],
    )

    quick_picks = (await client.get("/ingredients", params={"substrate": "kombucha"})).json()
    assert "Mangos, raw" in {i["name"] for i in quick_picks}

    comp = (await client.get(f"/batches/{batch_id}/composition")).json()
    sugars = next(n for n in comp["nutrients"] if n["nutrient"] == "sugars_total")
    assert sugars["grams"] == pytest.approx(27.32)


@pytest.mark.asyncio
async def test_second_pick_reuses_and_tags_new_ferment(
    client: AsyncClient, db_session: AsyncSession, mango: None
) -> None:
    kombucha_batch = await _batch(client, "kombucha")
    kefir_batch = await _batch(client, "kefir")
    await client.post(f"/batches/{kombucha_batch}/ingredients", json={"fdc_id": MANGO})
    resp = await client.post(f"/batches/{kefir_batch}/ingredients", json={"fdc_id": MANGO})
    assert resp.status_code == 201
    assert resp.json()["role"] == "base"  # default when no role given

    [ing] = await _mango_ingredients(db_session)
    assert ing.fermentation_systems == ["kombucha", "kefir"]


@pytest.mark.asyncio
async def test_pick_reuses_backfilled_curated_ingredient(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cabbage = Ingredient(
        name="Cabbage", default_role="base", fermentation_systems=["lacto_ferment"], fdc_id=169975
    )
    db_session.add_all(
        [cabbage, FdcFood(fdc_id=169975, data_type="SR Legacy", description="Cabbage, raw")]
    )
    await db_session.commit()

    batch_id = await _batch(client, "lacto_ferment")
    resp = await client.post(
        f"/batches/{batch_id}/ingredients", json={"fdc_id": 169975, "quantity": 1, "unit": "kg"}
    )
    assert resp.status_code == 201
    assert resp.json()["ingredient_id"] == str(cabbage.id)


@pytest.mark.asyncio
async def test_unknown_fdc_id_404_and_id_validation(client: AsyncClient, mango: None) -> None:
    batch_id = await _batch(client, "kombucha")
    url = f"/batches/{batch_id}/ingredients"
    assert (await client.post(url, json={"fdc_id": 424242})).status_code == 404
    assert (await client.post(url, json={})).status_code == 422
    both = {"fdc_id": MANGO, "ingredient_id": "00000000-0000-0000-0000-000000000000"}
    assert (await client.post(url, json=both)).status_code == 422
