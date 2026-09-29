"""POST /batches/{id}/repeat — start the next batch from an existing one's recipe."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.auth import get_current_user_id
from fermenttrack.main import app
from fermenttrack.models import Batch, BatchIngredient, BatchOrganism, Ingredient, Organism, Reminder
from tests.conftest import TEST_USER_ID

UNKNOWN = "00000000-0000-0000-0000-000000000000"
FIRST = "brew_sweet_tea"  # kombucha's first stage


async def _source(client: AsyncClient) -> dict:
    culture = (await client.post("/cultures", json={"name": "Jun", "type": "kombucha"})).json()
    resp = await client.post(
        "/batches",
        json={"culture_id": culture["id"], "target": "tart", "expected_temperature_c": 24.5},
    )
    return resp.json()


async def _add_recipe(client: AsyncClient, db: AsyncSession, batch_id: str) -> list[str]:
    """Two ingredients (different roles/units) + one custom organism on the batch."""
    sugar = Ingredient(name="Cane sugar", default_role="base", fermentation_systems=["kombucha"])
    tea = Ingredient(name="Black tea", default_role="flavoring", fermentation_systems=["kombucha"])
    yeast = Organism(name="Brettanomyces", kingdom="yeast", source_version="v1")
    db.add_all([sugar, tea, yeast])
    await db.commit()
    for ing, qty, unit, role in [(sugar, 200.0, "g", "base"), (tea, None, None, "additive")]:
        body = {"ingredient_id": str(ing.id), "role": role}
        if qty is not None:
            body |= {"quantity": qty, "unit": unit}
        assert (await client.post(f"/batches/{batch_id}/ingredients", json=body)).status_code == 201
    resp = await client.post(
        f"/batches/{batch_id}/organisms", json={"organism_id": str(yeast.id), "notes": "wild"}
    )
    assert resp.status_code == 201
    return [str(sugar.id), str(tea.id)]


async def _open_reminders(db: AsyncSession, batch_id: str) -> list[Reminder]:
    res = await db.execute(
        select(Reminder).where(Reminder.batch_id == uuid.UUID(batch_id), Reminder.completed_at.is_(None))
    )
    return list(res.scalars().all())


async def _count_batches(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(Batch))).scalar_one()


@pytest.mark.asyncio
async def test_repeat_clones_recipe_and_starts_fresh(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    src = await _source(client)
    ingredient_ids = await _add_recipe(client, db_session, src["id"])

    resp = await client.post(f"/batches/{src['id']}/repeat")
    assert resp.status_code == 201
    new = resp.json()

    assert new["id"] != src["id"]
    assert new["culture_id"] == src["culture_id"]
    assert new["target"] == "tart"
    assert new["expected_temperature_c"] == 24.5
    assert new["current_stage"] == FIRST
    assert new["stage_entered_at"] == new["started_at"]
    assert new["outcome"] == "in_progress"
    assert new["ended_at"] is None
    started = datetime.fromisoformat(new["started_at"])
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    assert abs(datetime.now(timezone.utc) - started) < timedelta(seconds=30)

    old_rows = (await client.get(f"/batches/{src['id']}/ingredients")).json()
    new_rows = (await client.get(f"/batches/{new['id']}/ingredients")).json()
    assert len(new_rows) == 2
    key = lambda r: r["ingredient_id"]  # noqa: E731
    for o, n in zip(sorted(old_rows, key=key), sorted(new_rows, key=key), strict=True):
        assert n["id"] != o["id"]
        assert {k: n[k] for k in ("ingredient_id", "quantity", "unit", "role")} == {
            k: o[k] for k in ("ingredient_id", "quantity", "unit", "role")
        }
    assert {r["ingredient_id"] for r in new_rows} == set(ingredient_ids)

    orgs = (
        await db_session.execute(select(BatchOrganism).where(BatchOrganism.batch_id == uuid.UUID(new["id"])))
    ).scalars().all()
    assert [(o.source, o.notes) for o in orgs] == [("custom", "wild")]

    reminders = await _open_reminders(db_session, new["id"])
    assert len(reminders) == 1
    assert reminders[0].action  # first-stage reminder, same as create_batch


@pytest.mark.asyncio
async def test_repeat_leaves_source_untouched(client: AsyncClient, db_session: AsyncSession) -> None:
    src = await _source(client)
    await _add_recipe(client, db_session, src["id"])
    await client.post(f"/batches/{src['id']}/measure", json={"type": "pH", "value_numeric": 3.2})
    await client.post(f"/batches/{src['id']}/note", json={"text": "smells good"})
    await client.patch(f"/batches/{src['id']}/stage", json={"stage": "1F"})
    before = (await client.get(f"/batches/{src['id']}/timeline")).json()
    reminders_before = {r.id for r in await _open_reminders(db_session, src["id"])}

    new = (await client.post(f"/batches/{src['id']}/repeat")).json()

    after = (await client.get(f"/batches/{src['id']}/timeline")).json()
    assert after == before
    assert after["batch"]["current_stage"] == "1F"
    assert len(after["events"]) == 2
    assert {r.id for r in await _open_reminders(db_session, src["id"])} == reminders_before
    assert len((await client.get(f"/batches/{src['id']}/ingredients")).json()) == 2
    # nothing of the source's history leaks into the new batch
    assert (await client.get(f"/batches/{new['id']}/timeline")).json()["events"] == []


@pytest.mark.asyncio
async def test_repeat_of_finished_batch_restarts_at_first_stage(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    src = await _source(client)
    done = (await client.patch(f"/batches/{src['id']}/stage", json={"stage": "ready"})).json()
    assert done["outcome"] == "success" and done["ended_at"] is not None

    new = (await client.post(f"/batches/{src['id']}/repeat")).json()
    assert new["current_stage"] == FIRST
    assert new["outcome"] == "in_progress"
    assert new["ended_at"] is None
    assert len(await _open_reminders(db_session, new["id"])) == 1


@pytest.mark.asyncio
async def test_repeat_without_ingredients_or_organisms(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    src = await _source(client)
    resp = await client.post(f"/batches/{src['id']}/repeat")
    assert resp.status_code == 201
    new_id = resp.json()["id"]
    assert (await client.get(f"/batches/{new_id}/ingredients")).json() == []
    n = (
        await db_session.execute(
            select(func.count())
            .select_from(BatchIngredient)
            .where(BatchIngredient.batch_id == uuid.UUID(new_id))
        )
    ).scalar_one()
    assert n == 0


@pytest.mark.asyncio
async def test_repeat_of_repeat(client: AsyncClient, db_session: AsyncSession) -> None:
    src = await _source(client)
    await _add_recipe(client, db_session, src["id"])
    second = (await client.post(f"/batches/{src['id']}/repeat")).json()
    third = await client.post(f"/batches/{second['id']}/repeat")
    assert third.status_code == 201
    assert len((await client.get(f"/batches/{third.json()['id']}/ingredients")).json()) == 2
    assert len({src["id"], second["id"], third.json()["id"]}) == 3


@pytest.mark.asyncio
async def test_repeat_is_owner_scoped(client: AsyncClient, db_session: AsyncSession) -> None:
    src = await _source(client)
    await _add_recipe(client, db_session, src["id"])
    count = await _count_batches(db_session)

    app.dependency_overrides[get_current_user_id] = lambda: "someone-else"
    try:
        resp = await client.post(f"/batches/{src['id']}/repeat")
    finally:
        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Batch not found"
    assert await _count_batches(db_session) == count


@pytest.mark.asyncio
async def test_repeat_unknown_batch_404(client: AsyncClient, db_session: AsyncSession) -> None:
    resp = await client.post(f"/batches/{UNKNOWN}/repeat")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Batch not found"
    assert await _count_batches(db_session) == 0
