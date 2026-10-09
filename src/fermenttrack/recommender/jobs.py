"""Background recommender jobs (design § 10.2, Q19, Q28): a FIFO queue persisted in
recommendation_jobs, drained by one in-process asyncio worker; and the deep search it runs.

**Worker** (generic by job kind):
- `Worker(sessions, handlers)` is started by the app's lifespan (main.py) with the app's
  session factory (tests pass their own). Idle, it awaits an asyncio.Event, set by `notify()`
  once a job is committed (`submit` does it): no polling, no busy loop, nothing to keep the
  instance awake (Render's free instance sleeps when idle).
- It claims the oldest queued job (by created_at; a conditional UPDATE to running), plans it
  once (`Handler.plan`: the request -> at most `max_steps` JSON steps, saved in `steps`), then
  runs the steps one by one (`Handler.step`), saving `done` and the merged results
  (`Handler.merge`) after each: partial results are readable while it runs. Plans and steps
  run in a worker thread, never on the event loop; the engine's solve lock
  (prediction.service) serialises them with the API's own forecasts, one solve at a time.
- A step that raises fails the job: status failed, `error` (the message of the handler's own
  `errors`, else a generic one; details are logged), its partial results kept. The worker
  then takes the next job.
- **Resume** (the loop's first act, and its retry): jobs left running (the instance slept or
  restarted) go back to queued, still ahead of newer jobs, and continue from their saved
  progress: the saved plan, from step `done` (the step that was cut short runs again); a job
  cut short before its plan was saved is planned anew. A job whose row is deleted meanwhile
  (DELETE /me) is dropped.
- **Database errors**: a connection error (`transient`: OperationalError, InterfaceError or a
  pool timeout) while reading the queue or saving progress or a failure is the database's,
  not the job's: the loop logs it, waits
  RETRY_S (or for a new job), re-queues the jobs left running (the worker is idle then: any
  running row is its own orphan) and drains again, so a job resumes from its saved progress
  instead of staying queued or running. Any other database error in a job (a data or
  integrity error, e.g. in `Handler.on_done`) cannot be fixed by retrying: it fails the job
  with the generic message, like a step's own error.
- **Crash-loop guard**: every claim counts an attempt; a job claimed MAX_ATTEMPTS times (cut
  short by restarts, e.g. a step that kills the process) fails instead of running again.
- One process (Render's free plan): the claim is conditional, so a queued job is never taken
  twice, but the re-queue assumes no other process is running jobs. During a Render deploy the
  old and new instances overlap briefly, and the new one may re-queue and run a job the old one
  is finishing: harmless (the same steps give the same results; the last write wins).
- `eta_s`: the remaining steps (and while queued, those of every active job ahead of it) times
  the mean time per step of each kind in this process, the handler's prior counted as one step.

**Registry** (B9 adds community forecasts): `register(kind, Handler(plan, step, ...))`, then
`submit(db, kind, request, fingerprint=fingerprint(kind, request), owner_id=None)`. System jobs
have no owner; at most one job per owner is queued or running (a partial unique index).
`Handler.on_done(db, job)` runs in the transaction that marks the job done (e.g. to store its
results elsewhere). `Handler.version` is part of the fingerprint: bump it when the plan or the
steps change their results. `Handler.kept`: at most that many jobs per owner, so submitting one
deletes all but the newest kept − 1 finished ones (in the same transaction).

**Deep search** (kind "deep_search", POST /recommendations/deep-search): at most 20 live
64-member forecasts (FORECAST_MEMBERS) of Experimental variants of library parents, in design
§ 10.2's order. Sourdough parents are left out: their timing comes from the planner, which has
no live engine forecast here (POST /recommendations/forecast hands them off too).
1. **The best screened combinations not yet confirmed**: per parent, the first
   SCREENED_PER_PARENT screened combinations (2–3 operators, or a (v) must-include ingredient)
   that pass the gate, in B7's pre-ranking order (service._prerank; with no targets, the tie
   keys), scored on the grid and ranked across parents like the Experimental section (§ 5.4:
   U − penalty, ...). The user's USDA foods are step 3's: screening gives them no effect, so
   here they would only repeat their parent.
2. **2 extra temperatures per top parent** (the parents of the Experimental section's 3 cards):
   its best variant with the temperature moved by operator (iii) to the 2 temperatures that
   (iii) allows (inside the profile's range, outside the documented span, through the gate)
   farthest from every temperature the grid holds for it (`extra_temperatures`).
3. **The user's USDA foods** (operator v): for each, the best variant holding it.
(2) and (3) keep their places; (1) fills the rest. Each step is the variant's live forecast
(kept by fingerprint in service._live_variant), turned into a card exactly like those of POST
/recommendations (service.card_json), now confirmed: never "screened", and for a screened
combination `interaction_detected` (the confirmed E(peak) below 0.8 × the screened one). A fresh
forecast is logged as a grid and emulator candidate (service.log_candidate: no ids). The cards
are re-ranked (§ 5.4 Experimental) after each step. A step whose variant the gate now refuses,
or whose recipe or operators the library no longer allows (a saved plan resumed after a
deploy), counts as done with no card. An owner keeps their JOBS_KEPT newest searches.

**Results are kept under the request's fingerprint** (`deep_search_fingerprint`: the request
without `mode`, which does not change the results; the grid, the model and the plan's version):
the owner's repeat of a request whose job is done gets that job back at once.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import math
import time
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fermenttrack.models import (
    ACTIVE_JOB_STATUSES,
    JOB_DONE,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    RecommendationJob,
)
from fermenttrack.prediction import service as engine
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import grid, library, operators, run, service
from fermenttrack.recommender.library import Recipe
from fermenttrack.recommender.operators import Operator

logger = logging.getLogger(__name__)

DEFAULT_MAX_STEPS = 20
DEFAULT_STEP_S = 15.0  # a 64-member forecast on a 0.1-CPU instance (design § 10.2's message)
FAILED_MESSAGE = "The search stopped on an internal error."
RETRY_S = 30.0  # after a database error: wait this long (or for a new job), then try again
MAX_ATTEMPTS = 3  # claims of one job (restarts included) before it fails instead
INTERRUPTED_MESSAGE = "The search was interrupted too many times and has stopped."


# ── the worker, generic by job kind ─────────────────────────────────────


@dataclass(frozen=True)
class Job:
    """A job as its handler sees it: a snapshot of its row."""

    id: uuid.UUID
    kind: str
    owner_id: str | None
    request: Mapping[str, Any]
    steps: list[Any] | None
    done: int
    results: list[Any]


def _append(results: list[Any], result: Any) -> list[Any]:
    return results if result is None else [*results, result]


@dataclass(frozen=True)
class Handler:
    """How the worker runs one kind of job. plan and step are synchronous and run in a worker
    thread; everything they take and return is JSON."""

    plan: Callable[[Mapping[str, Any]], Sequence[Any]]  # the request -> its steps
    step: Callable[[Mapping[str, Any], Any], Any]  # (the request, one step) -> a result or None
    merge: Callable[[list[Any], Any], list[Any]] = _append  # results so far + one result
    max_steps: int = DEFAULT_MAX_STEPS  # a longer plan is cut here
    step_s: float = DEFAULT_STEP_S  # the prior time per step, for eta_s
    errors: tuple[type[Exception], ...] = ()  # their message is shown as the job's error
    on_done: Callable[[AsyncSession, Job], Awaitable[None]] | None = None
    version: int = 1  # in the fingerprint: bump it when plan or step change their results
    kept: int | None = None  # jobs kept per owner (None: all)


HANDLERS: dict[str, Handler] = {}
_STEP_TIMES: dict[str, tuple[int, float]] = {}  # kind -> (steps timed, their seconds)
_running: Worker | None = None  # the app's worker, woken by notify()


def register(kind: str, handler: Handler) -> None:
    HANDLERS[kind] = handler


def step_seconds(kind: str) -> float:
    """The mean time per step of this kind so far in this process, the handler's prior counted
    as one step (a single cached step cannot bring the estimate to zero)."""
    handler = HANDLERS.get(kind)
    prior = handler.step_s if handler else DEFAULT_STEP_S
    n, seconds = _STEP_TIMES.get(kind, (0, 0.0))
    return (prior + seconds) / (1 + n)


def _timed(kind: str, seconds: float) -> None:
    n, total = _STEP_TIMES.get(kind, (0, 0.0))
    _STEP_TIMES[kind] = (n + 1, total + seconds)


def _now() -> datetime:
    return datetime.now(UTC)


def transient(exc: BaseException) -> bool:
    """A database error worth retrying: the connection, not the data (B8 open item O2): an
    OperationalError (lost or refused connection), an InterfaceError, or a pool timeout. Any
    other database error (integrity, data, programming) is not: retrying cannot fix it."""
    return isinstance(exc, OperationalError | InterfaceError | PoolTimeoutError)


def notify() -> None:
    """Wake the app's worker; call it once a queued job is committed."""
    if _running is not None:
        _running.notify()


def fingerprint(kind: str, request: Mapping[str, Any]) -> str:
    """sha256 of the kind and its handler's version, the request (canonical JSON), the grid
    version and the engine's model version: the same request on the same grid, model and plan
    gives the same results. The first call loads the grid: call it off the event loop."""
    handler = HANDLERS.get(kind)
    body = {
        "kind": kind, "version": handler.version if handler else None, "request": request,
        "grid": grid.version(), "model": engine.MODEL_VERSION,
    }  # fmt: skip
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def submit(
    db: AsyncSession,
    kind: str,
    request: Mapping[str, Any],
    *,
    fingerprint: str,
    owner_id: str | None = None,
) -> RecommendationJob:
    """Queue a job (committed) and wake the worker; with Handler.kept, the owner's older
    finished jobs of this kind go in the same transaction. Raises IntegrityError (rolled back)
    when the owner already has a queued or running job, and ValueError for a kind without a
    handler."""
    handler = HANDLERS.get(kind)
    if handler is None:
        raise ValueError(f"no handler for job kind {kind!r}")
    if owner_id is not None and handler.kept is not None:
        finished = await db.execute(
            select(RecommendationJob.id)
            .where(
                RecommendationJob.owner_id == owner_id, RecommendationJob.kind == kind,
                RecommendationJob.status.not_in(ACTIVE_JOB_STATUSES),
            )
            .order_by(RecommendationJob.created_at.desc(), RecommendationJob.id.desc())
        )  # fmt: skip
        old = list(finished.scalars())[max(handler.kept - 1, 0) :]
        if old:
            await db.execute(delete(RecommendationJob).where(RecommendationJob.id.in_(old)))
    job = RecommendationJob(
        owner_id=owner_id, kind=kind, request=dict(request), fingerprint=fingerprint,
        status=JOB_QUEUED, done=0, total=0, results=[], attempts=0, created_at=_now(),
    )  # fmt: skip
    db.add(job)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise
    notify()
    return job


async def find_active(db: AsyncSession, owner_id: str) -> RecommendationJob | None:
    found = await db.execute(
        select(RecommendationJob)
        .where(
            RecommendationJob.owner_id == owner_id,
            RecommendationJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .limit(1)
    )
    return found.scalar_one_or_none()


async def find_done(
    db: AsyncSession, owner_id: str, kind: str, fingerprint: str
) -> RecommendationJob | None:
    """The owner's latest finished job of this kind and fingerprint (its results are kept)."""
    found = await db.execute(
        select(RecommendationJob)
        .where(
            RecommendationJob.owner_id == owner_id,
            RecommendationJob.kind == kind,
            RecommendationJob.fingerprint == fingerprint,
            RecommendationJob.status == JOB_DONE,
        )
        .order_by(RecommendationJob.finished_at.desc())
        .limit(1)
    )
    return found.scalar_one_or_none()


async def eta_s(db: AsyncSession, job: RecommendationJob) -> int | None:
    """Seconds left for an active job (None once finished): its remaining steps and, while
    queued, those of every active job ahead of it, each at its kind's step_seconds. A job not
    planned yet counts its handler's max_steps."""
    if job.status not in ACTIVE_JOB_STATUSES:
        return None
    rows: list[tuple[str, list[Any] | None, int, int]] = [
        (job.kind, job.steps, job.total, job.done)
    ]
    if job.status == JOB_QUEUED:
        ahead = await db.execute(
            select(
                RecommendationJob.kind, RecommendationJob.steps, RecommendationJob.total,
                RecommendationJob.done,
            ).where(
                RecommendationJob.status.in_(ACTIVE_JOB_STATUSES),
                RecommendationJob.created_at < job.created_at,
            )
        )  # fmt: skip
        rows += [(k, s, t, d) for k, s, t, d in ahead.tuples()]
    seconds = 0.0
    for kind, steps, total, done in rows:
        handler = HANDLERS.get(kind)
        left = (handler.max_steps if handler else DEFAULT_MAX_STEPS) if steps is None else total
        seconds += step_seconds(kind) * max(left - done, 0)
    return round(seconds)


class Worker:
    """The single in-process worker (see the module docstring)."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        handlers: Mapping[str, Handler] = HANDLERS,
    ) -> None:
        self._sessions = sessions
        self._handlers = handlers
        self._wake = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Drain the queue in the background, starting with the jobs a previous process left
        running (resume). Never touches the database itself: the app starts even when the
        database is not reachable yet (the loop retries)."""
        global _running
        self._task = asyncio.create_task(self._loop(), name="recommendation-jobs")
        _running = self

    async def stop(self) -> None:
        """Stop at once. A job cut short stays running in the table and resumes at the next
        start; the thread of a step in progress finishes on its own."""
        global _running
        if _running is self:
            _running = None
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def notify(self) -> None:
        self._wake.set()

    async def requeue(self) -> int:
        """Jobs left running go back to the queue (resume); the number re-queued. Only while
        this worker runs no job: then a running row is an orphan."""
        async with self._sessions() as db:
            moved = await db.execute(
                update(RecommendationJob)
                .where(RecommendationJob.status == JOB_RUNNING)
                .values(status=JOB_QUEUED)
            )
            await db.commit()
        return cast(CursorResult[Any], moved).rowcount

    async def _loop(self) -> None:
        orphans = True  # at startup: the jobs a previous process left running
        while True:
            self._wake.clear()  # before reading the queue: a job committed meanwhile re-sets it
            try:
                if orphans:
                    await self.requeue()
                    orphans = False
                while await self.run_once():
                    pass
            except Exception:
                # the database (the queue, a save): retry later, re-queuing first the job
                # it left running, which then resumes from its saved progress
                logger.exception("recommendation jobs: retrying in %g s", RETRY_S)
                orphans = True
            if orphans:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), RETRY_S)
            else:
                await self._wake.wait()

    async def run_once(self) -> bool:
        """Run the oldest queued job to its end (done or failed). False: the queue is empty. A
        job already claimed MAX_ATTEMPTS times fails instead (the crash-loop guard)."""
        async with self._sessions() as db:
            row = (
                await db.execute(
                    select(RecommendationJob)
                    .where(RecommendationJob.status == JOB_QUEUED)
                    .order_by(RecommendationJob.created_at, RecommendationJob.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            job = Job(
                row.id, row.kind, row.owner_id, row.request, row.steps, row.done,
                list(row.results),
            )  # fmt: skip
            queued = (RecommendationJob.id == job.id, RecommendationJob.status == JOB_QUEUED)
            if row.attempts >= MAX_ATTEMPTS:
                logger.warning("recommendation job %s: %d attempts, failed", job.id, row.attempts)
                await db.execute(
                    update(RecommendationJob).where(*queued).values(
                        status=JOB_FAILED, error=INTERRUPTED_MESSAGE, finished_at=_now()
                    )
                )
                await db.commit()
                return True
            claim = await db.execute(
                update(RecommendationJob).where(*queued).values(
                    status=JOB_RUNNING, attempts=row.attempts + 1,
                    started_at=row.started_at or _now(),
                )
            )  # fmt: skip
            await db.commit()
        if cast(CursorResult[Any], claim).rowcount == 1:
            await self._run(job)
        return True

    async def _save(self, job_id: uuid.UUID, **values: Any) -> bool:
        """Update the job's row; False when it is gone (deleted with its owner's account)."""
        async with self._sessions() as db:
            saved = await db.execute(
                update(RecommendationJob).where(RecommendationJob.id == job_id).values(**values)
            )
            await db.commit()
        if cast(CursorResult[Any], saved).rowcount != 1:
            logger.info("recommendation job %s was deleted while it ran", job_id)
            return False
        return True

    async def _run(self, job: Job) -> None:
        handler = self._handlers.get(job.kind)
        try:
            if handler is None:
                raise LookupError(f"no handler for job kind {job.kind!r}")
            steps = job.steps
            if steps is None:
                planned = await asyncio.to_thread(handler.plan, job.request)
                steps = list(planned)[: handler.max_steps]
                if not await self._save(job.id, steps=steps, total=len(steps)):
                    return
            results = list(job.results)
            for i in range(job.done, len(steps)):
                started = time.monotonic()
                result = await asyncio.to_thread(handler.step, job.request, steps[i])
                _timed(job.kind, time.monotonic() - started)
                results = handler.merge(results, result)
                if not await self._save(job.id, done=i + 1, results=results):
                    return
            async with self._sessions() as db:
                if handler.on_done is not None:
                    finished = replace(job, steps=steps, done=len(steps), results=results)
                    await handler.on_done(db, finished)
                await db.execute(
                    update(RecommendationJob)
                    .where(RecommendationJob.id == job.id)
                    .values(status=JOB_DONE, finished_at=_now())
                )
                await db.commit()
        except Exception as exc:
            if transient(exc):
                raise  # the database's connection, not the job: the loop retries, the job resumes
            if handler is not None and isinstance(exc, handler.errors):
                logger.warning("recommendation job %s failed: %s", job.id, exc)
                error = str(exc) or FAILED_MESSAGE
            else:  # its own error, or a database error retrying cannot fix (data, integrity)
                logger.exception("recommendation job %s failed", job.id)
                error = FAILED_MESSAGE
            await self._save(job.id, status=JOB_FAILED, error=error, finished_at=_now())


# ── deep search (design § 10.2) ─────────────────────────────────────────

DEEP_SEARCH = "deep_search"
DEEP_SEARCH_VERSION = 1  # the plan and its steps (in the fingerprint): bump on a change
JOBS_KEPT = 10  # an owner's newest deep searches kept (the active one included)
MAX_FORECASTS = 20  # design § 10.2
SCREENED_PER_PARENT = 4  # step 1: screened combinations taken per parent, best first
EXTRA_TEMPERATURES = 2  # step 2: per top parent
TEMPERATURE_STEP_C = 0.5  # step 2: the temperatures considered
INTERACTION_NOTE = (
    f"{service.INTERACTION}: the confirmed forecast is below {service.INTERACTION_RATIO:g} × "
    "the screened one"
)  # as POST /recommendations/forecast words it


@dataclass(frozen=True)
class Query:
    """A deep search's request (validated as schemas.RecommendationRequest on submission)."""

    listed: tuple[str, ...]
    targets: tuple[service.Target, ...]
    temperature_c: float | None
    batch_g: float
    usda_ids: tuple[int, ...]


def query(request: Mapping[str, Any]) -> Query:
    return Query(
        listed=tuple(dict.fromkeys(request.get("ingredients") or ())),
        targets=service.parse_targets(request.get("aromas") or (), request.get("tastes") or ()),
        temperature_c=request.get("temperature_c"),
        batch_g=float(request.get("batch_g") or service.DEFAULT_BATCH_G),
        usda_ids=tuple(dict.fromkeys(request.get("usda_fdc_ids") or ())),
    )


def extra_temperatures(
    recipe: Recipe, also: Iterable[float] = (), n: int = EXTRA_TEMPERATURES
) -> tuple[float, ...]:
    """Up to n temperatures for operator (iii) that the grid knows least about: on a 0.5 °C
    lattice of the profile's range, those (iii) allows (operators.temperature_ok: outside the
    documented span, through the gate), picked one at a time farthest from every temperature
    the grid holds for the recipe (its own and its temperature operators'), from `also` and
    from those already picked; ties go to the cooler one."""
    lo, hi = PROFILES[recipe.fermentation_type].temp_range
    known = [*grid.axis(recipe.key), *also]
    lattice = [
        k * TEMPERATURE_STEP_C
        for k in range(math.ceil(lo / TEMPERATURE_STEP_C), math.floor(hi / TEMPERATURE_STEP_C) + 1)
    ]  # fmt: skip
    allowed = [t for t in lattice if operators.temperature_ok(recipe, t)]
    picked: list[float] = []
    for _ in range(n):
        gaps = {t: min((abs(t - k) for k in known), default=math.inf) for t in allowed}
        free = [t for t, gap in gaps.items() if gap > 1e-9]
        if not free:
            break
        best = max(free, key=lambda t: (gaps[t], -t))
        picked.append(best)
        known.append(best)
    return tuple(picked)


def _ordered(
    parent: service.Parent,
    combos: Sequence[tuple[Operator, ...]],
    q: Query,
    reference: service.Reference,
) -> list[tuple[Operator, ...]]:
    """The parent's combinations, best first, as the Experimental section orders them
    (service.best_variant): B7's pre-ranking with targets, else the tie keys."""
    if q.targets:
        rank = service._prerank(parent, combos, q.targets, q.temperature_c, reference)
        return [combos[i] for i in rank]

    def cheap(combo: tuple[Operator, ...]) -> tuple[int, int, str]:
        v = service.make_variant(parent, combo)
        return len(service.to_buy(v.recipe, q.listed)), len(combo), v.id

    return sorted(combos, key=cheap)


def _scan(
    parent: service.Parent,
    order: Sequence[tuple[Operator, ...]],
    q: Query,
    reference: service.Reference,
) -> tuple[service.Card | None, list[service.Card], dict[int, service.Card]]:
    """One pass over the parent's combinations, best first, scoring (on the grid) only what is
    needed: (its best variant as the Experimental section picks it, the best of the first
    EXACT_PER_PARENT that pass the gate; its first SCREENED_PER_PARENT screened ones that pass,
    without the user's USDA foods (step 3's, and screening gives them no effect); per USDA food
    of the request, the first that passes and holds it)."""
    exact: list[service.Card] = []
    screened: list[service.Card] = []
    foods: dict[int, service.Card] = {}
    wanted = set(q.usda_ids)
    for combo in order:
        v = service.make_variant(parent, combo)
        picked = {op.fdc_id for op in combo if op.fdc_id is not None}
        need_exact = len(exact) < service.EXACT_PER_PARENT
        need_screened = v.screened and not picked and len(screened) < SCREENED_PER_PARENT
        held = (picked & wanted) - foods.keys()
        if not (need_exact or need_screened or held):
            continue
        card, _ = service.variant_card(
            v, q.targets, q.temperature_c, q.batch_g, q.listed, reference
        )
        if card is None:
            continue
        if need_exact:
            exact.append(card)
        if need_screened:
            screened.append(card)
        foods |= dict.fromkeys(held, card)
    best = min(exact, key=service.experimental_rank_key) if exact else None
    return best, screened, foods


def _other_temperatures(card: service.Card, q: Query) -> list[service.Variant]:
    """Step 2: the card's variant with its temperature moved to extra_temperatures (one
    operator more, so a variant that already has 3 others has none)."""
    v = card.variant
    assert v is not None
    keep = tuple(op for op in v.operators if op.kind != "temperature")
    if len(keep) >= operators.MAX_OPERATORS:
        return []
    moved = v.temperature_op
    also = () if moved is None or moved.to_c is None else (moved.to_c,)
    out = []
    for t in extra_temperatures(v.parent.recipe, also):
        try:
            w = service.make_variant(v.parent, (*keep, Operator("temperature", to_c=t)))
        except service.OperatorRefused:
            continue
        if service.variant_gate(w, service.variant_temperature(w, q.temperature_c)).ok:
            out.append(w)
    return out


def _step(stage: str, v: service.Variant) -> dict[str, Any]:
    """A planned forecast: the variant as its operator chips name it (resolved again, against
    the parent's own operators, when it runs)."""
    return {
        "stage": stage,
        "id": v.id,
        "recipe_key": v.parent.recipe.key,
        "operators": [
            {
                "op": op.kind, "ingredient": None if op.fdc_id is not None else op.ingredient,
                "replaces": op.replaces, "to_c": op.to_c, "fdc_id": op.fdc_id,
            }
            for op in v.operators
        ],  # fmt: skip
    }


def plan_deep_search(request: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The deep search's forecasts, in design § 10.2's order (see the module docstring)."""
    q = query(request)
    best: list[service.Card] = []
    picks: list[service.Card] = []
    by_food: dict[int, list[service.Card]] = {}
    for recipe in library.active():
        if recipe.handoff == "planner":
            continue
        parent = service.Parent(recipe, "library", recipe.name)
        combos = service._combos(parent, q.listed, q.temperature_c, q.usda_ids)
        if not combos:
            continue
        reference = service.library_reference(recipe, q.temperature_c)
        top, screened, foods = _scan(parent, _ordered(parent, combos, q, reference), q, reference)
        if top is not None:
            best.append(top)
        picks += screened
        for fdc_id, card in foods.items():
            by_food.setdefault(fdc_id, []).append(card)
    rank = service.experimental_rank_key
    best.sort(key=rank)
    picks.sort(key=rank)
    moved = [w for card in best[: service.CARDS_PER_SECTION] for w in _other_temperatures(card, q)]
    food_cards = [min(by_food[f], key=rank) for f in q.usda_ids if f in by_food]
    chosen = picks[: max(MAX_FORECASTS - len(moved) - len(food_cards), 0)]
    steps = [
        *(_step("screened", c.variant) for c in chosen if c.variant),
        *(_step("temperature", w) for w in moved),
        *(_step("usda", c.variant) for c in food_cards if c.variant),
    ]
    unique = {s["id"]: s for s in reversed(steps)}  # the first of each variant
    return [s for s in steps if unique[s["id"]] is s][:MAX_FORECASTS]


def run_deep_search_step(request: Mapping[str, Any], step: Mapping[str, Any]) -> Any:
    """One planned forecast: the confirmed card and its § 5.4 Experimental rank key, or None
    when the variant is no longer served: the gate refuses it, or (a saved plan resumed after a
    library or grid change) its recipe or operators are no longer allowed."""
    q = query(request)
    asked = tuple(
        service.OperatorRequest(o["op"], o["ingredient"], o["replaces"], o["to_c"], o["fdc_id"])
        for o in step["operators"]
    )
    try:
        parent = service.library_parent(step["recipe_key"])
        v = service.make_variant(parent, service.resolve_operators(parent, asked))
    except service.RecommendationError as exc:
        logger.info("deep search step %s is no longer allowed: %s", step["id"], exc)
        return None
    temp = service.variant_temperature(v, q.temperature_c)
    if not service.variant_gate(v, temp).ok:
        return None
    members = service.FORECAST_MEMBERS
    v, stats, fp, fresh, reference = service._live_variant(v, temp, members, q.temperature_c)
    card, _ = service.variant_card(
        v, q.targets, q.temperature_c, q.batch_g, q.listed, reference, stats=stats
    )
    if card is None:
        return None
    screened_e = None
    if v.screened and q.targets:
        basis = service.grid_basis(v.parent.recipe, temp.recipe_c)
        screened_e = service.evaluate(
            v.recipe, service.screened_statistics(v, temp), temp, q.targets,
            mode="experimental", reference=reference, basis=basis,
        ).e  # fmt: skip
    e = card.evaluation.e
    interaction = None
    if screened_e is not None and e is not None:
        interaction = e < service.INTERACTION_RATIO * screened_e
    if fresh:
        service.log_candidate(service.candidate_record(v, stats, fp, card.evaluation, screened_e))
    body = service.card_json(card) | {"interaction_detected": interaction}
    if interaction:
        body["notes"] = [*body["notes"], INTERACTION_NOTE]
    return {"rank": list(service.experimental_rank_key(card)), "card": body}


def _ranked(results: list[Any], result: Any) -> list[Any]:
    """§ 5.4 Experimental over the confirmed cards so far."""
    return results if result is None else sorted([*results, result], key=lambda r: r["rank"])


def deep_search_fingerprint(request: Mapping[str, Any]) -> str:
    """fingerprint() of a deep search's request without its `mode`: the search runs the
    Experimental variants whatever the mode."""
    return fingerprint(DEEP_SEARCH, {k: v for k, v in request.items() if k != "mode"})


register(
    DEEP_SEARCH,
    Handler(
        plan=plan_deep_search, step=run_deep_search_step, merge=_ranked,
        max_steps=MAX_FORECASTS, step_s=DEFAULT_STEP_S,
        errors=(service.RecommendationError, engine.PredictionUnavailable, run.RecipeError),
        version=DEEP_SEARCH_VERSION, kept=JOBS_KEPT,
    ),
)  # fmt: skip
