"""Search deeper (design § 10.2): the background job queue (recommender.jobs) and its API.

A live 64-member forecast takes seconds; most tests stand a fake in for it (FakeLive: the
parent's grid statistics, or zeros), so a whole job of up to 20 forecasts runs in about a
second. One test confirms a planned step with the real engine. The worker is driven step by
step (`run_once`) on the conftest engine; the test of the app's own worker (lifespan) uses a
file database, where the worker and the requests polling it each get their own connection.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import threading
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    InterfaceError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from fermenttrack import database
from fermenttrack.auth import get_current_user_id
from fermenttrack.config import settings
from fermenttrack.database import Base
from fermenttrack.main import app
from fermenttrack.models import RecommendationJob
from fermenttrack.prediction import service as engine
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import grid, jobs, library, operators
from fermenttrack.recommender import service as S
from fermenttrack.schemas import RecommendationCardOut, RecommendationRequest
from tests.conftest import TEST_USER_ID

URL = "/recommendations/deep-search"
OTHER = "someone-else"
KRAUT = "sauerkraut_dry_salted"
PERSIMMON = 169941  # USDA FDC: Persimmons, japanese, raw
BODY = {"ingredients": ["Fresh ginger"], "aromas": ["pungent"], "tastes": ["sour"],
        "mode": "experimental"}  # fmt: skip
OTHER_BODY = BODY | {"tastes": []}


def _request(body: dict[str, Any]) -> dict[str, Any]:
    """The request as the job stores it (the route leaves out community_recipe_id)."""
    request = RecommendationRequest.model_validate(body)
    return request.model_dump(mode="json", exclude={"community_recipe_id"})


class FakeLive:
    """Stands in for service.live_variant_statistics (seconds per call on the engine): the
    parent's grid statistics at that temperature on the requested time axis, or zeros. It can
    block at one call (until `release`) or raise at one."""

    def __init__(
        self, *, block_at: int | None = None, fail_at: int | None = None,
        error: Exception | None = None, zero: bool = False,
    ) -> None:  # fmt: skip
        self.calls: list[tuple[str, float, int]] = []
        self.block_at, self.fail_at, self.error, self.zero = block_at, fail_at, error, zero
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(
        self, recipe: library.Recipe, model_c: float, members: int, t_dst: Any, end_h: float
    ) -> tuple[grid.Entry, str, bool]:
        i = len(self.calls)
        self.calls.append((recipe.key, model_c, members))
        if i == self.fail_at and self.error is not None:
            raise self.error
        if i == self.block_at:
            self.started.set()
            assert self.release.wait(60)
        src = grid.interp_temp(recipe.key, model_c)

        def on(m: Any) -> Any:
            return type(m)({
                s: np.zeros(len(t_dst)) if self.zero else np.interp(t_dst, src.t_h, v)
                for s, v in m.items()
            })  # fmt: skip

        entry = dataclasses.replace(
            src, recipe_key=recipe.key, temp_c=model_c, t_h=np.asarray(t_dst), e=on(src.e),
            u=on(src.u), p=on(src.p), members=members,
        )  # fmt: skip
        return entry, f"fake:{recipe.key}:{i}", True


@pytest.fixture(autouse=True)
def _fresh_job_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jobs, "_STEP_TIMES", {})
    monkeypatch.setattr(settings, "candidates_path", None)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeLive]:
    live = FakeLive()
    monkeypatch.setattr(S, "live_variant_statistics", live)
    yield live
    live.release.set()


@pytest.fixture
def sessions(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """The worker's session factory on the conftest engine (the one the API uses)."""
    return async_sessionmaker(db_session.bind, expire_on_commit=False)


@contextlib.contextmanager
def as_user(user_id: str) -> Iterator[None]:
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    try:
        yield
    finally:
        app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID


async def _row(sessions: async_sessionmaker[AsyncSession], job_id: Any) -> RecommendationJob | None:
    async with sessions() as db:
        return await db.get(RecommendationJob, uuid.UUID(str(job_id)))


async def _submit(client: AsyncClient, body: dict[str, Any] = BODY) -> str:
    resp = await client.post(URL, json=body)
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "queued"
    return str(resp.json()["job_id"])


def _cards(body: dict[str, Any]) -> list[RecommendationCardOut]:
    return [RecommendationCardOut.model_validate(c) for c in body["results"]]


def _variant(step: dict[str, Any]) -> S.Variant:
    """A planned step's variant, resolved as the worker resolves it."""
    parent = S.library_parent(step["recipe_key"])
    asked = [
        S.OperatorRequest(o["op"], o["ingredient"], o["replaces"], o["to_c"], o["fdc_id"])
        for o in step["operators"]
    ]
    return S.make_variant(parent, S.resolve_operators(parent, asked))


# ── the plan: design § 10.2's order ─────────────────────────────────────


def test_the_plan_follows_design_10_2_order() -> None:
    request = _request({"aromas": ["fruity"], "tastes": ["sour"], "mode": "both",
                        "usda_fdc_ids": [PERSIMMON]})  # fmt: skip
    steps = jobs.plan_deep_search(request)
    assert len(steps) == jobs.MAX_FORECASTS
    stages = [s["stage"] for s in steps]
    order = ["screened", "temperature", "usda"]
    assert stages == sorted(stages, key=order.index) and set(stages) == set(order)
    assert len({s["id"] for s in steps}) == len(steps)
    q = jobs.query(request)
    keys = []
    for s in steps:
        v = _variant(s)
        assert v.id == s["id"] and v.parent.recipe.handoff != "planner"  # no sourdough
        assert S.variant_gate(v, S.variant_temperature(v, q.temperature_c)).ok
        foods = [op.fdc_id for op in v.operators if op.fdc_id is not None]
        if s["stage"] == "usda":
            assert foods == [PERSIMMON]
        if s["stage"] == "screened":  # not confirmed yet, and never the user's USDA food
            assert v.screened and not foods
            reference = S.library_reference(v.parent.recipe, None)
            card, _ = S.variant_card(v, q.targets, None, 1000.0, (), reference)
            assert card is not None
            keys.append(S.experimental_rank_key(card))
    assert keys == sorted(keys)  # ranked across parents by § 5.4 Experimental


def test_two_extra_temperatures_per_top_parent() -> None:
    request = _request(BODY)
    steps = jobs.plan_deep_search(request)
    moved = [s for s in steps if s["stage"] == "temperature"]
    assert moved
    per_parent: dict[str, int] = {}
    for s in moved:
        per_parent[s["recipe_key"]] = per_parent.get(s["recipe_key"], 0) + 1
        recipe = library.get(s["recipe_key"])
        assert recipe is not None and recipe.temp_c is not None
        [to_c] = [o["to_c"] for o in s["operators"] if o["op"] == "temperature"]
        lo, hi = PROFILES[recipe.fermentation_type].temp_range
        assert lo <= to_c <= hi and not recipe.temp_c.lo <= to_c <= recipe.temp_c.hi
        assert to_c not in grid.axis(recipe.key)  # a temperature the grid does not hold
    assert set(per_parent.values()) <= {1, jobs.EXTRA_TEMPERATURES}


@pytest.mark.parametrize(
    ("key", "want"),
    [
        (KRAUT, (18.0, 17.0)),  # grid 16, 20, 22.5, 24; documented 21.1-23.9
        ("lactic_fresh_cheese_curd", (29.0, 31.0)),  # grid 28, 30, 32 (documented 21-22)
        ("pacific_sand_lance_rice_koji_fish_sauce", (45.0, 37.5)),  # the gate stops at 45 °C
        ("rice_koji_steamed_rice", ()),  # the documented 27-40 °C covers the profile's range
    ],
)
def test_extra_temperatures_fill_the_grid_s_largest_gaps(
    key: str, want: tuple[float, ...]
) -> None:
    recipe = library.get(key)
    assert recipe is not None
    got = jobs.extra_temperatures(recipe)
    assert got == want
    assert all(operators.temperature_ok(recipe, t) for t in got)


# ── the job API and the worker ──────────────────────────────────────────


async def test_a_job_runs_queued_running_done(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession], fake: FakeLive
) -> None:
    job_id = await _submit(client)
    queued = (await client.get(f"/recommendations/jobs/{job_id}")).json()
    assert (queued["status"], queued["done"], queued["total"], queued["results"]) == (
        "queued", 0, 0, []
    )
    # not planned yet: 20 forecasts at the prior 15 s
    assert queued["eta_s"] == round(jobs.MAX_FORECASTS * jobs.DEFAULT_STEP_S)
    assert queued["request"] == _request(BODY) and queued["started_at"] is None
    worker = jobs.Worker(sessions)
    assert await worker.run_once()
    assert not await worker.run_once()  # the queue is empty
    body = (await client.get(f"/recommendations/jobs/{job_id}")).json()
    assert (body["status"], body["eta_s"], body["error"]) == ("done", None, None)
    assert 0 < body["total"] <= jobs.MAX_FORECASTS and body["done"] == body["total"]
    assert body["started_at"] and body["finished_at"]
    assert len(fake.calls) == body["total"]
    assert {m for _, _, m in fake.calls} == {S.FORECAST_MEMBERS}  # 64-member forecasts
    cards = _cards(body)
    assert len(cards) == body["total"]
    row = await _row(sessions, job_id)
    assert row is not None
    ranks = [r["rank"] for r in row.results]
    assert ranks == sorted(ranks)  # re-ranked by § 5.4 Experimental
    assert [r["card"]["id"] for r in row.results] == [c.id for c in cards]
    for card in cards:  # confirmed, never "screened"; the gate's safety lines kept
        assert card.section == "experimental" and card.source_kind == "variant"
        assert not card.screened and S.SCREENED not in card.trust.labels
        assert S.SCREENED_NOTE not in card.notes and card.safety_lines
        combined = len(card.operators) >= 2 or any(o.op == "usda" for o in card.operators)
        assert (card.interaction_detected is not None) is combined


async def test_partial_results_are_visible_while_it_runs(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession], fake: FakeLive
) -> None:
    fake.block_at = 1
    job_id = await _submit(client)
    task = asyncio.create_task(jobs.Worker(sessions).run_once())
    try:
        assert await asyncio.to_thread(fake.started.wait, 60)
        body = (await client.get(f"/recommendations/jobs/{job_id}")).json()
        assert (body["status"], body["done"]) == ("running", 1)
        assert body["total"] > 1 and len(body["results"]) == 1
        assert body["eta_s"] > 0 and body["started_at"] and body["finished_at"] is None
        assert not _cards(body)[0].screened
    finally:
        fake.release.set()
    assert await task
    body = (await client.get(f"/recommendations/jobs/{job_id}")).json()
    assert body["status"] == "done" and len(body["results"]) == body["total"]


async def test_one_queued_or_running_job_per_owner(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = await _submit(client)
    for body in (OTHER_BODY, BODY):  # another request, or the same one before it finished
        resp = await client.post(URL, json=body)
        assert resp.status_code == 409
        assert resp.json()["detail"]["job_id"] == first
    with as_user(OTHER):
        await _submit(client)  # one per owner
    # two requests at once both pass the check: the partial unique index decides
    real = jobs.find_active
    seen: list[str] = []

    async def blind(db: AsyncSession, owner_id: str) -> RecommendationJob | None:
        seen.append(owner_id)
        return None if len(seen) == 1 else await real(db, owner_id)

    monkeypatch.setattr(jobs, "find_active", blind)
    resp = await client.post(URL, json=OTHER_BODY)
    assert resp.status_code == 409 and resp.json()["detail"]["job_id"] == first


async def test_a_restart_resumes_a_job_from_its_saved_progress(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession], fake: FakeLive
) -> None:
    fake.block_at = 1
    job_id = await _submit(client)
    task = asyncio.create_task(jobs.Worker(sessions).run_once())
    assert await asyncio.to_thread(fake.started.wait, 60)
    task.cancel()  # the instance goes to sleep in the middle of the second forecast
    with contextlib.suppress(asyncio.CancelledError):
        await task
    fake.release.set()
    row = await _row(sessions, job_id)
    assert row is not None and (row.status, row.done, len(row.results)) == ("running", 1, 1)
    total, started, plan = row.total, row.started_at, row.steps
    before = len(fake.calls)
    restarted = jobs.Worker(sessions)
    assert await restarted.requeue() == 1  # what start() does first
    requeued = await _row(sessions, job_id)
    assert requeued is not None and requeued.status == "queued"
    assert await restarted.run_once()
    row = await _row(sessions, job_id)
    assert row is not None and (row.status, row.done, row.total) == ("done", total, total)
    assert len(fake.calls) - before == total - 1  # from step 2 (cut short), not from scratch
    assert row.steps == plan and row.started_at == started and len(row.results) == total
    assert row.attempts == 2  # claimed twice


async def test_a_job_is_its_owner_s_only(client: AsyncClient) -> None:
    job_id = await _submit(client)
    with as_user(OTHER):
        assert (await client.get(f"/recommendations/jobs/{job_id}")).status_code == 404
        assert (await client.get("/recommendations/jobs")).json() == []
    assert (await client.get(f"/recommendations/jobs/{uuid.uuid4()}")).status_code == 404
    mine = (await client.get("/recommendations/jobs")).json()
    assert [j["job_id"] for j in mine] == [job_id]


async def test_a_repeated_request_gets_its_finished_job_back(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession], fake: FakeLive
) -> None:
    job_id = await _submit(client)
    worker = jobs.Worker(sessions)
    assert await worker.run_once()
    calls = len(fake.calls)
    again = await client.post(URL, json=BODY)
    assert again.status_code == 200 and again.json() == {"job_id": job_id, "status": "done"}
    both = await client.post(URL, json=BODY | {"mode": "both"})  # the mode changes nothing
    assert both.status_code == 200 and both.json()["job_id"] == job_id
    assert not await worker.run_once() and len(fake.calls) == calls  # nothing new to run
    other = await _submit(client, OTHER_BODY)  # another request: a new job
    assert other != job_id
    with as_user(OTHER):
        assert await _submit(client) != job_id  # results are kept per owner


def test_the_fingerprint_is_the_request_the_grid_the_model_and_the_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request(BODY)
    fp = jobs.deep_search_fingerprint(request)
    assert fp == jobs.deep_search_fingerprint(dict(reversed(request.items())))
    assert fp == jobs.deep_search_fingerprint(_request(BODY | {"mode": "both"}))  # no effect
    assert fp != jobs.deep_search_fingerprint(_request(OTHER_BODY))
    assert fp != jobs.fingerprint("community_forecast", request)
    with monkeypatch.context() as m:
        m.setattr(grid, "version", lambda: "another grid")
        assert fp != jobs.deep_search_fingerprint(request)
    with monkeypatch.context() as m:
        m.setattr(engine, "MODEL_VERSION", "another model")
        assert fp != jobs.deep_search_fingerprint(request)
    with monkeypatch.context() as m:  # a new plan or step algorithm
        handler = jobs.HANDLERS[jobs.DEEP_SEARCH]
        m.setitem(jobs.HANDLERS, jobs.DEEP_SEARCH, dataclasses.replace(handler, version=2))
        assert fp != jobs.deep_search_fingerprint(request)


@pytest.mark.parametrize(
    ("error", "shown"),
    [
        (engine.PredictionUnavailable("the forecast exceeded its time budget"),
         "the forecast exceeded its time budget"),
        (RuntimeError("internal detail"), jobs.FAILED_MESSAGE),  # never shown
    ],
)  # fmt: skip
async def test_a_failing_forecast_fails_its_job_and_the_worker_goes_on(
    client: AsyncClient,
    sessions: async_sessionmaker[AsyncSession],
    fake: FakeLive,
    error: Exception,
    shown: str,
) -> None:
    fake.fail_at, fake.error = 1, error  # the second forecast of the first job to run
    ids = [await _submit(client)]
    with as_user(OTHER):
        ids.append(await _submit(client))
    worker = jobs.Worker(sessions)
    assert await worker.run_once() and await worker.run_once()
    assert not await worker.run_once()
    rows = [await _row(sessions, i) for i in ids]
    failed = [r for r in rows if r is not None and r.status == "failed"]
    finished = [r for r in rows if r is not None and r.status == "done"]
    assert len(failed) == len(finished) == 1
    [row] = failed
    assert (row.error, row.done, len(row.results)) == (shown, 1, 1)  # partial results kept
    assert row.finished_at is not None and row.total > 1
    owner = row.owner_id or ""
    with as_user(owner):
        body = (await client.get(f"/recommendations/jobs/{row.id}")).json()
        assert (body["status"], body["error"], body["eta_s"]) == ("failed", shown, None)
        assert len(body["results"]) == 1
        retry = await client.post(URL, json=BODY)  # a failed job is not reused
        assert retry.status_code == 202 and retry.json()["job_id"] != str(row.id)


async def test_deleting_the_account_deletes_its_jobs(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession], fake: FakeLive
) -> None:
    fake.block_at = 1
    mine = await _submit(client)
    with as_user(OTHER):
        theirs = await _submit(client)
    old = datetime(2026, 1, 1, tzinfo=UTC)  # mine runs first
    async with sessions() as db:
        job = await db.get(RecommendationJob, uuid.UUID(mine))
        assert job is not None
        job.created_at = old
        await db.commit()
    task = asyncio.create_task(jobs.Worker(sessions).run_once())
    assert await asyncio.to_thread(fake.started.wait, 60)
    assert (await client.delete("/me")).status_code == 204  # while it runs
    fake.release.set()
    assert await task
    assert await _row(sessions, mine) is None  # the worker does not bring it back
    assert (await client.get(f"/recommendations/jobs/{mine}")).status_code == 404
    other = await _row(sessions, theirs)
    assert other is not None and other.status == "queued"


async def test_a_parent_batch_is_refused(client: AsyncClient) -> None:
    body = BODY | {"parent_batch_id": str(uuid.uuid4())}
    assert (await client.post(URL, json=body)).status_code == 422
    assert (await client.post(URL, json={"mode": "experimental"})).status_code == 422  # empty


def _finished(
    owner: str | None, kind: str, at: datetime, *, status: str = "done",
    request: dict[str, Any] | None = None,
) -> RecommendationJob:  # fmt: skip
    return RecommendationJob(
        owner_id=owner, kind=kind, request=request or {}, fingerprint="old", status=status,
        done=0, total=0, results=[], created_at=at, finished_at=at,
    )  # fmt: skip


async def test_a_system_job_or_another_kind_is_no_one_s_to_read(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)
    system = _finished(None, jobs.DEEP_SEARCH, at)  # no owner: a system job
    other_kind = _finished(TEST_USER_ID, "community_forecast", at)  # not a deep search
    async with sessions() as db:
        db.add_all([system, other_kind])
        await db.commit()
    for job in (system, other_kind):
        assert (await client.get(f"/recommendations/jobs/{job.id}")).status_code == 404
    assert (await client.get("/recommendations/jobs")).json() == []


async def test_an_owner_keeps_their_newest_searches(
    client: AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    async with sessions() as db:
        db.add_all([
            _finished(TEST_USER_ID, jobs.DEEP_SEARCH, t0 + timedelta(hours=i), request={"i": i},
                      status="done" if i % 2 else "failed")
            for i in range(jobs.JOBS_KEPT + 2)
        ])  # fmt: skip
        db.add(_finished(OTHER, jobs.DEEP_SEARCH, t0))
        await db.commit()
    new = await _submit(client)  # prunes in the same transaction
    listed = (await client.get("/recommendations/jobs")).json()
    assert [j["job_id"] for j in listed][:1] == [new]
    newest = range(jobs.JOBS_KEPT + 1, 2, -1)  # the 9 newest finished: 11 … 3
    assert [j["request"] for j in listed[1:]] == [{"i": i} for i in newest]
    async with sessions() as db:
        rows = (await db.execute(select(RecommendationJob))).scalars().all()
    assert sum(r.owner_id == TEST_USER_ID for r in rows) == jobs.JOBS_KEPT == len(listed)
    assert sum(r.owner_id == OTHER for r in rows) == 1  # someone else's: untouched


# ── a planned step, confirmed ───────────────────────────────────────────


def _kraut_step(*ops: S.OperatorRequest) -> dict[str, Any]:
    parent = S.library_parent(KRAUT)
    return jobs._step("screened", S.make_variant(parent, S.resolve_operators(parent, ops)))


KRAUT_PAIR = (S.OperatorRequest("add", "Fresh ginger"),
              S.OperatorRequest("swap", "Napa cabbage", "Cabbage"))  # fmt: skip


def test_a_confirmed_card_below_0_8_times_its_screened_e_says_interaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(S, "live_variant_statistics", FakeLive(zero=True))
    out = jobs.run_deep_search_step(_request(BODY), _kraut_step(*KRAUT_PAIR))
    card = RecommendationCardOut.model_validate(out["card"])
    assert card.interaction_detected is True and jobs.INTERACTION_NOTE in card.notes
    assert card.level == "Low" and out["rank"][0] == 0.0  # U − penalty = 0
    single = jobs.run_deep_search_step(_request(BODY), _kraut_step(KRAUT_PAIR[0]))
    assert single["card"]["interaction_detected"] is None  # one grid operator: exact, not screened


def test_a_saved_step_the_library_no_longer_allows_gives_no_card() -> None:
    """A plan saved before a deploy that changed the library or the grid: no card, no failure."""
    step = _kraut_step(*KRAUT_PAIR)
    dill = {"op": "add", "ingredient": "Dill", "replaces": None, "to_c": None, "fdc_id": None}
    refused = step | {"operators": [*step["operators"], dill]}  # Dill has no use level
    assert jobs.run_deep_search_step(_request(BODY), refused) is None
    retired = step | {"recipe_key": "a_recipe_no_longer_active"}
    assert jobs.run_deep_search_step(_request(BODY), retired) is None


def test_a_planned_step_is_confirmed_by_the_engine_and_logged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log = tmp_path / "candidates.jsonl"
    monkeypatch.setattr(settings, "candidates_path", str(log))
    S._LIVE.clear()
    out = jobs.run_deep_search_step(_request(BODY), _kraut_step(*KRAUT_PAIR))
    card = RecommendationCardOut.model_validate(out["card"])
    assert card.id == f"variant:{KRAUT}:add:Fresh ginger+swap:Cabbage>Napa cabbage"
    assert not card.screened and isinstance(card.interaction_detected, bool)
    assert card.temperature.model_c == card.temperature.served_c
    [line] = log.read_text(encoding="utf-8").splitlines()
    record = json.loads(line)
    assert record["kind"] == "variant" and record["parent"] == KRAUT
    assert record["operators"] == ["add:Fresh ginger", "swap:Cabbage>Napa cabbage"]
    assert record["members"] == S.FORECAST_MEMBERS
    assert TEST_USER_ID not in line  # no ids
    jobs.run_deep_search_step(_request(BODY), _kraut_step(*KRAUT_PAIR))
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1  # kept by fingerprint


# ── the registry: another kind of job (B9's community forecasts) ────────


async def test_a_registered_kind_runs_through_the_same_queue(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    finished: list[jobs.Job] = []

    async def on_done(db: AsyncSession, job: jobs.Job) -> None:
        finished.append(job)

    toy = jobs.Handler(
        plan=lambda request: list(range(request["n"])), step=lambda request, step: step * 10,
        max_steps=3, step_s=2.0, on_done=on_done,
    )  # fmt: skip
    monkeypatch.setitem(jobs.HANDLERS, "toy", toy)
    t0 = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
    async with sessions() as db:
        later = await jobs.submit(db, "toy", {"n": 2}, fingerprint="b")
        first = await jobs.submit(db, "toy", {"n": 5}, fingerprint="a")  # system jobs: no owner
        first.created_at, later.created_at = t0, t0 + timedelta(seconds=1)
        db.add(RecommendationJob(
            kind="retired", request={}, fingerprint="c", status="queued", done=0, total=0,
            results=[], created_at=t0 + timedelta(seconds=2),
        ))  # fmt: skip
        await db.commit()
        assert await jobs.eta_s(db, first) == round(2.0 * 3)  # not planned: max_steps
        assert await jobs.eta_s(db, later) == round(2.0 * 3 * 2)  # the first is ahead of it
        with pytest.raises(ValueError, match="no handler"):
            await jobs.submit(db, "unknown", {}, fingerprint="d")
    worker = jobs.Worker(sessions)
    assert await worker.run_once()  # FIFO: the oldest first
    row = await _row(sessions, first.id)
    assert row is not None
    assert (row.status, row.steps, row.total, row.done, row.results) == (
        "done", [0, 1, 2], 3, 3, [0, 10, 20]  # the plan is cut at max_steps
    )
    assert [(j.id, j.results) for j in finished] == [(first.id, [0, 10, 20])]
    assert await worker.run_once() and await worker.run_once()
    second = await _row(sessions, later.id)
    assert second is not None and (second.status, second.results) == ("done", [0, 10])
    async with sessions() as db:
        retired = (
            await db.execute(select(RecommendationJob).where(RecommendationJob.kind == "retired"))
        ).scalar_one()
    assert (retired.status, retired.error) == ("failed", jobs.FAILED_MESSAGE)  # no handler
    assert not await worker.run_once()


async def test_a_job_claimed_three_times_fails_instead_of_running_again(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The crash-loop guard: a job whose step kills the process is resumed by each restart,
    then fails."""
    ran: list[Any] = []
    toy = jobs.Handler(plan=lambda request: ran.append("plan") or [0], step=lambda r, s: s)
    monkeypatch.setitem(jobs.HANDLERS, "toy", toy)
    at = datetime(2026, 1, 1, tzinfo=UTC)
    async with sessions() as db:
        tries = [
            RecommendationJob(
                owner_id=owner, kind="toy", request={}, fingerprint="t", status="running",
                done=0, total=0, results=[], attempts=attempts, created_at=at, started_at=at,
            )
            for owner, attempts in (("alice", jobs.MAX_ATTEMPTS), ("bob", jobs.MAX_ATTEMPTS - 1))
        ]  # fmt: skip
        db.add_all(tries)
        await db.commit()
    worker = jobs.Worker(sessions)
    assert await worker.requeue() == 2  # a restart
    assert await worker.run_once() and await worker.run_once()
    alice, bob = [await _row(sessions, job.id) for job in tries]
    assert alice is not None and bob is not None
    assert (alice.status, alice.error, alice.attempts) == (
        "failed", jobs.INTERRUPTED_MESSAGE, jobs.MAX_ATTEMPTS
    )
    assert alice.finished_at is not None
    assert (bob.status, bob.attempts) == ("done", jobs.MAX_ATTEMPTS)  # its last attempt
    assert ran == ["plan"]  # bob's only


# ── the worker's loop: the app's lifespan, database errors ──────────────


@pytest_asyncio.fixture
async def file_sessions(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A file database: the worker and the requests polling it get their own connections."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}"
    file_engine = create_async_engine(url, poolclass=NullPool)
    async with file_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(file_engine, expire_on_commit=False)
    await file_engine.dispose()


async def _finish(sessions: async_sessionmaker[AsyncSession], job_id: Any) -> RecommendationJob:
    """The job once the background worker has finished it (60 s at most)."""
    for _ in range(3000):
        row = await _row(sessions, job_id)
        if row is not None and row.status in ("done", "failed"):
            return row
        await asyncio.sleep(0.02)
    raise AssertionError(f"job {job_id} did not finish: {row and row.status}")


async def test_the_app_starts_the_worker_resumes_and_runs_jobs(
    client: AsyncClient,
    file_sessions: async_sessionmaker[AsyncSession],
    fake: FakeLive,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def get_db() -> AsyncIterator[AsyncSession]:
        async with file_sessions() as session:
            yield session

    app.dependency_overrides[database.get_db] = get_db
    monkeypatch.setattr(database, "async_session_maker", file_sessions)
    then = datetime(2026, 1, 1, tzinfo=UTC)
    async with file_sessions() as db:  # left running when the previous process stopped
        left = RecommendationJob(
            owner_id=OTHER, kind=jobs.DEEP_SEARCH, request=_request(OTHER_BODY),
            fingerprint="left", status="running", done=0, total=0, results=[], attempts=1,
            created_at=then, started_at=then,
        )  # fmt: skip
        db.add(left)
        await db.commit()
    async with app.router.lifespan_context(app):
        assert jobs._running is not None
        job_id = await _submit(client)  # wakes the worker
        rows = {i: await _finish(file_sessions, i) for i in (left.id, job_id)}
        assert [(r.status, r.error) for r in rows.values()] == [("done", None)] * 2
        assert rows[left.id].attempts == 2  # resumed: its second attempt
        body = (await client.get(f"/recommendations/jobs/{job_id}")).json()
        assert body["status"] == "done" and body["results"]
    assert jobs._running is None  # stopped with the app


class FlakySessions:
    """A session factory that raises on the calls numbered in `fail_at` (the database is down
    then), like a connection that cannot be opened. The worker's calls come in a fixed order:
    0 the re-queue, 1 the queue read and claim, 2 the plan's save, 3 + i the save after step i
    (or of its failure), then the final update."""

    def __init__(self, real: async_sessionmaker[AsyncSession], fail_at: set[int]) -> None:
        self.real, self.fail_at, self.calls = real, fail_at, 0

    def __call__(self) -> AsyncSession:
        i, self.calls = self.calls, self.calls + 1
        if i in self.fail_at:
            raise OperationalError("SELECT 1", {}, Exception("the database is down"))
        return self.real()


@pytest.mark.parametrize(
    ("fail_at", "step_error_at", "ran", "attempts"),
    [
        ({1}, None, [0, 1, 2], 1),  # the queue read: nothing else will wake the worker
        ({4}, None, [0, 1, 1, 2], 2),  # the save after step 1: the job is left running
        ({4}, 1, [0, 1, 1, 2], 2),  # step 1 fails once, and so does saving that failure
    ],
    ids=["queue read", "progress save", "failure save"],
)
async def test_a_database_error_is_retried_and_the_job_resumes(
    file_sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    fail_at: set[int],
    step_error_at: int | None,
    ran: list[int],
    attempts: int,
) -> None:
    monkeypatch.setattr(jobs, "RETRY_S", 0.05)
    steps_run: list[int] = []

    def step(request: Any, s: int) -> int:
        steps_run.append(s)
        if s == step_error_at and steps_run.count(s) == 1:
            raise ValueError("a step error")
        return s * 10

    toy = jobs.Handler(plan=lambda request: [0, 1, 2], step=step)
    monkeypatch.setitem(jobs.HANDLERS, "toy", toy)
    async with file_sessions() as db:  # queued before the worker starts: no wake-up comes
        job = await jobs.submit(db, "toy", {}, fingerprint="t", owner_id="alice")
    flaky = FlakySessions(file_sessions, fail_at)
    worker = jobs.Worker(flaky)
    await worker.start()
    try:
        row = await _finish(file_sessions, job.id)
    finally:
        await worker.stop()
    assert flaky.calls > max(fail_at)  # the database did fail there
    assert (row.status, row.results, row.attempts) == ("done", [0, 10, 20], attempts)
    assert steps_run == ran  # resumed at the step cut short, not from scratch
    async with file_sessions() as db:
        assert await jobs.find_active(db, "alice") is None  # its owner can search again


# ── which database errors are retried (B8 open item O2, narrowed in B9) ──


@pytest.mark.parametrize(
    ("error", "retried"),
    [
        (OperationalError("SELECT 1", {}, Exception("server closed the connection")), True),
        (InterfaceError("SELECT 1", {}, Exception("connection is closed")), True),
        (PoolTimeoutError("QueuePool limit of size 5 overflow 10 reached"), True),
        (IntegrityError("INSERT", {}, Exception("duplicate key")), False),
        (DataError("INSERT", {}, Exception("invalid input syntax")), False),
        (ProgrammingError("SELECT", {}, Exception("no such column")), False),
        (SQLAlchemyError("a generic database error"), False),
        (ValueError("not a database error"), False),
    ],
    ids=["operational", "interface", "pool timeout", "integrity", "data", "programming",
         "generic", "other"],
)  # fmt: skip
def test_only_connection_errors_are_transient(error: Exception, retried: bool) -> None:
    assert jobs.transient(error) is retried


async def test_a_data_error_fails_its_job_at_once(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database error retrying cannot fix (here in on_done) fails the job with the generic
    message instead of resuming it again and again."""

    async def on_done(db: AsyncSession, job: jobs.Job) -> None:
        raise IntegrityError("INSERT", {}, Exception("duplicate key"))

    toy = jobs.Handler(plan=lambda request: [0, 1], step=lambda r, s: s * 10, on_done=on_done)
    monkeypatch.setitem(jobs.HANDLERS, "toy", toy)
    async with sessions() as db:
        job = await jobs.submit(db, "toy", {}, fingerprint="t", owner_id="alice")
    worker = jobs.Worker(sessions)
    assert await worker.run_once()  # no exception: nothing for the loop to retry
    row = await _row(sessions, job.id)
    assert row is not None
    assert (row.status, row.error, row.attempts, row.results) == (
        "failed", jobs.FAILED_MESSAGE, 1, [0, 10]
    )
    assert row.finished_at is not None
    assert not await worker.run_once()  # not re-queued


async def test_a_connection_error_in_a_job_is_left_for_the_loop_to_retry(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    def step(request: Any, s: int) -> int:
        raise OperationalError("SELECT 1", {}, Exception("the database is down"))

    monkeypatch.setitem(jobs.HANDLERS, "toy", jobs.Handler(plan=lambda r: [0], step=step))
    async with sessions() as db:
        job = await jobs.submit(db, "toy", {}, fingerprint="t", owner_id="alice")
    with pytest.raises(OperationalError):
        await jobs.Worker(sessions).run_once()
    row = await _row(sessions, job.id)
    assert row is not None and (row.status, row.error) == ("running", None)  # resumes later
