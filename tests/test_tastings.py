"""Tastings (build plan B10; design § 11.2): POST, GET and DELETE /batches/{id}/tastings
(owner only, any batch, validated ratings), t_h from tasted_at, the stop-by tasting reminder
that Start batch creates (closed by a tasting, never by a stage change), the batch preview's
tastings_count, the export and account deletion, the community publish check, and what the
calibration gate (B11) reads: the link's P series at a tasting's t_h."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from test_community import _batch as _community_batch
from test_community import _publish, as_user
from test_recommendations_api import catalogue  # noqa: F401

from fermenttrack import database
from fermenttrack.config import settings
from fermenttrack.models import (
    SAFETY_REMINDER,
    STAGE_REMINDER,
    TASTING_REMINDER,
    Batch,
    Culture,
    RecommendationLink,
    Reminder,
    Tasting,
)
from fermenttrack.recommender import community as C
from fermenttrack.recommender import gate, grid, run
from fermenttrack.recommender import service as S
from fermenttrack.routers.recommendations import TASTING_AFTER_PH, TASTING_REMINDER_ACTION
from fermenttrack.routers.tastings import FUTURE_SKEW
from tests.conftest import TEST_USER_ID

KIMCHI = "napa_kimchi_room_temp"
KOJI = "rice_koji_steamed_rice"
OTHER = "someone-else"
NOTE = "Grandma's secret: tasted it in the cellar"  # distinctive, to search the logs for
STARTED = datetime.now(UTC).replace(microsecond=0) - timedelta(days=5)


async def _batch(
    db: AsyncSession, *, owner: str = TEST_USER_ID, ended: datetime | None = None
) -> Batch:
    """A plain batch (no recommendation behind it), started STARTED."""
    culture = Culture(name="my kraut", type="lacto_ferment", owner_id=owner)
    db.add(culture)
    await db.flush()
    batch = Batch(
        culture_id=culture.id, started_at=STARTED, current_stage="ferment",
        stage_entered_at=STARTED, outcome="in_progress" if ended is None else "success",
        ended_at=ended,
    )  # fmt: skip
    db.add(batch)
    await db.commit()
    return batch


def _url(batch_id: Any) -> str:
    return f"/batches/{batch_id}/tastings"


async def _count(db: AsyncSession) -> int:
    return int((await db.execute(select(func.count()).select_from(Tasting))).scalar_one())


# ── create, list, delete ────────────────────────────────────────────────


async def test_create_list_and_delete_a_tasting(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = await _batch(db_session)
    payload = {
        "tasted_at": (STARTED + timedelta(hours=30)).isoformat(),
        "ratings": {"sour": 2, "fruity": 1, "pungent": 0},
        "liking": 4, "make_again": True, "notes": f"  {NOTE}  ",
    }  # fmt: skip
    resp = await client.post(_url(batch.id), json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["batch_id"] == str(batch.id) and body["t_h"] == 30.0
    assert body["ratings"] == {"fruity": 1, "pungent": 0, "sour": 2}  # in run.SERIES order
    assert list(body["ratings"]) == [s for s in run.SERIES if s in body["ratings"]]
    assert (body["liking"], body["make_again"], body["notes"]) == (4, True, NOTE)
    later = await client.post(_url(batch.id), json={"liking": 2})  # a liking alone is enough
    assert later.status_code == 201, later.text
    assert (later.json()["ratings"], later.json()["make_again"], later.json()["notes"]) == (
        {}, None, None,
    )  # fmt: skip

    listed = (await client.get(_url(batch.id))).json()
    assert [t["id"] for t in listed] == [body["id"], later.json()["id"]]  # earliest t_h first
    assert (await client.delete(f"{_url(batch.id)}/{body['id']}")).status_code == 204
    assert [t["id"] for t in (await client.get(_url(batch.id))).json()] == [later.json()["id"]]
    assert (await client.delete(f"{_url(batch.id)}/{body['id']}")).status_code == 404


async def test_t_h_is_the_hours_since_the_batch_started(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = await _batch(db_session)
    ask = {"liking": 3}
    naive = (STARTED + timedelta(hours=12, minutes=30)).replace(tzinfo=None).isoformat()
    resp = await client.post(_url(batch.id), json=ask | {"tasted_at": naive})  # no zone: UTC
    assert resp.status_code == 201 and resp.json()["t_h"] == 12.5
    elsewhere = (STARTED + timedelta(hours=2)).astimezone(timezone(timedelta(hours=-5)))
    resp = await client.post(_url(batch.id), json=ask | {"tasted_at": elsewhere.isoformat()})
    assert resp.json()["t_h"] == 2.0

    def hours_now() -> float:
        return (datetime.now(UTC) - STARTED).total_seconds() / 3600.0

    now = (await client.post(_url(batch.id), json=ask)).json()["t_h"]  # default: now
    assert now == pytest.approx(hours_now(), abs=0.01)
    ahead = datetime.now(UTC) + FUTURE_SKEW / 2  # a client clock a little ahead: taken as now
    resp = await client.post(_url(batch.id), json=ask | {"tasted_at": ahead.isoformat()})
    assert resp.status_code == 201 and resp.json()["t_h"] == pytest.approx(hours_now(), abs=0.01)
    for bad, why in (
        (STARTED - timedelta(minutes=1), "before the batch started"),
        (datetime.now(UTC) + 2 * FUTURE_SKEW, "in the future"),
    ):
        resp = await client.post(_url(batch.id), json=ask | {"tasted_at": bad.isoformat()})
        assert resp.status_code == 422 and why in resp.json()["detail"]
    at_start = await client.post(_url(batch.id), json=ask | {"tasted_at": STARTED.isoformat()})
    assert at_start.json()["t_h"] == 0.0


async def test_any_batch_can_be_tasted_even_after_it_ended(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Not only recommended batches: the calibration baseline needs every tasted batch."""
    running = await _batch(db_session)
    ended = await _batch(db_session, ended=STARTED + timedelta(days=2))
    for batch in (running, ended):
        resp = await client.post(_url(batch.id), json={"ratings": {"sour": 3}})
        assert resp.status_code == 201, resp.text
    assert (await client.get(_url(ended.id))).json()[0]["t_h"] > 48  # tasted after it ended
    assert (await db_session.execute(select(RecommendationLink))).first() is None


async def test_only_the_owner_reaches_a_batch_s_tastings(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    theirs = await _batch(db_session, owner=OTHER)
    mine = await _batch(db_session)
    with as_user(OTHER):
        tasting = (await client.post(_url(theirs.id), json={"liking": 5, "notes": NOTE})).json()
    assert (await client.post(_url(theirs.id), json={"liking": 1})).status_code == 404
    assert (await client.get(_url(theirs.id))).status_code == 404
    assert (await client.delete(f"{_url(theirs.id)}/{tasting['id']}")).status_code == 404
    # someone else's tasting through one's own batch: not found either
    assert (await client.delete(f"{_url(mine.id)}/{tasting['id']}")).status_code == 404
    assert (await client.get(_url(uuid.uuid4()))).status_code == 404
    # an admin reads other people's batches, not their tastings (the notes are theirs)
    monkeypatch.setattr(settings, "admin_user_ids", TEST_USER_ID)
    assert (await client.get(f"/batches/{theirs.id}/preview")).status_code == 200
    assert (await client.get(_url(theirs.id))).status_code == 404
    assert await _count(db_session) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"ratings": {}},
        {"make_again": True, "notes": "nice"},  # neither ratings nor a liking
        {"ratings": {"chocolate": 1}},  # not a series
        {"ratings": {"Sour": 1}},
        {"ratings": {"ph_below_4_6": 1}},
        {"ratings": {"sour": 4}},
        {"ratings": {"sour": -1}},
        {"ratings": {"sour": 1.5}},
        {"ratings": {"sour": "2"}},
        {"ratings": {"sour": True}},
        {"ratings": {"sour": None}},
        {"liking": 0},
        {"liking": 6},
        {"liking": 4.5},
        {"liking": "4"},
        {"liking": 3, "notes": "x" * 1001},
        {"liking": 3, "notes": "a\u0000b"},  # Postgres refuses a NUL (its error carries text)
        {"liking": 3, "notes": "a\u001bb"},
        {"liking": 3, "notes": "a\u0008b"},
        {"liking": 3, "make_again": "maybe"},
        {"liking": 3, "tasted_at": "yesterday"},
    ],
    ids=[
        "empty", "empty ratings", "no rating no liking", "unknown series", "wrong case",
        "safety milestone", "rating 4", "rating -1", "rating 1.5", "rating string",
        "rating bool", "rating null", "liking 0", "liking 6", "liking 4.5", "liking string",
        "notes too long", "notes NUL", "notes ESC", "notes backspace", "make_again not bool",
        "tasted_at not a time",
    ],
)  # fmt: skip
async def test_validation(
    client: AsyncClient, db_session: AsyncSession, payload: dict[str, Any]
) -> None:
    batch = await _batch(db_session)
    resp = await client.post(_url(batch.id), json=payload)
    assert resp.status_code == 422, resp.text
    assert await _count(db_session) == 0


async def test_every_series_and_taste_can_be_rated_and_notes_have_1000_characters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = await _batch(db_session)
    every = {s: i % 4 for i, s in enumerate(run.SERIES)}
    assert len(every) == 20 and {"sour", "sweet", "umami", "alcohol"} <= set(every)
    resp = await client.post(_url(batch.id), json={"ratings": every, "notes": "x" * 1000})
    assert resp.status_code == 201, resp.text
    assert resp.json()["ratings"] == every and len(resp.json()["notes"]) == 1000
    blank = await client.post(_url(batch.id), json={"liking": 1, "notes": "   "})
    assert blank.json()["notes"] is None
    lines = await client.post(_url(batch.id), json={"liking": 1, "notes": "sour\tbright\r\nsalty"})
    assert lines.status_code == 201 and lines.json()["notes"] == "sour\tbright\r\nsalty"


async def test_a_database_error_never_carries_the_notes(db_session: AsyncSession) -> None:
    """hide_parameters on the app's engine (and the tests'): an error's message, which
    uvicorn would log, never holds the bound values."""
    assert database.engine.sync_engine.hide_parameters
    batch = await _batch(db_session)
    db_session.add(Tasting(batch_id=batch.id, t_h=-1.0, ratings={}, liking=9, notes=NOTE))
    with pytest.raises(IntegrityError) as caught:  # the database's checks refuse it
        await db_session.commit()
    await db_session.rollback()
    assert "ck_tastings" in str(caught.value) and NOTE not in str(caught.value)


async def test_notes_are_never_logged(
    client: AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not by the app at any level, nor by anything at INFO and above (uvicorn's default).
    Only a database driver's own DEBUG trace (aiosqlite logs its statements' parameters)
    would show them: never enabled outside local debugging, and not Postgres's."""
    # alembic's fileConfig (the migration tests) disables the loggers that exist by then
    for name, logger in logging.root.manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and name.startswith(("fermenttrack", "httpx")):
            monkeypatch.setattr(logger, "disabled", False)
    batch = await _batch(db_session)
    with caplog.at_level(logging.DEBUG):
        resp = await client.post(_url(batch.id), json={"liking": 4, "notes": NOTE})
        assert resp.status_code == 201
        await client.get(_url(batch.id))
        await client.post(_url(batch.id), json={"notes": NOTE})  # refused: still not logged
    logged = [
        r.getMessage() for r in caplog.records
        if r.name.startswith("fermenttrack") or r.levelno >= logging.INFO
    ]  # fmt: skip
    assert logged and not [m for m in logged if NOTE in m]


# ── the batch preview, the export, account deletion ─────────────────────


async def test_the_preview_says_whether_the_batch_was_tasted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """B12 offers the tasting form on finishing while tastings_count is 0."""
    culture = (await client.post("/cultures", json={"name": "k", "type": "lacto_ferment"})).json()
    batch = (await client.post("/batches", json={"culture_id": culture["id"]})).json()
    finished = await client.patch(f"/batches/{batch['id']}/stage", json={"stage": "ready"})
    assert finished.json()["outcome"] == "success"
    preview = (await client.get(f"/batches/{batch['id']}/preview")).json()
    assert preview["tastings_count"] == 0
    await client.post(_url(batch["id"]), json={"liking": 5})
    await client.post(_url(batch["id"]), json={"liking": 4})
    assert (await client.get(f"/batches/{batch['id']}/preview")).json()["tastings_count"] == 2


async def test_the_preview_gives_the_targets_the_batch_was_recommended_for(
    client: AsyncClient,
    db_session: AsyncSession,
    catalogue: None,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tasting form rates the card's targets first: the preview hands them back (its
    recommendation link's keys), so the browser keeps nothing."""
    request = {"recipe_key": KIMCHI, "aromas": ["fruity"], "tastes": ["sour"]}
    started = (await client.post("/batches/from-recommendation", json=request)).json()
    url = f"/batches/{started['batch']['id']}/preview"
    preview = (await client.get(url)).json()
    assert [t["key"] for t in started["link"]["targets"]] == ["fruity", "sour"]
    assert preview["recommendation_targets"] == ["fruity", "sour"]
    plain = await client.post("/batches/from-recommendation", json={"recipe_key": KIMCHI})
    assert (await client.get(f"/batches/{plain.json()['batch']['id']}/preview")).json()[
        "recommendation_targets"
    ] == []  # started from a card asked for no target
    unlinked = await _batch(db_session)
    assert (await client.get(f"/batches/{unlinked.id}/preview")).json()[
        "recommendation_targets"
    ] is None  # not started from a card
    monkeypatch.setattr(settings, "admin_user_ids", OTHER)
    with as_user(OTHER):  # an admin's read-only view: the keys too (no score, no tasting)
        seen = (await client.get(url)).json()
    assert (seen["read_only"], seen["recommendation_targets"]) == (True, ["fruity", "sour"])
    with as_user(OTHER + "-not-admin"):
        assert (await client.get(url)).status_code == 404


async def test_the_export_includes_tastings_and_deleting_the_account_removes_them(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = await _batch(db_session)
    later = {"liking": 4, "notes": NOTE, "tasted_at": (STARTED + timedelta(hours=40)).isoformat()}
    earlier = {"liking": 2, "tasted_at": (STARTED + timedelta(hours=10)).isoformat()}
    posted = [(await client.post(_url(batch.id), json=t)).json() for t in (later, earlier)]
    with as_user(OTHER):
        theirs = await _batch(db_session, owner=OTHER)
        assert (await client.post(_url(theirs.id), json={"liking": 2})).status_code == 201
    export = (await client.get("/me/export")).json()
    [exported] = export[0]["batches"]
    # an extra per-batch field (csv.js ignores it), in tasting order (Batch.tastings by t_h)
    assert exported["tastings"] == posted[::-1]
    assert exported["measurements"] == []

    assert (await client.delete("/me")).status_code == 204
    left = (await db_session.execute(select(Tasting.batch_id))).scalars().all()
    assert left == [theirs.id]  # only the other account's


async def test_tastings_at_the_same_time_keep_one_order_in_the_export_and_the_list(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Batch.tastings (the export) orders like GET /batches/{id}/tastings: by t_h, then
    created_at, then id, so tastings at the same t_h never swap between reads."""
    batch = await _batch(db_session)
    at = datetime(2026, 10, 1, 12, 0)
    low, high = sorted(uuid.uuid4() for _ in range(2))  # the same t_h and created_at: by id
    rows = [
        Tasting(id=high, batch_id=batch.id, t_h=5.0, ratings={}, liking=1, created_at=at),
        Tasting(batch_id=batch.id, t_h=5.0, ratings={}, liking=2, created_at=at - timedelta(1)),
        Tasting(id=low, batch_id=batch.id, t_h=5.0, ratings={}, liking=3, created_at=at),
        Tasting(batch_id=batch.id, t_h=1.0, ratings={}, liking=4, created_at=at + timedelta(1)),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    expected = [str(rows[3].id), str(rows[1].id), str(low), str(high)]
    listed = [t["id"] for t in (await client.get(_url(batch.id))).json()]
    [exported] = (await client.get("/me/export")).json()[0]["batches"]
    assert listed == [t["id"] for t in exported["tastings"]] == expected


# ── the stop-by reminder (Start batch) ──────────────────────────────────


async def _open(db: AsyncSession, batch_id: str) -> dict[str, str]:
    """The batch's open reminders: id -> kind."""
    rows = await db.execute(
        select(Reminder.id, Reminder.kind)
        .where(Reminder.batch_id == uuid.UUID(batch_id), Reminder.completed_at.is_(None))
        .execution_options(populate_existing=True)
    )
    return {str(i): k for i, k in rows.tuples()}


async def test_start_batch_asks_for_a_tasting_at_the_stop_by_time(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    body = (await client.post("/batches/from-recommendation", json={"recipe_key": KIMCHI})).json()
    batch_id = body["batch"]["id"]
    kinds = [r["kind"] for r in body["reminders"]]
    assert sorted(kinds) == sorted([STAGE_REMINDER, SAFETY_REMINDER, TASTING_REMINDER])
    [tasting] = [r for r in body["reminders"] if r["kind"] == TASTING_REMINDER]
    # an acid-safety ferment: the prompt carries the gate's pH deadline line verbatim (time
    # limit and discard rule included), never a reworded clearance
    assert gate.PH_DEADLINE_LINE in tasting["action"]
    assert tasting["action"] == f"{TASTING_REMINDER_ACTION} Before tasting: {gate.PH_DEADLINE_LINE}"
    assert TASTING_AFTER_PH == f"Before tasting: {gate.PH_DEADLINE_LINE}"
    assert tasting["urgency"] == "medium"
    due, started = (
        datetime.fromisoformat(x).replace(tzinfo=None)
        for x in (tasting["due_at"], body["batch"]["started_at"])
    )
    stop_by = body["link"]["window"]["stop_by_h"]
    assert abs((due - started) - timedelta(hours=stop_by)) < timedelta(seconds=1)

    # a stage change, then finishing the batch, close the stage timers only
    assert (await client.patch(f"/batches/{batch_id}/stage", json={})).status_code == 200
    finish = await client.patch(f"/batches/{batch_id}/stage", json={"stage": "ready"})
    assert finish.json()["outcome"] == "success"
    assert set((await _open(db_session, batch_id)).values()) == {SAFETY_REMINDER, TASTING_REMINDER}
    # the tasting closes the prompt; the pH check stays the user's to close
    assert (await client.post(_url(batch_id), json={"ratings": {"sour": 2}})).status_code == 201
    assert set((await _open(db_session, batch_id)).values()) == {SAFETY_REMINDER}
    stored = await db_session.get(Reminder, uuid.UUID(tasting["id"]), populate_existing=True)
    assert stored is not None and stored.completed_at is not None


async def test_the_stop_by_prompt_of_a_type_without_a_ph_check(
    client: AsyncClient, catalogue: None  # noqa: F811
) -> None:
    body = (await client.post("/batches/from-recommendation", json={"recipe_key": KOJI})).json()
    [tasting] = [r for r in body["reminders"] if r["kind"] == TASTING_REMINDER]
    assert tasting["action"] == TASTING_REMINDER_ACTION
    assert gate.PH_DEADLINE_LINE not in tasting["action"]
    assert SAFETY_REMINDER not in {r["kind"] for r in body["reminders"]}


async def test_a_tasting_closes_only_its_own_batch_s_prompt(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    first = (await client.post("/batches/from-recommendation", json={"recipe_key": KOJI})).json()
    second = (await client.post("/batches/from-recommendation", json={"recipe_key": KOJI})).json()
    await client.post(_url(first["batch"]["id"]), json={"liking": 3})
    assert TASTING_REMINDER not in (await _open(db_session, first["batch"]["id"])).values()
    assert TASTING_REMINDER in (await _open(db_session, second["batch"]["id"])).values()


# ── what the calibration gate (B11) reads ───────────────────────────────


async def test_the_link_keeps_p_per_target_for_a_tasting_at_any_time(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    """B11 joins a tasting to its batch's link and reads P_s(t_h) from link.p_series: the
    card's own statistics (here the grid at the served temperature), on its time axis."""
    ask = {"recipe_key": KIMCHI, "aromas": ["pungent"], "tastes": ["sour"], "temperature_c": 22}
    body = (await client.post("/batches/from-recommendation", json=ask)).json()
    batch_id = uuid.UUID(body["batch"]["id"])
    batch = await db_session.get(Batch, batch_id)
    assert batch is not None
    batch.started_at = STARTED  # five days ago: the peak is in the past
    await db_session.commit()
    link = await db_session.get(RecommendationLink, batch_id)
    assert link is not None and link.p_series is not None
    series = link.p_series
    t = np.asarray(series["t_h"], dtype=float)
    assert len(t) >= 2 and np.all(np.diff(t) > 0)
    assert list(series["p"]) == ["pungent", "sour"]  # the targets, in order
    stats = grid.interp_temp(KIMCHI, 22.0)
    np.testing.assert_allclose(t, stats.t_h, atol=1e-4)
    for key, p in series["p"].items():
        assert len(p) == len(t) and all(0.0 <= x <= 1.0 for x in p)
        np.testing.assert_allclose(p, stats.p[key], atol=1e-4)
    peak = body["link"]["window"]["peak_h"]
    assert peak < 5 * 24

    # the join B11 makes: tasting -> link (batch_id), P_s at the tasting's t_h
    tasted_at = STARTED + timedelta(hours=peak)
    resp = await client.post(
        _url(batch_id), json={"tasted_at": tasted_at.isoformat(), "ratings": {"sour": 2}}
    )
    assert resp.status_code == 201, resp.text
    tasting, linked = (
        await db_session.execute(
            select(Tasting, RecommendationLink).join(
                RecommendationLink, RecommendationLink.batch_id == Tasting.batch_id
            )
        )
    ).one()
    assert tasting.t_h == pytest.approx(peak, abs=1e-3)
    p_sour = float(np.interp(tasting.t_h, linked.p_series["t_h"], linked.p_series["p"]["sour"]))
    assert p_sour == pytest.approx(float(np.interp(peak, stats.t_h, stats.p["sour"])), abs=1e-3)
    assert tasting.ratings["sour"] >= 1  # design § 13.2: noticed = rating >= 1


async def test_a_link_without_a_modelled_target_has_no_p_series(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    body = (await client.post("/batches/from-recommendation", json={"recipe_key": KOJI})).json()
    found = await db_session.execute(
        select(RecommendationLink.p_series.is_(None)).where(
            RecommendationLink.batch_id == uuid.UUID(body["batch"]["id"])
        )
    )
    assert found.scalar_one() is True  # SQL NULL, not a JSON null


def test_p_series_json_keeps_modelled_targets_only() -> None:
    recipe = S.active_recipe(KIMCHI)
    targets = S.parse_targets(["pungent", "caramel"], ["sour"])  # kimchi has no caramel series
    card, _ = S.build_card(recipe, targets, 22.0)
    assert card is not None
    assert [s.target.key for s in card.evaluation.targets if not s.modelled] == ["caramel"]
    doc = S.p_series_json(card.evaluation)
    assert doc is not None and list(doc["p"]) == ["pungent", "sour"]
    none, _ = S.build_card(recipe, (), 22.0)
    assert none is not None and S.p_series_json(none.evaluation) is None


# ── the community publish check ─────────────────────────────────────────


async def test_publishing_needs_a_tasting(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    batch = await _community_batch(db_session, tasted=False)
    refused = await _publish(client, batch)
    assert refused.status_code == 422
    assert refused.json()["detail"]["reasons"] == [C.TASTING_NEEDED]
    assert (await client.post(_url(batch.id), json={"liking": 4})).status_code == 201
    resp = await _publish(client, batch)
    assert resp.status_code == 201, resp.text
