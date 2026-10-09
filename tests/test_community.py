"""Community recipes (build plan B9; design § 10.3): publishing a finished batch and its
automatic checks, the admin review queue, the forecast jobs (kind "community_forecast") and
their startup recompute, the "Community — not proven" section, a community recipe as an
Experimental parent and Start batch from its card, and privacy (DELETE /me detaches, GET
/me/community-recipes exports).

A live 64-member forecast takes seconds: most tests stand a fake in for it (FakeLive:
sauerkraut's grid statistics on the requested time axis, scaled per recipe title so ranking
can be steered). One test runs a forecast step on the real engine.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_recommendations_api import catalogue  # noqa: F401

from fermenttrack import database
from fermenttrack.auth import get_current_user_id
from fermenttrack.config import settings
from fermenttrack.main import app
from fermenttrack.models import (
    SAFETY_REMINDER,
    Batch,
    BatchIngredient,
    CommunityRecipe,
    CommunityRecipeForecast,
    Culture,
    FdcFood,
    FdcFoodNutrient,
    Ingredient,
    IngredientNutrient,
    Measurement,
    RecommendationJob,
    RecommendationLink,
    Reminder,
)
from fermenttrack.recommender import community as C
from fermenttrack.recommender import gate, grid, jobs, library
from fermenttrack.recommender import service as S
from fermenttrack.routers import community as community_routes
from fermenttrack.schemas import RecommendationCardOut, RecommendationsOut
from tests.conftest import TEST_USER_ID

KRAUT = "sauerkraut_dry_salted"
OTHER = "someone-else"
PERSIMMON = 169941  # USDA FDC: Persimmons, japanese, raw
KRAUT_ROWS = [("Cabbage", 1.958, "kg"), ("Salt", 42.0, "g")]  # a 2 kg batch: 979 + 21 g/kg
START = datetime(2026, 9, 1, 12, 0)
PH_LINES = [gate.PH_DEADLINE_LINE, gate.PH_LOG_LINE]


class FakeLive:
    """Stands in for service.live_variant_statistics: sauerkraut's grid statistics at that
    temperature on the requested time axis, E and U scaled by `scale[recipe title]`."""

    def __init__(self, scale: dict[str, float] | None = None) -> None:
        self.scale = scale or {}
        self.calls: list[tuple[str, float, int]] = []
        self.error: Exception | None = None  # raised by every call while set

    def __call__(
        self, recipe: library.Recipe, model_c: float, members: int, t_dst: Any, end_h: float
    ) -> tuple[grid.Entry, str, bool]:
        self.calls.append((recipe.key, model_c, members))
        if self.error is not None:
            raise self.error
        src = grid.interp_temp(KRAUT, model_c)
        k = self.scale.get(recipe.name, 1.0)

        def on(m: Any, factor: float = 1.0) -> Any:
            return type(m)({s: factor * np.interp(t_dst, src.t_h, v) for s, v in m.items()})

        entry = dataclasses.replace(
            src, recipe_key=recipe.key, temp_c=model_c, t_h=np.asarray(t_dst, dtype=float),
            e=on(src.e, k), u=on(src.u, k), p=on(src.p), members=members,
        )  # fmt: skip
        names = "|".join(sorted(i.name for i in recipe.ingredients))
        return entry, f"fake:{names}:{model_c}:{k}", True


@pytest.fixture(autouse=True)
def _no_candidates_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "candidates_path", None)
    monkeypatch.setattr(jobs, "_STEP_TIMES", {})


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeLive:
    live = FakeLive()
    monkeypatch.setattr(S, "live_variant_statistics", live)
    return live


@pytest.fixture
def as_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", TEST_USER_ID)


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


async def _ingredient(db: AsyncSession, name: str, **values: Any) -> Ingredient:
    row = Ingredient(name=name, default_role="flavoring", fermentation_systems=[], **values)
    db.add(row)
    await db.commit()
    return row


async def _batch(
    db: AsyncSession,
    ferment_type: str = "lacto_ferment",
    rows: list[tuple[str, float | None, str | None]] | None = None,
    *,
    owner: str = TEST_USER_ID,
    temps: tuple[float, ...] = (18.0, 20.0),
    ph: tuple[float, ...] = (3.6,),
    hours: float | None = 336.0,
    outcome: str = "success",
    expected: float | None = 21.0,
) -> Batch:
    """A batch of `ferment_type` with its logged rows (name, quantity, unit), temperature and
    pH readings; finished after `hours` (None: still running)."""
    culture = Culture(name=f"my {ferment_type}", type=ferment_type, owner_id=owner)
    db.add(culture)
    await db.flush()
    batch = Batch(
        culture_id=culture.id, started_at=START, current_stage="ferment", stage_entered_at=START,
        expected_temperature_c=expected, outcome=outcome,
        ended_at=None if hours is None else START + timedelta(hours=hours),
    )  # fmt: skip
    db.add(batch)
    await db.flush()
    by_name = {i.name: i for i in (await db.execute(select(Ingredient))).scalars()}
    for name, quantity, unit in KRAUT_ROWS if rows is None else rows:
        ingredient = by_name[name]
        db.add(BatchIngredient(
            batch_id=batch.id, ingredient_id=ingredient.id, quantity=quantity, unit=unit,
            role=ingredient.default_role,
        ))  # fmt: skip
    readings = [("temperature", t) for t in temps] + [("pH", p) for p in ph]
    for i, (kind, value) in enumerate(readings):
        db.add(Measurement(
            batch_id=batch.id, measured_at=START + timedelta(hours=i + 1), type=kind,
            value_numeric=value,
        ))  # fmt: skip
    await db.commit()
    return batch


async def _publish(
    client: AsyncClient, batch: Batch, title: str = "Bright kraut", pseudonym: str = "Ana"
) -> Any:
    return await client.post(
        "/community-recipes",
        json={"batch_id": str(batch.id), "title": title, "pseudonym": pseudonym},
    )


async def _drain(sessions: async_sessionmaker[AsyncSession]) -> None:
    worker = jobs.Worker(sessions)
    while await worker.run_once():
        pass


async def _approved(
    client: AsyncClient,
    db: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    title: str = "Bright kraut",
    **batch: Any,
) -> uuid.UUID:
    """A published, approved recipe whose forecast job has run (admin: the test user)."""
    resp = await _publish(client, await _batch(db, **batch), title)
    assert resp.status_code == 201, resp.text
    recipe_id = resp.json()["id"]
    approve = await client.post(f"/admin/community-recipes/{recipe_id}/approve")
    assert approve.status_code == 200, approve.text
    await _drain(sessions)
    return uuid.UUID(recipe_id)


async def _forecasts(db: AsyncSession, recipe_id: uuid.UUID) -> list[CommunityRecipeForecast]:
    found = await db.execute(
        select(CommunityRecipeForecast)
        .where(CommunityRecipeForecast.recipe_id == recipe_id)
        .order_by(CommunityRecipeForecast.temp_c)
        .execution_options(populate_existing=True)
    )
    return list(found.scalars())


async def _jobs(db: AsyncSession) -> list[RecommendationJob]:
    found = await db.execute(
        select(RecommendationJob)
        .where(RecommendationJob.kind == C.COMMUNITY_FORECAST)
        .execution_options(populate_existing=True)
    )
    return list(found.scalars())


# ── publishing (design § 10.3) ──────────────────────────────────────────


async def test_publish_normalises_a_finished_batch_to_g_per_kg(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    batch = await _batch(db_session)
    resp = await _publish(client, batch, "  Bright kraut ", "  Ana López ")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["notice"] == C.PRIVACY_NOTICE
    assert "stays in the library if you delete your account" in body["notice"]
    assert (body["title"], body["pseudonym"], body["status"], body["reason"]) == (
        "Bright kraut", "Ana López", "pending", None,
    )  # fmt: skip
    assert body["fermentation_type"] == "lacto_ferment"
    # 1.958 kg + 42 g = 2 kg: g/kg of the weighed total
    assert body["ingredients"] == [
        {"name": "Cabbage", "role": "base", "g_per_kg": 979.0, "fdc_id": None, "label": None},
        {"name": "Salt", "role": "additive", "g_per_kg": 21.0, "fdc_id": None, "label": None},
    ]
    assert body["temperature_c"] == 19.0  # the mean of the logged 18 and 20 °C, not 21
    assert body["duration_h"] == 336.0  # its actual duration
    row = await db_session.get(CommunityRecipe, uuid.UUID(body["id"]))
    assert row is not None
    assert (row.owner_id, row.source_batch_id, row.reviewed_at) == (TEST_USER_ID, batch.id, None)


async def test_publish_falls_back_to_the_expected_temperature(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    resp = await _publish(client, await _batch(db_session, temps=(), expected=21.5))
    assert resp.status_code == 201, resp.text
    assert resp.json()["temperature_c"] == 21.5


async def test_anonymous_accounts_may_publish(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    """An anonymous Supabase session has a user id like any other (auth.py): no extra rule."""
    anon = "anon-3f2b9c"
    batch = await _batch(db_session, owner=anon)
    with as_user(anon):
        resp = await _publish(client, batch)
        assert resp.status_code == 201, resp.text
        assert [r["id"] for r in (await client.get("/me/community-recipes")).json()] == [
            resp.json()["id"]
        ]


@pytest.mark.parametrize(
    ("batch", "reason"),
    [
        ({"hours": None, "outcome": "in_progress"}, "only a finished batch can be published"),
        ({"outcome": "in_progress"}, "record its outcome as a success"),
        ({"outcome": "failed"}, "record its outcome as a success"),
        ({"ph": ()}, "log a pH reading of 4.6 or below"),
        ({"ph": (4.7, 4.61)}, "log a pH reading of 4.6 or below"),
        ({"ph": (1.5, 15.0)}, "log a pH reading of 4.6 or below"),  # implausible readings
        ({"rows": [("Cabbage", 990.0, "g"), ("Salt", 10.0, "g")]}, "SALT-001: salt 1.00 % w/w"),
        ({"temps": (46.0,)}, "TEMP-001: 46 °C > 45 °C"),
        ({"temps": (), "expected": None}, "no temperature"),
        (
            {"rows": [("Cabbage", 979.0, "g"), ("Salt", 2.0, "cup")]},
            "no usable quantity (missing, not positive, or in an unknown unit): Salt",
        ),
        (
            {"rows": [("Cabbage", 979.0, "g"), ("Salt", None, "g")]},
            "no usable quantity (missing, not positive, or in an unknown unit): Salt",
        ),
        ({"ferment_type": "generic"}, "has no forecast profile (a generic type)"),
        ({"ferment_type": "sourdough"}, "sourdough recipes are shared through the levain planner"),
        (
            {"ferment_type": "miso", "ph": (), "temps": (25.0,), "rows": [
                ("White rice", 414.4, "g"), ("Soybeans", 414.4, "g"), ("Water", 131.3, "g"),
                ("Salt", 39.9, "g"),
            ]},
            "SALT-BARRIER: salt 3.99 % w/w < 4.0 %",
        ),
    ],
    ids=[
        "unfinished", "no outcome", "failed outcome", "no pH", "pH above 4.6", "pH implausible",
        "salt too low", "too hot", "no temperature", "unknown unit", "no quantity",
        "generic type", "sourdough", "miso below 4 % salt",
    ],
)  # fmt: skip
async def test_each_automatic_check_refuses_with_its_reason(
    client: AsyncClient,
    db_session: AsyncSession,
    catalogue: None,  # noqa: F811
    batch: dict[str, Any],
    reason: str,
) -> None:
    resp = await _publish(client, await _batch(db_session, **batch))
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["message"] == "This batch cannot be published yet."
    assert any(reason in r for r in detail["reasons"]), detail["reasons"]
    assert (await db_session.execute(select(CommunityRecipe))).first() is None


async def test_every_reason_is_given_at_once(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    resp = await _publish(client, await _batch(db_session, ph=(), outcome="in_progress"))
    assert resp.status_code == 422
    assert len(resp.json()["detail"]["reasons"]) == 2  # the pH and the outcome


async def test_retired_and_unknown_ingredients_are_named(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    await _ingredient(db_session, "Fruit", is_active=False)  # retired in v3
    await _ingredient(db_session, "Grandma's spice mix")  # a user's own, not in the catalogue
    rows = [("Cabbage", 950.0, "g"), ("Salt", 21.0, "g"), ("Fruit", 20.0, "g"),
            ("Grandma's spice mix", 9.0, "g")]  # fmt: skip
    resp = await _publish(client, await _batch(db_session, rows=rows))
    assert resp.status_code == 422
    assert resp.json()["detail"]["reasons"] == [
        "retired ingredients, replace them with current ones: Fruit",
        "not in the ingredient catalogue: Grandma's spice mix",
    ]


async def test_a_usda_pick_is_kept_with_its_nutrients_and_labelled(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    persimmon = await _ingredient(db_session, "Persimmons, japanese, raw", fdc_id=PERSIMMON)
    db_session.add_all(
        IngredientNutrient(
            ingredient_id=persimmon.id, nutrient=n, amount_per_100g=v, source="usda_fdc",
            source_food_id=str(PERSIMMON), source_version="test",
        )
        for n, v in (("water", 80.3), ("sugars_total", 12.5))
    )  # fmt: skip
    await db_session.commit()
    rows = [("Cabbage", 950.0, "g"), ("Salt", 21.0, "g"), ("Persimmons, japanese, raw", 29.0, "g")]
    resp = await _publish(client, await _batch(db_session, rows=rows))
    assert resp.status_code == 201, resp.text
    usda = next(i for i in resp.json()["ingredients"] if i["fdc_id"] == PERSIMMON)
    assert (usda["g_per_kg"], usda["label"]) == (29.0, "USDA food: aroma effect unknown")
    row = await db_session.get(CommunityRecipe, uuid.UUID(resp.json()["id"]))
    assert row is not None
    stored = next(r for r in row.recipe if r["fdc_id"] == PERSIMMON)
    assert stored["nutrients"] == [["sugars_total", 12.5], ["water", 80.3]]
    recipe = C.candidate(C.stored(row)).recipe
    as_row = next(i for i in recipe.ingredients if i.fdc_id == PERSIMMON)
    assert as_row.nutrients == (("sugars_total", 12.5), ("water", 80.3))
    assert as_row.label == C.USDA_LABEL


def test_masses_balance_to_1000_g_per_kg_within_5_percent() -> None:
    for total, ok in ((949.9, False), (950.0, True), (1050.0, True), (1050.1, False)):
        assert C.mass_balanced([{"g_per_kg": total}]) is ok, total
    assert not C.mass_balanced([{"g_per_kg": float("nan")}])
    # thirds of an odd total: each rounded to 0.01 g/kg, the rows still balance
    third = C.LoggedRow("Cabbage", 1.0, "g", "base", True)
    rows, reasons = C.normalise([third, dataclasses.replace(third, name="Salt"), third])
    assert reasons == [] and [r["g_per_kg"] for r in rows] == [333.33] * 3
    assert C.mass_balanced(rows)


def test_the_feedback_check_is_one_function_b10_switches() -> None:
    """Until the tasting form (B10), publishing needs the batch's outcome to be a success."""
    end = START + timedelta(hours=1)
    base = C.SourceBatch("lacto_ferment", (), (), 20.0, (), START, end, "success")
    assert C.publish_checks_feedback(base) == []
    for outcome in (None, "", "in_progress", "failed", "discarded"):
        assert C.publish_checks_feedback(dataclasses.replace(base, outcome=outcome)) == [
            "only a batch that turned out well is shared: record its outcome as a success"
        ]


def test_only_plausible_readings_logged_during_the_batch_count() -> None:
    """The mean temperature and the pH evidence ignore readings outside the engine's
    TEMP_RANGE_C, a "pH" below 2 or above 14, and readings logged before the batch started
    or after it ended."""
    end = START + timedelta(hours=100)
    during, before = START + timedelta(hours=5), START - timedelta(hours=1)
    after = end + timedelta(hours=1)
    batch = C.SourceBatch(
        "lacto_ferment", (),
        ((during, 18.0), (during, 20.0), (during, 75.0), (during, -10.0), (during, float("nan")),
         (before, 30.0), (after, 30.0)),
        21.0, (), START, end, "success",
    )  # fmt: skip
    assert C.mean_temperature(batch) == 19.0
    assert C.mean_temperature(dataclasses.replace(batch, temperatures=((before, 18.0),))) == 21.0
    assert C.mean_temperature(
        dataclasses.replace(batch, temperatures=(), expected_temperature_c=99.0)
    ) is None  # an implausible expected temperature is no temperature either
    assert C.mean_temperature(dataclasses.replace(batch, temperatures=((end, 22.0),))) == 22.0
    for readings, ok in (
        (((during, 4.6),), True), (((START, 3.5),), True), (((end, 2.0),), True),
        (((during, 4.61),), False), (((during, 1.99),), False), (((during, 0.0),), False),
        (((during, -1.0),), False), (((during, 15.0),), False), (((during, float("nan")),), False),
        (((before, 3.5),), False), (((after, 3.5),), False),
    ):  # fmt: skip
        assert C.ph_evidence(dataclasses.replace(batch, ph=readings)) is ok, readings


async def test_a_ph_logged_after_the_batch_ended_is_no_evidence(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    batch = await _batch(db_session, ph=())
    db_session.add(Measurement(
        batch_id=batch.id, measured_at=START + timedelta(hours=400), type="pH", value_numeric=3.6,
    ))  # fmt: skip
    await db_session.commit()
    resp = await _publish(client, batch)
    assert resp.status_code == 422
    assert any("log a pH reading of 4.6 or below" in r for r in resp.json()["detail"]["reasons"])


async def test_someone_else_s_batch_is_404(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    resp = await _publish(client, await _batch(db_session, owner=OTHER))
    assert resp.status_code == 404
    assert (await db_session.execute(select(CommunityRecipe))).first() is None


async def test_a_batch_is_published_once_until_rejected(
    client: AsyncClient, db_session: AsyncSession, catalogue: None, as_admin: None  # noqa: F811
) -> None:
    batch = await _batch(db_session)
    first = await _publish(client, batch)
    assert first.status_code == 201
    assert (await _publish(client, batch, "Again")).status_code == 409
    reject = {"reason": "Add the brine method to the title"}
    url = f"/admin/community-recipes/{first.json()['id']}/reject"
    assert (await client.post(url, json=reject)).status_code == 200
    assert (await _publish(client, batch, "Bright kraut, brined")).status_code == 201


async def test_two_simultaneous_publishes_of_a_batch_give_one_recipe(
    client: AsyncClient,
    db_session: AsyncSession,
    catalogue: None,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second request passed the "already published?" check before the first committed:
    the partial unique index refuses its insert, a 409."""
    batch = await _batch(db_session)
    assert (await _publish(client, batch)).status_code == 201

    async def not_yet(db: AsyncSession, batch_id: uuid.UUID) -> bool:
        return False

    monkeypatch.setattr(community_routes, "_published", not_yet)
    resp = await _publish(client, batch, "Racing")
    assert (resp.status_code, resp.json()["detail"]) == (409, community_routes.ALREADY_PUBLISHED)
    titles = (await db_session.execute(select(CommunityRecipe.title))).scalars().all()
    assert titles == ["Bright kraut"]


@pytest.mark.parametrize(
    "pseudonym", ["", " ", "A", "x" * 41, "ana@example.com", "https://x.io", "<b>Ana</b>", "-Ana"]
)
async def test_the_pseudonym_is_validated(
    client: AsyncClient, db_session: AsyncSession, catalogue: None, pseudonym: str  # noqa: F811
) -> None:
    resp = await _publish(client, await _batch(db_session), pseudonym=pseudonym)
    assert resp.status_code == 422, pseudonym


async def test_the_title_is_required_and_bounded(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    batch = await _batch(db_session)
    for title in ("", "   ", "t" * 121):
        assert (await _publish(client, batch, title)).status_code == 422, title


# ── the review queue (admins) and the forecast jobs ─────────────────────


async def test_the_review_queue_is_admins_only(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    rid = (await _publish(client, await _batch(db_session))).json()["id"]
    assert (await client.get("/admin/community-recipes")).status_code == 403
    assert (await client.post(f"/admin/community-recipes/{rid}/approve")).status_code == 403
    reject = await client.post(f"/admin/community-recipes/{rid}/reject", json={"reason": "no"})
    assert reject.status_code == 403
    row = await db_session.get(CommunityRecipe, uuid.UUID(rid))
    assert row is not None and row.status == "pending"
    assert await _jobs(db_session) == []


async def test_approval_queues_one_job_whose_forecasts_are_stored(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    batch = await _batch(db_session)
    rid = (await _publish(client, batch)).json()["id"]
    queue = (await client.get("/admin/community-recipes")).json()
    assert [(r["id"], r["owner_id"], r["source_batch_id"]) for r in queue] == [
        (rid, TEST_USER_ID, str(batch.id))
    ]
    assert (await client.post("/admin/community-recipes/nope/approve")).status_code == 422
    unknown = await client.post(f"/admin/community-recipes/{uuid.uuid4()}/approve")
    assert unknown.status_code == 404

    resp = await client.post(f"/admin/community-recipes/{rid}/approve")
    assert resp.status_code == 200, resp.text
    assert (resp.json()["status"], resp.json()["reviewed_by"]) == ("approved", TEST_USER_ID)
    assert resp.json()["reviewed_at"] is not None
    assert resp.json()["forecast_job"]["status"] == "queued"
    assert queue[0]["forecast_job"] is None  # pending: never queued
    assert (await client.get("/admin/community-recipes")).json() == []  # no longer pending
    approved = (await client.get("/admin/community-recipes?status=approved")).json()
    assert [r["id"] for r in approved] == [rid]
    assert (await client.post(f"/admin/community-recipes/{rid}/approve")).status_code == 200
    queued = await _jobs(db_session)
    assert len(queued) == 1  # approving again queues no second job while one is active
    job = queued[0]
    assert (job.owner_id, job.status, job.fingerprint) == (
        None, "queued", f"{C.COMMUNITY_FORECAST}:{rid}",
    )  # fmt: skip
    # a system job: no user sees it
    assert (await client.get(f"/recommendations/jobs/{job.id}")).status_code == 404

    await _drain(sessions)
    (job,) = await _jobs(db_session)
    assert (job.status, job.error) == ("done", None)
    row = await db_session.get(CommunityRecipe, uuid.UUID(rid))
    assert row is not None
    recipe = C.candidate(C.stored(row)).recipe
    temps = C.forecast_temperatures(recipe)
    assert temps == (16.0, 19.0, 24.0)  # the profile's 16-24 °C, its 20 °C replaced by 19 °C
    stored = await _forecasts(db_session, row.id)
    assert [f.temp_c for f in stored] == list(temps)
    assert {f.grid_version for f in stored} == {grid.version()}
    assert fake.calls == [(recipe.key, t, S.FORECAST_MEMBERS) for t in temps]
    t_axis, _ = C.axis(recipe)
    for f in stored:  # the grid's statistics on the recipe's own time axis
        entry = C.entry_from_json(recipe.key, f.stats)
        assert f.stats["t_h"] == [C._num(x) for x in t_axis]
        assert set(entry.e) == set(entry.u) == set(entry.p) and "sour" in entry.e
        assert all(len(v) == len(t_axis) for v in entry.e.values())
        assert "ph_below_4_6" in entry.milestones
        assert C.entry_json(entry) == f.stats  # a lossless round trip


async def test_a_recipe_rejected_before_its_job_ran_keeps_no_forecast(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    rid = (await _publish(client, await _batch(db_session))).json()["id"]
    await client.post(f"/admin/community-recipes/{rid}/approve")
    no_reason = await client.post(f"/admin/community-recipes/{rid}/reject", json={})
    assert no_reason.status_code == 422
    assert (await client.post(f"/admin/community-recipes/{rid}/reject")).status_code == 422
    reject = await client.post(
        f"/admin/community-recipes/{rid}/reject", json={"reason": "  Too close to the library "}
    )
    assert (reject.json()["status"], reject.json()["reason"]) == (
        "rejected", "Too close to the library"
    )  # fmt: skip
    await _drain(sessions)
    assert await _forecasts(db_session, uuid.UUID(rid)) == []
    mine = (await client.get("/me/community-recipes")).json()
    assert [(r["status"], r["reason"]) for r in mine] == [("rejected", "Too close to the library")]


async def test_a_forecast_step_on_the_real_engine(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    rid = (await _publish(client, await _batch(db_session))).json()["id"]
    row = await db_session.get(CommunityRecipe, uuid.UUID(rid))
    assert row is not None
    request = C.job_request(row, grid.version())
    assert request["grid_version"] == grid.version()
    assert C.plan_forecasts(request) == [{"temp_c": 16.0}, {"temp_c": 19.0}, {"temp_c": 24.0}]
    result = C.run_forecast_step(request, {"temp_c": 19.0})
    assert (result["temp_c"], result["grid_version"]) == (19.0, grid.version())
    stats = result["stats"]
    assert stats["members"] == S.FORECAST_MEMBERS and stats["temp_c"] == 19.0
    t_axis, _ = C.axis(C.candidate(C.stored(row)).recipe)
    assert len(stats["t_h"]) == len(t_axis) and len(stats["e"]["sour"]) == len(t_axis)
    assert all(0.0 <= x <= 1.0 for x in stats["e"]["sour"] if x is not None)
    assert set(stats["milestones"]) >= {"ph_below_4_6"}


# ── startup recompute ───────────────────────────────────────────────────


async def test_startup_recomputes_stale_forecasts_once(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    current = await _approved(client, db_session, sessions, "Current")
    old = await _approved(client, db_session, sessions, "Old grid")
    for f in await _forecasts(db_session, old):
        f.grid_version = "an-older-grid"
    missing = await _approved(client, db_session, sessions, "Never forecast")
    for f in await _forecasts(db_session, missing):
        await db_session.delete(f)
    pending = (await _publish(client, await _batch(db_session), "Pending")).json()["id"]
    await db_session.commit()

    assert await C.enqueue_stale(sessions) == 2
    queued = {j.fingerprint for j in await _jobs(db_session) if j.status == "queued"}
    assert queued == {C.job_fingerprint(old), C.job_fingerprint(missing)}
    assert await C.enqueue_stale(sessions) == 0  # their jobs are queued: no second one
    await C.recompute_at_startup(sessions)
    assert len([j for j in await _jobs(db_session) if j.status == "queued"]) == 2

    await _drain(sessions)
    for rid in (current, old, missing):
        assert {f.grid_version for f in await _forecasts(db_session, rid)} == {grid.version()}
    assert await _forecasts(db_session, uuid.UUID(pending)) == []
    finished = await _jobs(db_session)
    assert len(finished) == 3  # each recipe keeps its newest finished job only
    assert await C.enqueue_stale(sessions) == 0


async def test_a_job_that_failed_on_this_grid_waits_for_a_reapproval_or_a_new_grid(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake.error = S.RecommendationError("the engine cannot run this recipe")
    rid = await _approved(client, db_session, sessions)
    (job,) = await _jobs(db_session)
    assert (job.status, job.error) == ("failed", "the engine cannot run this recipe")
    assert await _forecasts(db_session, rid) == []
    assert await C.enqueue_stale(sessions) == 0  # it would only fail again on this grid
    (item,) = (await client.get("/admin/community-recipes?status=approved")).json()
    assert item["forecast_job"] | {"finished_at": None} == {
        "id": str(job.id), "status": "failed", "error": "the engine cannot run this recipe",
        "done": 0, "total": 3, "finished_at": None,
    }  # fmt: skip

    again = await client.post(f"/admin/community-recipes/{rid}/approve")  # the admin retries
    assert again.json()["forecast_job"]["status"] == "queued"
    await _drain(sessions)
    assert [j.status for j in await _jobs(db_session)] == ["failed", "failed"]
    assert await C.enqueue_stale(sessions) == 0

    with monkeypatch.context() as m:  # a new grid version: worth another try
        m.setattr(grid, "version", lambda: "a-newer-grid")
        assert await C.enqueue_stale(sessions) == 1
    fake.error = None
    await _drain(sessions)
    assert {f.grid_version for f in await _forecasts(db_session, rid)} == {grid.version()}
    (item,) = (await client.get("/admin/community-recipes?status=approved")).json()
    assert (item["forecast_job"]["status"], item["forecast_job"]["error"]) == ("done", None)
    assert len(await _jobs(db_session)) == 1  # the done job replaced the failed ones


async def test_the_startup_recompute_retries_connection_errors_only(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "RETRY_S", 0.0)
    errors: list[Exception] = [OperationalError("SELECT 1", {}, Exception("the database is down"))]
    calls: list[int] = []

    async def enqueue_stale(_: Any) -> int:
        calls.append(1)
        if errors:
            raise errors.pop()
        return 0

    monkeypatch.setattr(C, "enqueue_stale", enqueue_stale)
    await C.recompute_at_startup(sessions)
    assert len(calls) == 2  # retried once the database answered
    errors.append(IntegrityError("INSERT", {}, Exception("a data error")))
    calls.clear()
    await C.recompute_at_startup(sessions)
    assert len(calls) == 1  # logged, not retried


async def test_the_app_registers_the_job_kind_and_recomputes_at_startup(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert jobs.HANDLERS[C.COMMUNITY_FORECAST].on_done is C.store_forecasts
    started: list[Any] = []

    async def recompute(factory: Any) -> None:
        started.append(factory)

    monkeypatch.setattr(C, "recompute_at_startup", recompute)
    monkeypatch.setattr(database, "async_session_maker", sessions)
    async with app.router.lifespan_context(app):
        assert jobs._running is not None
        for _ in range(100):  # the recompute is a task of its own
            if started:
                break
            await asyncio.sleep(0.01)
    assert started == [sessions]
    assert jobs._running is None


# ── the "Community — not proven" section ────────────────────────────────


def _community(body: dict[str, Any]) -> list[dict[str, Any]]:
    return list(body["community"]["cards"])


async def test_the_community_section_ranks_labels_and_counts_its_batches(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    fake.scale.update({"Bright": 1.0, "Twin A": 0.6, "Twin B": 0.6, "Faint": 0.3})
    ids = {t: await _approved(client, db_session, sessions, t) for t in fake.scale}
    pending = await _publish(client, await _batch(db_session), "Pending one")
    assert pending.status_code == 201
    # someone else started Twin B (twice: one person): "made 1×", ahead of Twin A at the same
    # E(peak); the author's own batch from Bright counts for nothing
    start = {"community_recipe_id": str(ids["Twin B"]), "tastes": ["sour"]}
    with as_user(OTHER):
        for _ in range(2):
            started = await client.post("/batches/from-recommendation", json=start)
            assert started.status_code == 201
    own = start | {"community_recipe_id": str(ids["Bright"])}
    assert (await client.post("/batches/from-recommendation", json=own)).status_code == 201

    ask = {"tastes": ["sour"], "mode": "proven"}
    body = (await client.post("/recommendations", json=ask)).json()
    RecommendationsOut.model_validate(body)
    cards = _community(body)
    assert [c["community"]["title"] for c in cards] == ["Bright", "Twin B", "Twin A"]
    assert [c["community"]["made"] for c in cards] == [0, 1, 0]
    assert [c["level"] for c in cards][0] == "High"
    bright = cards[0]
    RecommendationCardOut.model_validate(bright)
    assert bright["id"] == f"community:{ids['Bright']}"
    assert (bright["section"], bright["source_kind"], bright["recipe_key"]) == (
        "community", "community", None,
    )  # fmt: skip
    assert bright["community"] == {
        "id": str(ids["Bright"]), "title": "Bright", "pseudonym": "Ana", "made": 0,
        "mean_liking": None,
    }  # fmt: skip
    labels = bright["trust"]["labels"]
    assert labels[:3] == [*S.CARD_LABELS, C.SECTION_LABEL] and C.SECTION_LABEL == (
        "Community — not proven"
    )
    assert "single-value source, widened" in labels
    assert bright["safety_lines"] == PH_LINES
    # Q26: the publishing temperature, its ± 3 °C span as the slider (inside TEMP-001)
    assert bright["recipe"]["temperature_c"] == 19.0
    assert (bright["temperature"]["served_c"], bright["temperature"]["slider"]) == (
        19.0, {"min_c": 16.0, "max_c": 22.0},
    )  # fmt: skip
    # § 6 in mode community: the published 336 h ± 30 % as the documented span
    window = bright["window"]
    assert 0.7 * 336 - 1e-6 <= window["taste_from_h"] <= window["peak_h"] <= window["stop_by_h"]
    assert window["stop_by_h"] <= 1.3 * 336 + 1e-6
    assert {i["name"]: i["grams"] for i in bright["recipe"]["ingredients"]} == {
        "Cabbage": 979.0, "Salt": 21.0,
    }  # fmt: skip

    both = (await client.post("/recommendations", json=ask | {"mode": "both"})).json()
    assert [c["id"] for c in _community(both)] == [c["id"] for c in cards]
    experimental = await client.post("/recommendations", json=ask | {"mode": "experimental"})
    assert experimental.json()["community"] is None
    ginger = {"ingredients": ["Fresh ginger"], "mode": "proven"}
    none = (await client.post("/recommendations", json=ginger)).json()["community"]
    assert none == {"cards": [], "message": C.NO_MATCH}


async def test_a_community_recipe_that_cannot_be_served_is_left_out(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _approved(client, db_session, sessions, "Good")
    corrupt = await _approved(client, db_session, sessions, "Corrupt")
    broken = await _approved(client, db_session, sessions, "Broken")
    for f in await _forecasts(db_session, corrupt):
        f.stats = {"t_h": "not a series"}  # unreadable
    await db_session.commit()
    card = C.community_card

    def failing(c: C.Candidate, *args: Any, **kwargs: Any) -> Any:
        if c.title == "Broken":
            raise RuntimeError("an engine fault")
        return card(c, *args, **kwargs)

    monkeypatch.setattr(C, "community_card", failing)
    with caplog.at_level(logging.ERROR, logger=C.__name__):
        resp = await client.post("/recommendations", json={"tastes": ["sour"], "mode": "both"})
    assert resp.status_code == 200, resp.text
    assert [c["community"]["title"] for c in _community(resp.json())] == ["Good"]
    assert resp.json()["proven"]["cards"]  # the rest of the response is untouched
    logged = [r.getMessage() for r in caplog.records]
    assert f"community recipe {corrupt} cannot be read: left out" in logged
    assert f"community recipe {broken}: its card is left out" in logged


def _candidate(title: str, made: int, liking: float | None, temp_c: float = 19.0) -> C.Candidate:
    rows = ({"name": "Cabbage", "role": "base", "g_per_kg": 979.0},
            {"name": "Salt", "role": "additive", "g_per_kg": 21.0})  # fmt: skip
    recipe = C.as_recipe(title, title, "lacto_ferment", rows, temp_c, 336.0)
    t_dst, end = C.axis(recipe)
    entries = tuple(
        FakeLive()(recipe, t, S.FORECAST_MEMBERS, t_dst, end)[0]
        for t in C.forecast_temperatures(recipe)
    )
    return C.Candidate(uuid.uuid4(), title, "Ana", recipe, entries, made, liking)


def test_the_section_ranks_by_e_then_made_then_mean_liking() -> None:
    cands = [
        _candidate("Liked less", 2, 3.0), _candidate("Liked more", 2, 4.5),
        _candidate("Made more", 3, None), _candidate("Unrated", 2, None),
    ]  # fmt: skip
    body = C.section(cands, [], [], ["sour"], None)
    assert [c["community"]["title"] for c in body["cards"]] == [
        "Made more", "Liked more", "Liked less",
    ]  # fmt: skip
    assert C.section([dataclasses.replace(cands[0], forecasts=())], [], [], ["sour"], None) == {
        "cards": [], "message": C.NO_MATCH
    }  # a recipe without forecasts of the current grid is left out


def test_a_community_card_s_temperature_is_clamped_by_the_safety_limits() -> None:
    """Q26: the documented span is the publishing temperature ± 3 °C, within the safety
    limits: a lacto ferment published at 43 °C slides 40-45 °C (TEMP-001)."""
    hot = _candidate("Hot", 0, None, temp_c=43.0)
    card = C.community_card(hot, (), None, 1000.0)
    assert card is not None
    assert (card.temperature.served_c, card.temperature.slider_c) == (43.0, (40.0, 45.0))
    assert card.temperature.source_only  # outside the profile's 16-24 °C: the source's window
    asked = C.community_card(hot, (), 50.0, 1000.0)
    assert asked is not None and asked.temperature.served_c == 45.0


# ── a community recipe as an Experimental parent; its card's forecast ───


async def test_a_community_recipe_is_an_experimental_parent(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    rid = await _approved(client, db_session, sessions, "Bright kraut")
    fake.calls.clear()
    ask = {"tastes": ["sour"], "mode": "experimental", "community_recipe_id": str(rid)}
    resp = await client.post("/recommendations", json=ask)
    assert resp.status_code == 200, resp.text
    cards = resp.json()["experimental"]["cards"]
    mine, *library_cards = cards
    assert (mine["section"], mine["source_kind"], mine["recipe_key"]) == (
        "experimental", "community", None,
    )  # fmt: skip
    assert mine["id"].startswith(f"community:{rid}:")
    assert mine["parent"] | {"name": None} == {
        "kind": "community", "recipe_key": None, "batch_id": None,
        "community_recipe_id": str(rid), "name": None,
        "label": "community recipe “Bright kraut” by Ana",
    }  # fmt: skip
    assert "Experimental — departs from community recipe “Bright kraut” by Ana" in (
        mine["trust"]["labels"]
    )
    assert mine["safety_lines"] == PH_LINES and len(cards) <= 3
    assert 2 <= len(fake.calls) <= 1 + S.OWN_BATCH_VARIANTS  # live: the recipe, then variants
    assert all(c["source_kind"] == "variant" for c in library_cards)
    assert resp.json()["community"] is None  # mode experimental lists no community section

    pending = (await _publish(client, await _batch(db_session), "Pending")).json()["id"]
    for unknown in (pending, str(uuid.uuid4())):
        refused = ask | {"community_recipe_id": unknown}
        assert (await client.post("/recommendations", json=refused)).status_code == 404
    proven = await client.post("/recommendations", json=ask | {"mode": "proven"})
    assert proven.status_code == 422  # a parent needs mode experimental or both
    both = ask | {"parent_batch_id": str(uuid.uuid4()), "mode": "both"}
    assert (await client.post("/recommendations", json=both)).status_code == 422


async def test_the_live_forecast_of_a_community_card_and_its_variant(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    rid = await _approved(client, db_session, sessions)
    ask = {"community_recipe_id": str(rid), "tastes": ["sour"], "temperature_c": 21.0}
    resp = await client.post("/recommendations/forecast", json=ask)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["source_kind"], body["recipe_key"], body["members"]) == (
        "community", None, S.FORECAST_MEMBERS,
    )  # fmt: skip
    assert body["temperature"]["served_c"] == 21.0 and body["safety_lines"] == PH_LINES
    assert body["level"] in ("Low", "Med", "High") and body["bands"][0]["key"] == "sour"
    variant = ask | {"operators": [{"op": "temperature", "to_c": 24.0}]}
    resp = await client.post("/recommendations/forecast", json=variant)
    assert resp.status_code == 200, resp.text
    assert resp.json()["source_kind"] == "community" and resp.json()["operators"][0]["to_c"] == 24
    deep = {"tastes": ["sour"], "mode": "experimental", "community_recipe_id": str(rid)}
    assert (await client.post("/recommendations/deep-search", json=deep)).status_code == 422


# ── Start batch from a community card ───────────────────────────────────


async def test_start_batch_from_a_community_card(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    rid = await _approved(client, db_session, sessions)
    fake.calls.clear()
    payload = {"community_recipe_id": str(rid), "tastes": ["sour"], "batch_g": 2000}
    resp = await client.post("/batches/from-recommendation", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    link = body["link"]
    assert (link["source_kind"], link["community_recipe_id"], link["recipe_key"]) == (
        "community", str(rid), None,
    )  # fmt: skip
    assert link["parent_batch_id"] is None and link["operators"] == []
    assert link["grid_version"] == grid.version() and link["temperature_c"] == 19.0
    assert fake.calls == []  # booked from its stored forecasts
    assert body["batch"]["expected_temperature_c"] == 19.0
    assert body["culture"]["name"] == "Bright kraut (community)"
    booked = await db_session.execute(
        select(Ingredient.name, BatchIngredient.quantity)
        .join(Ingredient, BatchIngredient.ingredient_id == Ingredient.id)
        .where(BatchIngredient.batch_id == uuid.UUID(body["batch"]["id"]))
    )
    assert dict(booked.tuples().all()) == {"Cabbage": 1958.0, "Salt": 42.0}
    reminders = (
        await db_session.execute(
            select(Reminder).where(Reminder.batch_id == uuid.UUID(body["batch"]["id"]))
        )
    ).scalars()  # fmt: skip
    assert SAFETY_REMINDER in {r.kind for r in reminders}  # an acid-safety type: the pH reminder

    variant = payload | {"operators": [{"op": "temperature", "to_c": 24.0}], "mode": "experimental"}
    resp = await client.post("/batches/from-recommendation", json=variant)
    assert resp.status_code == 201, resp.text
    link = resp.json()["link"]
    assert (link["source_kind"], link["community_recipe_id"]) == ("community", str(rid))
    assert link["operators"][0]["key"] == "temp:24"
    assert resp.json()["batch"]["expected_temperature_c"] == 24.0
    made = await db_session.execute(
        select(RecommendationLink).where(RecommendationLink.community_recipe_id == rid)
    )
    assert len(made.scalars().all()) == 2

    pending = (await _publish(client, await _batch(db_session), "Pending")).json()["id"]
    refused = await client.post(
        "/batches/from-recommendation", json=payload | {"community_recipe_id": pending}
    )
    assert refused.status_code == 404


async def test_start_batch_runs_live_when_the_forecasts_are_not_of_this_grid(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    rid = await _approved(client, db_session, sessions)
    for f in await _forecasts(db_session, rid):
        f.grid_version = "an-older-grid"
    await db_session.commit()
    body = (await client.post("/recommendations", json={"tastes": ["sour"]})).json()
    assert _community(body) == []  # only forecasts of the current grid are served
    fake.calls.clear()
    resp = await client.post("/batches/from-recommendation", json={"community_recipe_id": str(rid)})
    assert resp.status_code == 201, resp.text
    assert [m for _, _, m in fake.calls] == [S.FORECAST_MEMBERS]


# ── privacy: DELETE /me detaches, GET /me/community-recipes exports ─────


async def test_start_batch_from_a_community_recipe_with_a_usda_row(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    name = "Persimmons, japanese, raw"
    db_session.add(FdcFood(
        fdc_id=PERSIMMON, data_type="SR Legacy", description=name,
        category="Fruits and Fruit Juices",
        nutrients=[FdcFoodNutrient(nutrient="water", amount_per_100g=80.32)],
    ))  # fmt: skip
    persimmon = await _ingredient(db_session, name, fdc_id=PERSIMMON)  # the publisher's pick
    db_session.add(IngredientNutrient(
        ingredient_id=persimmon.id, nutrient="water", amount_per_100g=80.32, source="usda_fdc",
        source_food_id=str(PERSIMMON), source_version="test",
    ))  # fmt: skip
    await db_session.commit()
    rows = [("Cabbage", 950.0, "g"), ("Salt", 21.0, "g"), (name, 29.0, "g")]
    rid = await _approved(client, db_session, sessions, rows=rows)

    card = _community((await client.post("/recommendations", json={"tastes": ["sour"]})).json())[0]
    usda = next(i for i in card["recipe"]["ingredients"] if i["fdc_id"] == PERSIMMON)
    assert (usda["grams"], usda["label"], usda["in_catalogue"]) == (29.0, C.USDA_LABEL, True)
    payload = {"community_recipe_id": str(rid), "tastes": ["sour"], "batch_g": 2000}
    resp = await client.post("/batches/from-recommendation", json=payload)
    assert resp.status_code == 201, resp.text
    assert resp.json()["skipped_ingredients"] == []
    booked = await db_session.execute(
        select(Ingredient.name, BatchIngredient.quantity, BatchIngredient.role, Ingredient.fdc_id)
        .join(Ingredient, BatchIngredient.ingredient_id == Ingredient.id)
        .where(BatchIngredient.batch_id == uuid.UUID(resp.json()["batch"]["id"]))
    )
    assert {n: (q, r, f) for n, q, r, f in booked.tuples()} == {
        "Cabbage": (1900.0, "base", None), "Salt": (42.0, "additive", None),
        name: (58.0, "flavoring", PERSIMMON),  # the same USDA ingredient, booked like a pick
    }  # fmt: skip
    assert resp.json()["link"]["community_recipe_id"] == str(rid)


async def test_an_admin_s_account_deletion_removes_their_id_from_reviews(
    client: AsyncClient, db_session: AsyncSession, catalogue: None, as_admin: None  # noqa: F811
) -> None:
    theirs = await _batch(db_session, owner=OTHER)
    with as_user(OTHER):
        rid = (await _publish(client, theirs, "Theirs", "Bo")).json()["id"]
    reject = {"reason": "Duplicate"}
    assert (await client.post(f"/admin/community-recipes/{rid}/reject", json=reject)).is_success
    assert (await client.delete("/me")).status_code == 204  # the admin leaves
    row = (
        await db_session.execute(
            select(CommunityRecipe).execution_options(populate_existing=True)
        )
    ).scalar_one()  # fmt: skip
    assert (row.reviewed_by, row.status, row.reason, row.owner_id) == (
        None, "rejected", "Duplicate", OTHER,
    )  # fmt: skip
    assert row.reviewed_at is not None


async def test_deleting_the_account_detaches_its_recipes(
    client: AsyncClient,
    db_session: AsyncSession,
    sessions: async_sessionmaker[AsyncSession],
    catalogue: None,  # noqa: F811
    as_admin: None,
    fake: FakeLive,
) -> None:
    approved = await _approved(client, db_session, sessions)
    pending = uuid.UUID((await _publish(client, await _batch(db_session), "Pending")).json()["id"])
    theirs = await _batch(db_session, owner=OTHER)
    with as_user(OTHER):
        other = uuid.UUID((await _publish(client, theirs, "Theirs", "Bo")).json()["id"])
    assert (await client.delete("/me")).status_code == 204

    rows = {
        r.id: r
        for r in (
            await db_session.execute(
                select(CommunityRecipe).execution_options(populate_existing=True)
            )
        ).scalars()
    }  # fmt: skip
    assert set(rows) == {approved, pending, other}  # the recipes stay in the library
    for rid in (approved, pending):
        assert (rows[rid].owner_id, rows[rid].source_batch_id, rows[rid].pseudonym) == (
            None, None, "Ana",
        )  # fmt: skip
    assert (rows[other].owner_id, rows[other].source_batch_id) == (OTHER, theirs.id)
    assert (await db_session.execute(select(Batch).where(Batch.id != theirs.id))).first() is None
    assert (await client.get("/me/community-recipes")).json() == []
    body = (await client.post("/recommendations", json={"tastes": ["sour"]})).json()
    assert [c["community"]["id"] for c in _community(body)] == [str(approved)]  # still served


async def test_my_community_recipes_lists_every_status_newest_first(
    client: AsyncClient, db_session: AsyncSession, catalogue: None, as_admin: None  # noqa: F811
) -> None:
    ids = []
    for title in ("First", "Second", "Third"):
        ids.append((await _publish(client, await _batch(db_session), title)).json()["id"])
    t0 = datetime(2026, 9, 20)
    for i, rid in enumerate(ids):
        row = await db_session.get(CommunityRecipe, uuid.UUID(rid))
        assert row is not None
        row.created_at = t0 + timedelta(days=i)
    await db_session.commit()
    await client.post(f"/admin/community-recipes/{ids[1]}/reject", json={"reason": "Duplicate"})
    with as_user(OTHER):
        await _publish(client, await _batch(db_session, owner=OTHER), "Theirs")
        assert [r["title"] for r in (await client.get("/me/community-recipes")).json()] == [
            "Theirs"
        ]
    mine = (await client.get("/me/community-recipes")).json()
    assert [(r["title"], r["status"], r["reason"]) for r in mine] == [
        ("Third", "pending", None), ("Second", "rejected", "Duplicate"), ("First", "pending", None),
    ]  # fmt: skip
    assert mine[0]["ingredients"][0] == {
        "name": "Cabbage", "role": "base", "g_per_kg": 979.0, "fdc_id": None, "label": None,
    }  # fmt: skip
    assert "owner_id" not in mine[0]  # the export is yours; the admin view adds the owner


# ── the salt-barrier minimum on every path ──────────────────────────────


def test_a_miso_below_4_percent_salt_has_no_variant_and_no_card() -> None:
    """The gate's miso minimum holds for an own batch's variants and a community card alike
    (Proven: test_recommender_gate; publishing: the "miso below 4 % salt" refusal)."""
    rows = (
        S.OwnBatchRow("White rice", 414.4, "base", ()),
        S.OwnBatchRow("Soybeans", 414.4, "base", ()),
        S.OwnBatchRow("Water", 131.3, "base", ()),
        S.OwnBatchRow("Salt", 39.9, "additive", ()),
    )
    own = S.own_parent(S.OwnBatch(str(uuid.uuid4()), 1, "my miso", "miso", rows, 25.0, 480.0))
    assert S.own_batch_cards(own, [], [], None) == []  # no variant passes: nothing runs live
    stored = [{"name": r.name, "role": r.role, "g_per_kg": r.grams} for r in rows]
    recipe = C.as_recipe("m", "Low-salt miso", "miso", stored, 25.0, 480.0)
    assert C.forecast_temperatures(recipe) == ()  # nothing to approve or forecast
    live = _candidate("any", 0, None).forecasts[0]
    cand = C.Candidate(uuid.uuid4(), "Low-salt miso", "Ana", recipe, (live,), 0, None)
    assert C.community_card(cand, (), None, 1000.0) is None
    assert C.community_card(cand, (), None, 1000.0, stats=live) is None
