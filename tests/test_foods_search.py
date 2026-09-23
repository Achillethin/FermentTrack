"""GET /foods — search the USDA catalog."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import FdcFood


@pytest.fixture
async def catalog(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            FdcFood(
                fdc_id=1,
                data_type="SR Legacy",
                description="Cabbage, raw",
                category="Vegetables",
            ),
            FdcFood(
                fdc_id=2,
                data_type="SR Legacy",
                description="Cabbage, red, raw",
                category="Vegetables",
            ),
            FdcFood(
                fdc_id=3,
                data_type="Foundation",
                description="Cabbage, savoy, cooked, boiled",
                category=None,
            ),
            FdcFood(
                fdc_id=4,
                data_type="SR Legacy",
                description="Mangos, raw",
                category="Fruits",
            ),
            FdcFood(
                fdc_id=5,
                data_type="SR Legacy",
                description="Milk, 100% whole",
                category="Dairy",
            ),
        ]
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_all_tokens_must_match_case_insensitive(client: AsyncClient, catalog: None) -> None:
    body = (await client.get("/foods", params={"q": "RAW cabbage"})).json()
    assert [f["description"] for f in body] == ["Cabbage, raw", "Cabbage, red, raw"]
    assert body[0] == {
        "fdc_id": 1,
        "description": "Cabbage, raw",
        "data_type": "SR Legacy",
        "category": "Vegetables",
    }


@pytest.mark.asyncio
async def test_shorter_names_first_and_limit(client: AsyncClient, catalog: None) -> None:
    body = (await client.get("/foods", params={"q": "cabbage", "limit": 2})).json()
    assert [f["fdc_id"] for f in body] == [1, 2]


@pytest.mark.asyncio
async def test_like_wildcards_are_literal(client: AsyncClient, catalog: None) -> None:
    assert [f["fdc_id"] for f in (await client.get("/foods", params={"q": "100%"})).json()] == [5]
    assert (await client.get("/foods", params={"q": "c_bbage"})).json() == []


@pytest.mark.asyncio
async def test_query_validation(client: AsyncClient, catalog: None) -> None:
    assert (await client.get("/foods", params={"q": "c"})).status_code == 422
    assert (await client.get("/foods", params={"q": "cabbage", "limit": 51})).status_code == 422
    assert (await client.get("/foods", params={"q": "   "})).json() == []
    assert (await client.get("/foods", params={"q": "x" * 101})).status_code == 422


@pytest.mark.asyncio
async def test_only_first_six_tokens_are_applied(client: AsyncClient, catalog: None) -> None:
    # 7 tokens: cabbage , , , , raw zzz. Every "Cabbage..." description contains a
    # comma, so tokens 2-5 (",") and 1/6 (cabbage/raw) all match both cabbage rows.
    # The 7th token "zzz" matches nothing — if it were applied, results would be
    # empty, so a non-empty result proves it was dropped.
    body = (await client.get("/foods", params={"q": "cabbage , , , , raw zzz"})).json()
    assert [f["description"] for f in body] == ["Cabbage, raw", "Cabbage, red, raw"]
