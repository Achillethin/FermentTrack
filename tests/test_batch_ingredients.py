"""POST/GET /batches/{id}/ingredients — recipe logging with role pre-fill."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Ingredient


async def _create_culture_and_batch(client: AsyncClient) -> tuple[str, str]:
    resp = await client.post("/cultures", json={"name": "Jun SCOBY", "type": "kombucha"})
    culture_id = resp.json()["id"]
    resp = await client.post("/batches", json={"culture_id": culture_id})
    return culture_id, resp.json()["id"]


@pytest.mark.asyncio
async def test_add_batch_ingredient_prefills_role_from_ingredient_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ingredient = Ingredient(name="Cane sugar", default_role="base", fermentation_systems=["kombucha"])
    db_session.add(ingredient)
    await db_session.commit()
    await db_session.refresh(ingredient)

    _culture_id, batch_id = await _create_culture_and_batch(client)

    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": str(ingredient.id), "quantity": 200.0, "unit": "g"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "base"
    assert body["quantity"] == 200.0
    assert body["unit"] == "g"


@pytest.mark.asyncio
async def test_add_batch_ingredient_role_override_persists(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ingredient = Ingredient(name="Cane sugar", default_role="base", fermentation_systems=["kombucha"])
    db_session.add(ingredient)
    await db_session.commit()
    await db_session.refresh(ingredient)

    _culture_id, batch_id = await _create_culture_and_batch(client)

    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": str(ingredient.id), "role": "flavoring"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "flavoring"

    # Later edits to Ingredient.default_role must not retroactively change
    # this batch's already-recorded role.
    ingredient.default_role = "starter"
    await db_session.commit()

    resp = await client.get(f"/batches/{batch_id}/ingredients")
    assert resp.json()[0]["role"] == "flavoring"


@pytest.mark.asyncio
async def test_add_batch_ingredient_wrong_substrate_400s(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ingredient = Ingredient(name="Rennet", default_role="starter", fermentation_systems=["cheese"])
    db_session.add(ingredient)
    await db_session.commit()
    await db_session.refresh(ingredient)

    # kombucha batch, cheese-only ingredient — not the same taxonomy.
    _culture_id, batch_id = await _create_culture_and_batch(client)

    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": str(ingredient.id)},
    )
    assert resp.status_code == 400
    assert "Rennet" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_add_batch_ingredient_unknown_ingredient_404s(client: AsyncClient) -> None:
    _culture_id, batch_id = await _create_culture_and_batch(client)
    resp = await client.post(
        f"/batches/{batch_id}/ingredients",
        json={"ingredient_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_batch_ingredients_unknown_batch_404s(client: AsyncClient) -> None:
    resp = await client.get("/batches/00000000-0000-0000-0000-000000000000/ingredients")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_batch_ingredients_empty_recipe(client: AsyncClient) -> None:
    _culture_id, batch_id = await _create_culture_and_batch(client)
    resp = await client.get(f"/batches/{batch_id}/ingredients")
    assert resp.status_code == 200
    assert resp.json() == []
