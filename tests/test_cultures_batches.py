"""Culture/batch CRUD, stage transitions + reminder computation, measurements."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


async def _create_culture(client: AsyncClient, name: str = "Jun SCOBY #3") -> dict:
    resp = await client.post("/cultures", json={"name": name, "type": "kombucha"})
    assert resp.status_code == 201
    return resp.json()


async def _create_batch(client: AsyncClient, culture_id: str) -> dict:
    resp = await client.post("/batches", json={"culture_id": culture_id, "target": "fizzy, tart"})
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_create_and_list_cultures(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    assert culture["name"] == "Jun SCOBY #3"
    assert culture["type"] == "kombucha"
    assert culture["status"] == "active"

    resp = await client.get("/cultures")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_get_culture_with_batches(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    resp = await client.get(f"/cultures/{culture['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["batches"]) == 1
    assert body["batches"][0]["id"] == batch["id"]


@pytest.mark.asyncio
async def test_get_culture_404(client: AsyncClient) -> None:
    resp = await client.get("/cultures/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_batch_starts_at_brew_sweet_tea_with_reminder(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])
    assert batch["current_stage"] == "brew_sweet_tea"
    assert batch["outcome"] == "in_progress"

    resp = await client.get("/reminders")
    assert resp.status_code == 200
    reminders = resp.json()
    assert len(reminders) == 1
    assert reminders[0]["batch_id"] == batch["id"]
    assert reminders[0]["urgency"] == "low"


@pytest.mark.asyncio
async def test_stage_transition_advances_and_recomputes_reminder(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    resp = await client.patch(f"/batches/{batch['id']}/stage", json={})
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["current_stage"] == "1F"

    resp = await client.get("/reminders")
    reminders = resp.json()
    # 1F reminder is due in 10 days, outside the 48h window -> not listed yet.
    assert all(r["batch_id"] != batch["id"] or r["urgency"] != "low" for r in reminders)


@pytest.mark.asyncio
async def test_stage_transition_to_bottling_is_critical_urgency(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    for stage in ("1F", "2F_flavoring", "bottling"):
        resp = await client.patch(f"/batches/{batch['id']}/stage", json={"stage": stage})
        assert resp.status_code == 200

    body = resp.json()
    assert body["current_stage"] == "bottling"

    resp = await client.get("/reminders")
    reminders = [r for r in resp.json() if r["batch_id"] == batch["id"]]
    assert len(reminders) == 1
    assert reminders[0]["urgency"] == "critical"
    assert "burp bottles" in reminders[0]["action"]


@pytest.mark.asyncio
async def test_stage_transition_past_ready_fails(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    for stage in ("1F", "2F_flavoring", "bottling", "conditioning", "ready"):
        resp = await client.patch(f"/batches/{batch['id']}/stage", json={"stage": stage})
        assert resp.status_code == 200

    body = resp.json()
    assert body["current_stage"] == "ready"
    assert body["outcome"] == "success"
    assert body["ended_at"] is not None

    resp = await client.patch(f"/batches/{batch['id']}/stage", json={})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_invalid_stage_name_rejected(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    resp = await client.patch(f"/batches/{batch['id']}/stage", json={"stage": "bogus_stage"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_add_measurement(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    resp = await client.post(
        f"/batches/{batch['id']}/measure",
        json={"type": "pH", "value_numeric": 3.2, "notes": "tart"},
    )
    assert resp.status_code == 201
    measurement = resp.json()
    assert measurement["type"] == "pH"
    assert measurement["value_numeric"] == 3.2
    assert measurement["batch_id"] == batch["id"]


@pytest.mark.asyncio
async def test_add_note(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    resp = await client.post(f"/batches/{batch['id']}/note", json={"text": "smells great today"})
    assert resp.status_code == 201
    note = resp.json()
    assert note["type"] == "note"
    assert note["value_text"] == "smells great today"


@pytest.mark.asyncio
async def test_timeline_includes_measurements_and_notes(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    await client.post(f"/batches/{batch['id']}/measure", json={"type": "pH", "value_numeric": 3.5})
    await client.post(f"/batches/{batch['id']}/note", json={"text": "looking good"})

    resp = await client.get(f"/batches/{batch['id']}/timeline")
    assert resp.status_code == 200
    body = resp.json()
    assert body["batch"]["id"] == batch["id"]
    kinds = {e["kind"] for e in body["events"]}
    assert kinds == {"measurement", "note"}


@pytest.mark.asyncio
async def test_compare_batches(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch_a = await _create_batch(client, culture["id"])
    batch_b = await _create_batch(client, culture["id"])

    await client.post(f"/batches/{batch_a['id']}/measure", json={"type": "pH", "value_numeric": 3.1})
    await client.post(f"/batches/{batch_b['id']}/measure", json={"type": "pH", "value_numeric": 3.6})

    resp = await client.get(
        "/batches/compare", params={"batch_id": [batch_a["id"], batch_b["id"]]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["batches"]) == 2
    assert len(body["measurements"][batch_a["id"]]) == 1
    assert len(body["measurements"][batch_b["id"]]) == 1


@pytest.mark.asyncio
async def test_compare_requires_at_least_two(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    resp = await client.get("/batches/compare", params={"batch_id": [batch["id"]]})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_mark_reminder_done_and_snooze(client: AsyncClient) -> None:
    culture = await _create_culture(client)
    batch = await _create_batch(client, culture["id"])

    resp = await client.get("/reminders")
    reminder_id = resp.json()[0]["id"]

    resp = await client.patch(f"/reminders/{reminder_id}/done")
    assert resp.status_code == 200
    assert resp.json()["completed_at"] is not None

    # Completed reminders drop out of the upcoming list.
    resp = await client.get("/reminders")
    assert all(r["id"] != reminder_id for r in resp.json())


@pytest.mark.asyncio
async def test_sourdough_batch_uses_sourdough_stages(client: AsyncClient) -> None:
    culture = await _create_culture(client, name="My Levain")
    resp = await client.post("/cultures", json={"name": "My Levain", "type": "sourdough"})
    culture = resp.json()
    batch = await _create_batch(client, culture["id"])
    assert batch["current_stage"] == "feed_starter"

    resp = await client.patch(f"/batches/{batch['id']}/stage", json={})
    assert resp.status_code == 200
    assert resp.json()["current_stage"] == "bulk_ferment"


@pytest.mark.asyncio
async def test_kefir_batch_has_no_stage_machine(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "Water Kefir #1", "type": "kefir"})
    culture = resp.json()
    batch = await _create_batch(client, culture["id"])
    assert batch["current_stage"] == "in_progress"

    # No reminder should have been created — no expected_duration on the
    # no-machine pseudo-stage.
    resp = await client.get("/reminders")
    assert all(r["batch_id"] != batch["id"] for r in resp.json())

    # Advancing a substrate with no stage machine has nowhere to go.
    resp = await client.patch(f"/batches/{batch['id']}/stage", json={})
    assert resp.status_code == 400
