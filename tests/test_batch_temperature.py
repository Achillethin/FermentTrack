"""Batch.expected_temperature_c: set on create, edited via PATCH /batches/{id}."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _batch(client: AsyncClient, **extra: object) -> dict:
    culture = (await client.post("/cultures", json={"name": "Jar", "type": "lacto_ferment"})).json()
    resp = await client.post("/batches", json={"culture_id": culture["id"], **extra})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_expected_temperature_defaults_to_none(client: AsyncClient) -> None:
    batch = await _batch(client)
    assert batch["expected_temperature_c"] is None


@pytest.mark.asyncio
async def test_expected_temperature_set_on_create(client: AsyncClient) -> None:
    batch = await _batch(client, expected_temperature_c=19.5)
    assert batch["expected_temperature_c"] == 19.5

    preview = (await client.get(f"/batches/{batch['id']}/preview")).json()
    assert preview["batch"]["expected_temperature_c"] == 19.5


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [-6.0, 72.0])  # 72 = a Fahrenheit room temperature
async def test_expected_temperature_out_of_range_is_rejected(
    client: AsyncClient, value: float
) -> None:
    culture = (await client.post("/cultures", json={"name": "Jar", "type": "koji"})).json()
    resp = await client.post(
        "/batches", json={"culture_id": culture["id"], "expected_temperature_c": value}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_updates_only_fields_sent(client: AsyncClient) -> None:
    batch = await _batch(client, target="sour", expected_temperature_c=20.0)

    resp = await client.patch(f"/batches/{batch['id']}", json={"expected_temperature_c": 24.0})
    assert resp.status_code == 200
    assert resp.json()["expected_temperature_c"] == 24.0
    assert resp.json()["target"] == "sour"

    resp = await client.patch(f"/batches/{batch['id']}", json={"expected_temperature_c": None})
    assert resp.json()["expected_temperature_c"] is None
    assert resp.json()["target"] == "sour"


@pytest.mark.asyncio
async def test_patch_validates_and_404s(client: AsyncClient) -> None:
    batch = await _batch(client)
    resp = await client.patch(f"/batches/{batch['id']}", json={"expected_temperature_c": 99})
    assert resp.status_code == 422

    resp = await client.patch(
        "/batches/00000000-0000-0000-0000-000000000000", json={"expected_temperature_c": 20}
    )
    assert resp.status_code == 404
