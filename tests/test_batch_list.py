"""GET /batches — list/search batches by culture name, type and outcome."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create_culture_and_batch(client: AsyncClient, name: str, type_: str = "kombucha") -> str:
    resp = await client.post("/cultures", json={"name": name, "type": type_})
    culture_id = resp.json()["id"]
    resp = await client.post("/batches", json={"culture_id": culture_id})
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_list_batches_returns_culture_name_and_type(client: AsyncClient) -> None:
    batch_id = await _create_culture_and_batch(client, "Jun SCOBY", "kombucha")

    resp = await client.get("/batches")
    assert resp.status_code == 200
    rows = resp.json()
    assert any(r["id"] == batch_id and r["culture_name"] == "Jun SCOBY" for r in rows)
    row = next(r for r in rows if r["id"] == batch_id)
    assert row["culture_type"] == "kombucha"
    assert row["outcome"] == "in_progress"


@pytest.mark.asyncio
async def test_list_batches_filters_by_q(client: AsyncClient) -> None:
    await _create_culture_and_batch(client, "Jun SCOBY")
    await _create_culture_and_batch(client, "Sourdough Starter", "sourdough")

    resp = await client.get("/batches", params={"q": "jun"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["culture_name"] == "Jun SCOBY"


@pytest.mark.asyncio
async def test_list_batches_filters_by_type(client: AsyncClient) -> None:
    await _create_culture_and_batch(client, "Jun SCOBY", "kombucha")
    await _create_culture_and_batch(client, "Sourdough Starter", "sourdough")

    resp = await client.get("/batches", params={"type": "sourdough"})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["culture_type"] == "sourdough"


@pytest.mark.asyncio
async def test_list_batches_filters_by_outcome(client: AsyncClient) -> None:
    await _create_culture_and_batch(client, "Jun SCOBY")

    resp = await client.get("/batches", params={"outcome": "in_progress"})
    rows = resp.json()
    assert len(rows) >= 1
    assert all(r["outcome"] == "in_progress" for r in rows)

    resp = await client.get("/batches", params={"outcome": "failed"})
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_batches_empty_when_no_match(client: AsyncClient) -> None:
    await _create_culture_and_batch(client, "Jun SCOBY")
    resp = await client.get("/batches", params={"q": "nonexistent"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_batches_orders_newest_first(client: AsyncClient) -> None:
    first = await _create_culture_and_batch(client, "Older Batch")
    second = await _create_culture_and_batch(client, "Newer Batch")

    resp = await client.get("/batches")
    ids = [r["id"] for r in resp.json()]
    assert ids.index(second) < ids.index(first)
