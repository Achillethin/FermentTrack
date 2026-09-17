"""iSpindel webhook."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ispindel_webhook_creates_measurements(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "Jun #1", "type": "kombucha"})
    culture_id = resp.json()["id"]
    resp = await client.post("/batches", json={"culture_id": culture_id})
    batch_id = resp.json()["id"]

    payload = {
        "name": "iSpindel001",
        "ID": 123456,
        "angle": 78.32,
        "temperature": 21.5,
        "temp_units": "C",
        "gravity": 1.042,
        "battery": 3.98,
        "RSSI": -65,
    }
    resp = await client.post("/webhooks/ispindel", params={"batch_id": batch_id}, json=payload)
    assert resp.status_code == 201
    measurements = resp.json()
    types = {m["type"] for m in measurements}
    assert types == {"gravity", "temperature", "battery"}

    gravity = next(m for m in measurements if m["type"] == "gravity")
    assert gravity["value_numeric"] == pytest.approx(1.042)

    resp = await client.get(f"/batches/{batch_id}/timeline")
    assert len(resp.json()["events"]) == 3


@pytest.mark.asyncio
async def test_ispindel_webhook_unknown_batch_404(client: AsyncClient) -> None:
    resp = await client.post(
        "/webhooks/ispindel",
        params={"batch_id": "00000000-0000-0000-0000-000000000000"},
        json={"gravity": 1.02},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ispindel_webhook_empty_payload_422(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "Jun #1", "type": "kombucha"})
    culture_id = resp.json()["id"]
    resp = await client.post("/batches", json={"culture_id": culture_id})
    batch_id = resp.json()["id"]

    resp = await client.post("/webhooks/ispindel", params={"batch_id": batch_id}, json={})
    assert resp.status_code == 422
