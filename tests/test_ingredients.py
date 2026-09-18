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
