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


@pytest.mark.asyncio
async def test_search_limit_bounds_validation(client: AsyncClient) -> None:
    """limit=0 and limit=-1 should return 422 validation errors."""
    resp = await client.get("/organisms", params={"q": "test", "limit": 0})
    assert resp.status_code == 422

    resp = await client.get("/organisms", params={"q": "test", "limit": -1})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_escapes_like_wildcards(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Wildcards in query should be treated as literals, not SQL patterns."""
    db_session.add_all(
        [
            Organism(name="Saccharomyces cerevisiae", kingdom="yeast", source_version="v1"),
            Organism(name="Acetobacter aceti", kingdom="bacteria", source_version="v1"),
        ]
    )
    await db_session.commit()

    # Query with % should not match anything
    resp = await client.get("/organisms", params={"q": "%%"})
    assert resp.status_code == 200
    assert resp.json() == []

    # Query with _ should not match anything
    resp = await client.get("/organisms", params={"q": "a_"})
    assert resp.status_code == 200
    assert resp.json() == []

    # Normal query should still work
    resp = await client.get("/organisms", params={"q": "acet"})
    assert resp.status_code == 200
    names = [o["name"] for o in resp.json()]
    assert names == ["Acetobacter aceti"]


@pytest.mark.asyncio
async def test_search_orders_by_name_length(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Results should be ordered by name length (shortest first), then alphabetically."""
    db_session.add_all(
        [
            Organism(
                name="Lactococcus lactis subsp. cremoris",
                kingdom="bacteria",
                source_version="v1",
            ),
            Organism(name="Lactococcus lactis", kingdom="bacteria", source_version="v1"),
        ]
    )
    await db_session.commit()

    resp = await client.get("/organisms", params={"q": "lactococcus"})
    assert resp.status_code == 200
    names = [o["name"] for o in resp.json()]
    # Shorter name should come first
    assert names == ["Lactococcus lactis", "Lactococcus lactis subsp. cremoris"]
