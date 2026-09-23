"""GET /ingredients — reference data listing."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Ingredient


@pytest.mark.asyncio
async def test_list_ingredients_returns_only_active(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            Ingredient(name="Black/green tea", default_role="base", fermentation_systems=["kombucha"]),
            Ingredient(
                name="Retired ingredient",
                default_role="base",
                fermentation_systems=["kombucha"],
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    resp = await client.get("/ingredients")
    assert resp.status_code == 200
    names = {i["name"] for i in resp.json()}
    assert names == {"Black/green tea"}


@pytest.mark.asyncio
async def test_list_ingredients_filters_by_substrate(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            Ingredient(name="Black/green tea", default_role="base", fermentation_systems=["kombucha"]),
            Ingredient(
                name="Salt",
                default_role="additive",
                fermentation_systems=["cheese", "lacto_ferment", "garum"],
            ),
            Ingredient(name="Rennet", default_role="starter", fermentation_systems=["cheese"]),
        ]
    )
    await db_session.commit()

    resp = await client.get("/ingredients", params={"substrate": "lacto_ferment"})
    assert resp.status_code == 200
    assert {i["name"] for i in resp.json()} == {"Salt"}


@pytest.mark.asyncio
async def test_include_retired_flag(client: AsyncClient, db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Ingredient(name="Lemon", default_role="flavoring", fermentation_systems=["kombucha"]),
            Ingredient(
                name="Fruit",
                default_role="flavoring",
                fermentation_systems=["kombucha"],
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    default = {i["name"] for i in (await client.get("/ingredients?substrate=kombucha")).json()}
    everything = {
        i["name"]
        for i in (await client.get("/ingredients?substrate=kombucha&include_retired=true")).json()
    }
    assert default == {"Lemon"}
    assert everything == {"Lemon", "Fruit"}
