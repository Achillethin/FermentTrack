"""GET /batches/{id}/composition and the closed unit set on recipe logging."""

from __future__ import annotations

import typing
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.composition import to_grams
from fermenttrack.models import Ingredient, IngredientNutrient
from fermenttrack.schemas import Unit


def _nutrient(code: str, amount: float) -> IngredientNutrient:
    return IngredientNutrient(
        nutrient=code, amount_per_100g=amount, source="usda_fdc",
        source_food_id="0", source_version="fdc_nutrients_v1",
    )


async def _lacto_batch(client: AsyncClient) -> str:
    culture = (
        await client.post("/cultures", json={"name": "Kraut", "type": "lacto_ferment"})
    ).json()
    return (await client.post("/batches", json={"culture_id": culture["id"]})).json()["id"]


async def _ingredient(db: AsyncSession, name: str, nutrients: dict[str, float]) -> str:
    ing = Ingredient(name=name, default_role="base", fermentation_systems=["lacto_ferment"])
    ing.nutrients = [_nutrient(k, v) for k, v in nutrients.items()]
    db.add(ing)
    await db.commit()
    return str(ing.id)


def test_every_api_unit_converts_to_grams() -> None:
    for unit in typing.get_args(Unit):
        assert to_grams(1.0, unit) is not None, unit


@pytest.mark.asyncio
async def test_composition_brine(client: AsyncClient, db_session: AsyncSession) -> None:
    cabbage = await _ingredient(db_session, "Cabbage", {"sugars_total": 3.2, "sodium": 0.018})
    salt = await _ingredient(db_session, "Salt", {"sodium": 38.758})
    chilies = await _ingredient(db_session, "Chilies", {})
    batch_id = await _lacto_batch(client)
    for ing, qty, unit in [(cabbage, 1.0, "kg"), (salt, 20.0, "g"), (chilies, 30.0, "g")]:
        resp = await client.post(
            f"/batches/{batch_id}/ingredients",
            json={"ingredient_id": ing, "quantity": qty, "unit": unit},
        )
        assert resp.status_code == 201

    body = (await client.get(f"/batches/{batch_id}/composition")).json()
    assert body["total_mass_g"] == 1050.0
    assert body["mapped_mass_g"] == 1020.0
    assert body["unmapped"] == ["Chilies"]
    assert body["salt_pct"] == pytest.approx(20 / 1050 * 100)  # added salt only
    sugars = next(n for n in body["nutrients"] if n["nutrient"] == "sugars_total")
    assert sugars["grams"] == pytest.approx(32.0)
    assert sugars["missing_from"] == ["Salt"]
    assert body["salt_suggestion"] is None  # salt already logged


@pytest.mark.asyncio
async def test_salt_suggestion_before_salt_is_logged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    cabbage = await _ingredient(db_session, "Cabbage", {"sugars_total": 3.2})
    batch_id = await _lacto_batch(client)
    await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": cabbage, "quantity": 1, "unit": "kg"},
    )
    body = (await client.get(f"/batches/{batch_id}/composition")).json()
    assert body["salt_suggestion"] == {"pct": 3.0, "basis_g": 1000.0, "grams": 30.0}
    assert body["salt_pct"] is None  # suggestion is never counted as logged salt


@pytest.mark.asyncio
async def test_composition_empty_recipe(client: AsyncClient) -> None:
    batch_id = await _lacto_batch(client)
    body = (await client.get(f"/batches/{batch_id}/composition")).json()
    assert body == {
        "total_mass_g": 0.0, "mapped_mass_g": 0.0, "coverage": 0.0, "salt_pct": None,
        "salt_suggestion": None, "nutrients": [], "unmapped": [], "unquantified": [],
    }


@pytest.mark.asyncio
async def test_composition_404(client: AsyncClient) -> None:
    assert (await client.get(f"/batches/{uuid.uuid4()}/composition")).status_code == 404


@pytest.mark.asyncio
async def test_free_text_unit_rejected(client: AsyncClient, db_session: AsyncSession) -> None:
    salt = await _ingredient(db_session, "Salt", {"sodium": 38.758})
    batch_id = await _lacto_batch(client)
    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": salt, "quantity": 1, "unit": "tbsp"},
    )
    assert resp.status_code == 422
