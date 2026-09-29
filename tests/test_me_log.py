"""GET /me/log: flat, newest-first logbook across the caller's batches."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.auth import get_current_user_id
from fermenttrack.main import app
from fermenttrack.models import Batch, Culture, Measurement
from tests.conftest import TEST_USER_ID

T0 = datetime(2026, 1, 1, 12, 0, 0)  # naive: SQLite drops tzinfo


async def _seed(
    db: AsyncSession, owner: str = TEST_USER_ID, name: str = "Jar", type_: str = "kombucha"
) -> tuple[Culture, Batch]:
    c = Culture(name=name, type=type_, owner_id=owner)
    db.add(c)
    await db.flush()
    b = Batch(culture_id=c.id, current_stage="F1", started_at=T0, stage_entered_at=T0)
    db.add(b)
    await db.flush()
    return c, b


def _m(b: Batch, minutes: int, type_: str = "ph", **kw) -> Measurement:
    return Measurement(batch_id=b.id, measured_at=T0 + timedelta(minutes=minutes), type=type_, **kw)


@pytest.mark.asyncio
async def test_empty_account(client: AsyncClient) -> None:
    resp = await client.get("/me/log")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_unauthenticated(client: AsyncClient) -> None:
    del app.dependency_overrides[get_current_user_id]
    try:
        resp = await client.get("/me/log")
    finally:
        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_newest_first_with_all_kinds(client: AsyncClient, db_session: AsyncSession) -> None:
    c, b = await _seed(db_session)
    db_session.add_all([
        _m(b, 10, value_numeric=3.4),
        _m(b, 20, "note", value_text="smells fruity"),
    ])
    await db_session.commit()

    body = (await client.get("/me/log")).json()
    assert [e["kind"] for e in body] == ["note", "measurement", "stage-change"]
    assert body[0]["detail"] == {
        "type": "note", "value_numeric": None, "value_text": "smells fruity", "notes": None,
    }
    assert body[1]["detail"]["value_numeric"] == 3.4
    assert body[2]["detail"] == {"stage": "F1"}
    assert body[0]["culture"] == {"id": str(c.id), "name": "Jar", "type": "kombucha"}
    assert body[0]["batch"]["id"] == str(b.id)
    assert body[0]["batch"]["current_stage"] == "F1"


@pytest.mark.asyncio
async def test_q_matches_text_notes_stage_and_escapes_wildcards(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, b = await _seed(db_session)
    db_session.add_all([
        _m(b, 1, "note", value_text="Pellicle forming"),
        _m(b, 2, notes="tasted SOUR", value_numeric=3.0),
        _m(b, 3, notes="100% sure"),
        _m(b, 4, notes="plain"),
        _m(b, 5, notes="a_b"),
        _m(b, 6, notes="axb"),
    ])
    await db_session.commit()

    async def notes(q: str) -> list[str | None]:
        r = await client.get("/me/log", params={"q": q, "type": "ph"})
        return [e["detail"]["notes"] for e in r.json()]

    assert (await client.get("/me/log", params={"q": "pellicle"})).json()[0]["detail"]["value_text"]
    assert await notes("sour") == ["tasted SOUR"]
    assert await notes("%") == ["100% sure"]  # literal, not "match everything"
    assert await notes("a_b") == ["a_b"]  # "_" is not a single-char wildcard
    assert await notes("\\") == []
    stage = (await client.get("/me/log", params={"q": "f1"})).json()
    assert [e["kind"] for e in stage] == ["stage-change"]


@pytest.mark.asyncio
async def test_culture_type_since_filters(client: AsyncClient, db_session: AsyncSession) -> None:
    c1, b1 = await _seed(db_session, name="A")
    c2, b2 = await _seed(db_session, name="B")
    db_session.add_all([_m(b1, 10), _m(b1, 20, "note", value_text="n"), _m(b2, 30)])
    await db_session.commit()

    by_culture = (await client.get("/me/log", params={"culture_id": str(c1.id)})).json()
    assert {e["culture"]["name"] for e in by_culture} == {"A"}
    assert len(by_culture) == 3  # 2 measurements + stage-change

    notes = (await client.get("/me/log", params={"type": "note"})).json()
    assert [e["kind"] for e in notes] == ["note"]  # no stage-change unless type absent/"stage-change"
    stages = (await client.get("/me/log", params={"type": "stage-change"})).json()
    assert [e["kind"] for e in stages] == ["stage-change"] * 2

    since = (T0 + timedelta(minutes=20)).isoformat()  # inclusive
    recent = (await client.get("/me/log", params={"since": since})).json()
    assert [e["kind"] for e in recent] == ["measurement", "note"]


@pytest.mark.asyncio
async def test_pagination_no_overlap_or_gap_with_equal_timestamps(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, b = await _seed(db_session)
    # 7 measurements share one timestamp, and the stage-change ties with them too.
    db_session.add_all([_m(b, 0, value_text=f"m{i}") for i in range(7)] + [_m(b, 5)])
    await db_session.commit()

    full = (await client.get("/me/log", params={"limit": 200})).json()
    assert len(full) == 9
    paged: list[dict] = []
    for off in range(0, 12, 4):
        paged += (await client.get("/me/log", params={"limit": 4, "offset": off})).json()
    assert paged == full
    keys = [(e["timestamp"], e["detail"].get("value_text"), e["kind"]) for e in paged]
    assert len(set(keys)) == len(keys)


@pytest.mark.asyncio
async def test_other_users_data_is_invisible(client: AsyncClient, db_session: AsyncSession) -> None:
    c, b = await _seed(db_session, owner="someone-else", name="Theirs")
    db_session.add(_m(b, 1, "note", value_text="secret"))
    await db_session.commit()

    assert (await client.get("/me/log")).json() == []
    assert (await client.get("/me/log", params={"culture_id": str(c.id)})).json() == []
    assert (await client.get("/me/log", params={"q": "secret"})).json() == []

    app.dependency_overrides[get_current_user_id] = lambda: "someone-else"
    try:
        assert len((await client.get("/me/log")).json()) == 2
    finally:
        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID


@pytest.mark.asyncio
async def test_limit_bounds(client: AsyncClient) -> None:
    assert (await client.get("/me/log", params={"limit": 0})).status_code == 422
    assert (await client.get("/me/log", params={"limit": 201})).status_code == 422
    assert (await client.get("/me/log", params={"offset": -1})).status_code == 422


@pytest.mark.asyncio
async def test_entry_ids_present_and_match_source_rows(client: AsyncClient, db_session: AsyncSession) -> None:
    _, b = await _seed(db_session)
    m, n = _m(b, 10, value_numeric=3.4), _m(b, 20, "note", value_text="x")
    db_session.add_all([m, n])
    await db_session.commit()

    body = (await client.get("/me/log")).json()
    ids = {e["kind"]: e["id"] for e in body}
    assert ids == {"note": str(n.id), "measurement": str(m.id), "stage-change": str(b.id)}
    assert len({e["id"] for e in body if e["kind"] != "stage-change"}) == 2  # unique per measurement row


@pytest.mark.asyncio
async def test_q_backslash_is_literal(client: AsyncClient, db_session: AsyncSession) -> None:
    _, b = await _seed(db_session)
    db_session.add(_m(b, 1, "note", notes=r"saved to C:\dir"))
    await db_session.commit()

    hit = (await client.get("/me/log", params={"q": "\\"})).json()
    assert [e["kind"] for e in hit] == ["note"]
    assert (await client.get("/me/log", params={"q": "%"})).json() == []


@pytest.mark.asyncio
async def test_type_filter_is_case_insensitive(client: AsyncClient, db_session: AsyncSession) -> None:
    _, b = await _seed(db_session)
    db_session.add_all([_m(b, 1, "pH", value_numeric=3.3), _m(b, 2, "ph", value_numeric=3.2), _m(b, 3, "brix")])
    await db_session.commit()

    for t in ("ph", "PH"):
        body = (await client.get("/me/log", params={"type": t})).json()
        assert sorted(e["detail"]["type"] for e in body) == ["pH", "ph"]


@pytest.mark.asyncio
async def test_empty_type_equals_no_type(client: AsyncClient, db_session: AsyncSession) -> None:
    _, b = await _seed(db_session)
    db_session.add(_m(b, 1, value_numeric=3.3))
    await db_session.commit()

    base = (await client.get("/me/log")).json()
    assert [e["kind"] for e in base] == ["measurement", "stage-change"]
    assert (await client.get("/me/log", params={"type": ""})).json() == base


@pytest.mark.asyncio
async def test_offset_and_q_caps(client: AsyncClient) -> None:
    assert (await client.get("/me/log", params={"offset": 10_000})).status_code == 200
    assert (await client.get("/me/log", params={"offset": 10_001})).status_code == 422
    assert (await client.get("/me/log", params={"q": "x" * 201})).status_code == 422


async def test_logged_stage_history_appears_once(client) -> None:
    c = await client.post("/cultures", json={"name": "Levain", "type": "sourdough"})
    b = (await client.post("/batches", json={"culture_id": c.json()["id"]})).json()
    await client.patch(f"/batches/{b['id']}/stage", json={"stage": "bulk_ferment"})
    await client.patch(f"/batches/{b['id']}/stage", json={"stage": "shape"})
    log = (await client.get("/me/log", params={"type": "stage-change"})).json()
    stages = [e["detail"]["stage"] for e in log if e["batch"]["id"] == b["id"]]
    assert stages == ["shape", "bulk_ferment"]  # the history, newest first, no synthesized duplicate
