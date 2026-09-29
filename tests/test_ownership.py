"""Stage 0 auth/sharing: requests are scoped to the caller's owner_id.

conftest.py overrides get_current_user_id with a fixed TEST_USER_ID for every
test; here we swap it mid-test to simulate a second account.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from fermenttrack.auth import get_current_user_id
from fermenttrack.main import app


@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected(client: AsyncClient) -> None:
    del app.dependency_overrides[get_current_user_id]
    try:
        resp = await client.get("/cultures")
    finally:
        from tests.conftest import TEST_USER_ID

        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_users_cannot_see_each_others_cultures_or_batches(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "My SCOBY", "type": "kombucha"})
    culture = resp.json()
    resp = await client.post("/batches", json={"culture_id": culture["id"]})
    batch = resp.json()

    app.dependency_overrides[get_current_user_id] = lambda: "someone-else"
    try:
        assert (await client.get("/cultures")).json() == []
        assert (await client.get(f"/cultures/{culture['id']}")).status_code == 404
        assert (await client.get(f"/batches/{batch['id']}/timeline")).status_code == 404
        assert (await client.get("/batches")).json() == []
        # Can't create a batch under someone else's culture either.
        resp = await client.post("/batches", json={"culture_id": culture["id"]})
        assert resp.status_code == 404
    finally:
        from tests.conftest import TEST_USER_ID

        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID

    # Original owner still sees their own data.
    assert len((await client.get("/cultures")).json()) == 1
    assert (await client.get(f"/batches/{batch['id']}/timeline")).status_code == 200


@pytest.mark.asyncio
async def test_export_and_delete_my_data(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "Kraut", "type": "lacto_ferment"})
    culture = resp.json()
    await client.post("/batches", json={"culture_id": culture["id"]})

    export = await client.get("/me/export")
    assert export.status_code == 200
    body = export.json()
    assert len(body) == 1
    assert len(body[0]["batches"]) == 1

    assert (await client.delete("/me")).status_code == 204
    assert (await client.get("/me/export")).json() == []
    assert (await client.get("/cultures")).json() == []


async def test_born_from_must_be_your_own_culture(client, db_session) -> None:
    from fermenttrack.models import Culture

    theirs = Culture(name="Their starter", type="sourdough", owner_id="someone-else")
    db_session.add(theirs)
    await db_session.commit()
    resp = await client.post("/cultures", json={"name": "Mine", "type": "sourdough",
                                                "born_from": str(theirs.id)})  # fmt: skip
    assert resp.status_code == 404
    parent = await client.post("/cultures", json={"name": "Mother", "type": "sourdough"})
    child = await client.post("/cultures", json={"name": "Daughter", "type": "sourdough",
                                                 "born_from": parent.json()["id"]})  # fmt: skip
    assert child.status_code == 201
    assert (await client.delete("/me")).status_code == 204  # lineage does not block erasure
