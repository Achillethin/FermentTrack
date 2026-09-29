"""Admin read access across accounts (routers/admin.py, _get_batch(admin_read=)): an
allow-listed admin reads every logbook and any bake; nobody, admin included, writes to
another account's data."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.config import settings
from fermenttrack.models import Batch, Culture, Measurement
from tests.conftest import TEST_USER_ID


async def _someone_elses_batch(db: AsyncSession) -> Batch:
    culture = Culture(name="Aymard rye mother", type="sourdough", owner_id="aymard")
    db.add(culture)
    await db.flush()
    now = datetime.now(UTC)
    batch = Batch(culture_id=culture.id, started_at=now, current_stage="feed_starter",
                  stage_entered_at=now)  # fmt: skip
    db.add(batch)
    await db.flush()
    db.add(Measurement(batch_id=batch.id, measured_at=now, type="rise", value_numeric=40))
    await db.commit()
    return batch


@pytest.fixture
def as_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", f"someone, {TEST_USER_ID}")


async def test_whoami_and_non_admins_are_kept_out(client: AsyncClient, db_session: AsyncSession) -> None:
    me = (await client.get("/me")).json()
    assert me == {"user_id": TEST_USER_ID, "admin": False}
    batch = await _someone_elses_batch(db_session)
    assert (await client.get("/admin/log")).status_code == 403
    assert (await client.get("/admin/cultures")).status_code == 403
    assert (await client.get(f"/batches/{batch.id}/preview")).status_code == 404


async def test_admin_reads_everything_writes_nothing(
    client: AsyncClient, db_session: AsyncSession, as_admin: None
) -> None:
    assert (await client.get("/me")).json()["admin"] is True
    batch = await _someone_elses_batch(db_session)
    own = await client.post("/cultures", json={"name": "Mine", "type": "sourdough"})
    await client.post("/batches", json={"culture_id": own.json()["id"]})

    log = (await client.get("/admin/log")).json()
    owners = {e["owner"] for e in log}
    assert {"aymard", TEST_USER_ID} <= owners
    assert any(e["culture"]["name"] == "Aymard rye mother" for e in log)
    assert all(e["owner"] is None for e in (await client.get("/me/log")).json())  # own log unlabelled
    cultures = (await client.get("/admin/cultures")).json()
    assert {c["owner_id"] for c in cultures} == {"aymard", TEST_USER_ID}

    preview = await client.get(f"/batches/{batch.id}/preview")
    assert preview.status_code == 200 and preview.json()["read_only"] is True
    for path in ("timeline", "ingredients", "composition", "biochemistry", "safety", "prediction"):
        assert (await client.get(f"/batches/{batch.id}/{path}")).status_code == 200, path

    # read-only: every write to someone else's bake is refused as if it did not exist
    assert (await client.post(f"/batches/{batch.id}/measure",
                              json={"type": "pH", "value_numeric": 4})).status_code == 404  # fmt: skip
    assert (await client.patch(f"/batches/{batch.id}/stage", json={})).status_code == 404
    assert (await client.patch(f"/batches/{batch.id}", json={"target": "x"})).status_code == 404
    assert (await client.post(f"/batches/{batch.id}/repeat")).status_code == 404
