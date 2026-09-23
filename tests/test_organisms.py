from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import Organism


@pytest.mark.asyncio
async def test_search_matches_case_insensitive_substring(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            Organism(name="Saccharomyces cerevisiae", kingdom="yeast", source_version="v1"),
            Organism(name="Acetobacter aceti", kingdom="bacteria", source_version="v1"),
        ]
    )
    await db_session.commit()

    resp = await client.get("/organisms", params={"q": "cerevisiae"})
    assert resp.status_code == 200
    names = [o["name"] for o in resp.json()]
    assert names == ["Saccharomyces cerevisiae"]


@pytest.mark.asyncio
async def test_search_requires_min_length(client: AsyncClient) -> None:
    resp = await client.get("/organisms", params={"q": "a"})
    assert resp.status_code == 422
