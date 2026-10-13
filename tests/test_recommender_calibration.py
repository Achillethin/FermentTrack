"""The calibration gate (build plan B11; design § 13.2): the observations a tasting gives (P at
its time, inside the card's axis only; noticed = rating ≥ 1), the leave-one-batch-out baseline,
the batch-level bootstrap and its pass rule, the reliability bins; the stored reports, the
startup and weekly recompute and the admin trigger; GET /recommendations/calibration (aggregates
only); and the cards' numbers, shown only while the latest report passes."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import pytest
from httpx import AsyncClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_community import as_user
from test_recommendations_api import catalogue  # noqa: F401

from fermenttrack import database
from fermenttrack.auth import get_current_user_id
from fermenttrack.config import settings
from fermenttrack.main import app
from fermenttrack.models import Batch, CalibrationReport, Culture, RecommendationLink, Tasting
from fermenttrack.recommender import calibration as K
from fermenttrack.recommender import community as C
from fermenttrack.recommender import grid, jobs, library
from fermenttrack.recommender import service as S
from fermenttrack.schemas import CalibrationReportOut
from tests.conftest import TEST_USER_ID

LACTO = "lacto_ferment"
KIMCHI = "napa_kimchi_room_temp"
KRAUT = "sauerkraut_dry_salted"
OTHER = "someone-else"
NOTE = "Grandma's secret: tasted it in the cellar"
NOW = datetime(2026, 10, 13, 9, 0, tzinfo=UTC)
START = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
AXIS = [0.0, 10.0, 20.0]
ASK = {"ingredients": ["Napa cabbage"], "aromas": ["pungent"], "tastes": ["sour"], "mode": "both"}
REPORT_KEYS = {
    "computed_at", "n_tastings", "n_observations", "n_batches", "brier_model", "brier_baseline",
    "diff", "ci_low", "ci_high", "auc", "auc_low", "passed", "reason", "bins",
}  # fmt: skip


@pytest.fixture(autouse=True)
def _no_cached_report() -> Iterator[None]:
    """The cards read the process's cached report: every test starts and ends without one."""
    K.remember(None)
    yield
    K.remember(None)


@pytest.fixture
def as_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_user_ids", TEST_USER_ID)


@pytest.fixture
def sessions(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_session.bind, expire_on_commit=False)


def row(
    batch: str,
    ratings: dict[str, Any],
    p: dict[str, Any] | None = None,
    *,
    t_h: float = 10.0,
    axis: Any = None,
    ftype: str = LACTO,
    tasting: str | None = None,
) -> K.TastingRow:
    """A tasting of `batch`; with `p`, its link's P series on `axis` (default AXIS)."""
    series = None if p is None else {"t_h": AXIS if axis is None else axis, "p": p}
    return K.TastingRow(tasting or f"{batch}@{t_h}", batch, ftype, t_h, ratings, series)


def synthetic(
    n_batches: int, *, good: bool = True, tastings: int = 1, seed: int = 7
) -> list[K.TastingRow]:
    """Linked batches whose sour is noticed with a true chance of 0.1 or 0.9 each: the model's
    P is that chance (good) or its reverse (bad); the baseline can only say about 0.5."""
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_batches):
        truth = 0.9 if rng.random() < 0.5 else 0.1
        p = truth if good else 1.0 - truth
        for k in range(tastings):
            noticed = rng.random() < truth
            rows.append(
                row(f"b{b:03d}", {"sour": 2 if noticed else 0}, {"sour": [p, p, p]},
                    tasting=f"b{b:03d}-{k}")
            )  # fmt: skip
    return rows


def passed_report(n_batches: int = 31) -> K.Report:
    """A report that passed, computed now (the cards turn numbers off for a stale one)."""
    report = K.compute(synthetic(n_batches), datetime.now(UTC))
    assert report.passed and report.n_batches == n_batches
    return report


# ── observations ────────────────────────────────────────────────────────


def test_a_tasting_is_scored_at_its_time_inside_the_axis_only() -> None:
    p = {"sour": [0.0, 0.5, 1.0]}
    rows = [
        row("a", {"sour": 2}, p, t_h=15.0),  # P = 0.75, noticed
        row("b", {"sour": 0}, p, t_h=0.0),  # the axis' ends are inside
        row("c", {"sour": 1}, p, t_h=20.0),  # a faint note is noticed
        row("d", {"sour": 3}, p, t_h=20.5),  # after the axis: skipped, never clamped
        row("e", {"sour": 3}, p, t_h=4.0, axis=[5.0, 10.0, 20.0]),  # before it
    ]
    got = [(o.batch_id, o.series, o.p, o.y) for o in K.observations(rows)]
    assert got == [("a", "sour", 0.75, 1), ("b", "sour", 0.0, 0), ("c", "sour", 1.0, 1)]


def test_only_targets_that_were_rated_are_scored() -> None:
    p = {"sour": [0.2] * 3, "pungent": [0.4] * 3}
    got = K.observations([row("a", {"sour": 0, "umami": 2, "fruity": 1}, p)])
    assert [(o.series, o.p, o.y) for o in got] == [("sour", 0.2, 0)]  # pungent was not rated
    assert K.observations([row("a", {"umami": 2}, p)]) == []  # no target rated
    assert K.observations([row("a", {}, p)]) == []  # a liking only


def test_missing_or_broken_p_series_are_skipped() -> None:
    rows = [
        row("unlinked", {"sour": 2}),  # no link, or a link written before 0022: no P series
        row("null-next", {"sour": 2}, {"sour": [0.2, None, 0.6]}, t_h=5.0),  # null next to t_h
        row("short", {"sour": 2}, {"sour": [0.2, 0.4]}),  # not one P per time
        row("bad-axis", {"sour": 2}, {"sour": [0.2] * 3}, axis=[0.0, None, 20.0]),
        row("backwards", {"sour": 2}, {"sour": [0.2] * 3}, axis=[20.0, 10.0, 0.0]),
        row("repeated-time", {"sour": 2}, {"sour": [0.2] * 3}, axis=[0.0, 10.0, 10.0]),
        row("not-p", {"sour": 2}, {"sour": [0.2, 1.4, 0.6]}),  # not a probability
        row("bad-rating", {"sour": 7}, {"sour": [0.2] * 3}),
        row("bool-rating", {"sour": True}, {"sour": [0.2] * 3}),
        row("text-p", {"sour": 1}, {"sour": ["0.2", "0.2", "0.2"]}),
        row("no-p", {"sour": 1}, None),
        row("fine", {"sour": 1}, {"sour": [0.2, None, 0.6]}, t_h=20.0),  # its own value, finite
    ]
    rows.append(K.TastingRow("t", "p-not-a-map", LACTO, 10.0, {"sour": 1}, {"t_h": AXIS, "p": []}))
    got = K.observations(rows)
    assert [(o.batch_id, o.p) for o in got] == [("fine", 0.6)]


def test_several_tastings_of_a_batch_all_count_but_the_gate_counts_batches() -> None:
    rows = synthetic(10, tastings=5)
    report = K.compute(rows, NOW)
    assert (report.n_tastings, report.n_observations, report.n_batches) == (50, 50, 10)
    assert (report.passed, report.reason, report.ci_low, report.ci_high) == (
        False, K.TOO_FEW, None, None,
    )  # fmt: skip


# ── the baseline ────────────────────────────────────────────────────────


def test_the_baseline_leaves_the_whole_batch_out() -> None:
    """Hand-computed. Lacto: b1 (linked) noticed sour; b2 (unlinked) did not, then did; b3
    (unlinked) did. Koji: b4 (linked) did not, and no other koji batch rated sour: the series'
    rate over the other batches of any type. Umami: rated by b5 alone: 0.5."""
    p = {"sour": [0.8] * 3, "umami": [0.3] * 3}
    rows = [
        row("b1", {"sour": 2}, p),
        row("b2", {"sour": 0}, tasting="b2-1"),
        row("b2", {"sour": 3}, tasting="b2-2"),
        row("b3", {"sour": 1, "umami": 0}, ftype="koji"),  # not lacto: only the pooled rate
        row("b3b", {"sour": 1}),
        row("b4", {"sour": 0}, p, ftype="koji"),
        row("b5", {"umami": 1}, p, ftype="miso"),
    ]
    obs = K.observations(rows)
    assert [(o.batch_id, o.series, o.y) for o in obs] == [
        ("b1", "sour", 1), ("b4", "sour", 0), ("b5", "umami", 1),
    ]  # fmt: skip
    rates = K.baseline_rates(rows, obs)
    # b1: the other lacto ratings of sour: b2 (0, 1) and b3b (1) -> 2/3
    # b4: koji has b3 besides b4 -> 1/1; b5: miso has nobody else, and nobody else rated
    # umami but b3 (koji, 0) -> the pooled rate 0/1
    np.testing.assert_allclose(rates, [2 / 3, 1.0, 0.0])
    alone = [row("b5", {"umami": 1}, p, ftype="miso")]
    np.testing.assert_allclose(K.baseline_rates(alone, K.observations(alone)), [0.5])

    report = K.compute(rows, NOW)
    y = np.array([1, 0, 1])
    assert report.brier_model == pytest.approx(np.mean((np.array([0.8, 0.8, 0.3]) - y) ** 2))
    assert report.brier_baseline == pytest.approx(np.mean((rates - y) ** 2))
    assert report.diff == pytest.approx(report.brier_model - report.brier_baseline)
    assert (report.n_batches, report.n_tastings, report.passed) == (3, 3, False)


# ── the gate ────────────────────────────────────────────────────────────


def test_a_model_better_than_the_baseline_passes() -> None:
    report = K.compute(synthetic(40), NOW)
    assert report.n_batches == 40 and report.n_observations == 40
    assert report.brier_model is not None and report.brier_baseline is not None
    assert report.brier_model < report.brier_baseline
    assert report.ci_low is not None and report.ci_high is not None
    assert report.ci_low <= report.diff <= report.ci_high < 0
    assert report.auc is not None and report.auc_low is not None
    assert 0.5 < report.auc_low <= report.auc
    assert (report.passed, report.reason) == (True, None)
    assert K.calibrated_on(report, NOW) == 40


def test_a_model_worse_than_the_baseline_fails() -> None:
    report = K.compute(synthetic(40, good=False), NOW)
    assert report.diff is not None and report.diff > 0
    assert report.ci_low is not None and report.ci_low > 0
    assert report.auc_low is not None and report.auc_low < 0.5
    assert (report.passed, report.reason) == (False, f"{K.NOT_BETTER}; {K.NO_SKILL}")
    assert K.calibrated_on(report, NOW) is None


def test_a_base_rate_model_beats_the_brier_baseline_but_fails_the_auc() -> None:
    """The leave-one-batch-out baseline's built-in penalty: a model that only says each type's
    noticed rate beats it on Brier alone. The AUC (within each type and series) shows it tells
    nothing apart: exactly 0.5, so it fails, with one type or with several of different rates."""
    one = [row(f"b{b:02d}", {"sour": 2 if b % 2 else 0}, {"sour": [0.5] * 3}) for b in range(40)]
    several = [  # 20 batches per type, noticed exactly at its rate
        row(f"{ftype}{b:02d}", {"sour": 2 if b < 20 * rate else 0}, {"sour": [rate] * 3},
            ftype=ftype)
        for ftype, rate in (("koji", 0.2), (LACTO, 0.5), ("miso", 0.8)) for b in range(20)
    ]  # fmt: skip
    for rows in (one, several):
        report = K.compute(rows, NOW)
        assert report.ci_high is not None and report.ci_high < 0  # the Brier condition holds
        assert (report.auc, report.auc_low) == (0.5, 0.5)
        assert (report.passed, report.reason) == (False, K.NO_SKILL)
    pooled = K.auc(np.array([o.p for o in K.observations(several)]),
                   np.array([o.y for o in K.observations(several)], dtype=float))  # fmt: skip
    assert pooled is not None and pooled > 0.6  # across types it would have looked skilled


def test_the_auc_counts_ties_as_one_half_within_each_cell() -> None:
    """Hand-computed. Noticed at P 0.4 and 0.8, not noticed at 0.2 and 0.4: of the 4 pairs, 3
    are ordered and 1 is tied, (3 + ½) / 4 = 0.875 (average ranks: noticed ranks 2.5 + 4, U =
    6.5 − 3 = 3.5). In two cells: only the pairs of a cell count."""
    p, y = np.array([0.2, 0.4, 0.4, 0.8]), np.array([0.0, 0.0, 1.0, 1.0])
    assert K.auc(p, y) == 0.875
    assert K.auc(np.full(4, 0.3), y) == 0.5  # all tied
    assert K.auc(p, np.ones(4)) is None and K.auc(np.array([]), np.array([])) is None
    # cell 0: 0.2 (not) vs 0.4 (noticed) -> 1; cell 1: 0.4 (not) vs 0.8 (noticed) -> 1;
    # pooled pairs across the cells (0.2 vs 0.8, 0.4 vs 0.4) are left out
    cells = np.array([0, 1, 0, 1], dtype=np.intp)
    assert K.auc(p, y, cells) == 1.0
    assert K.auc(np.array([0.9, 0.1]), np.array([1.0, 0.0]), np.array([0, 1])) is None


def test_fewer_than_30_batches_cannot_pass() -> None:
    report = K.compute(synthetic(29), NOW)
    assert report.n_batches == 29 and report.diff is not None and report.diff < 0
    assert report.auc is not None and report.auc_low is None
    assert (report.passed, report.reason, report.ci_low, report.ci_high) == (
        False, "fewer than 30 tasted batches", None, None,
    )  # fmt: skip
    assert K.calibrated_on(report, NOW) is None
    empty = K.compute([], NOW)
    assert (empty.n_observations, empty.brier_model, empty.auc, empty.passed) == (
        0, None, None, False,
    )  # fmt: skip
    assert empty.reason == K.TOO_FEW and [b.n for b in empty.bins] == [0] * 5


def test_a_stale_pass_turns_the_numbers_off() -> None:
    report = K.compute(synthetic(40), NOW)
    assert K.calibrated_on(report, NOW + K.DISPLAY_FOR) == 40
    assert K.calibrated_on(report, NOW + K.DISPLAY_FOR + timedelta(seconds=1)) is None
    assert K.calibrated_on(None, NOW) is None


def test_the_bootstrap_is_seeded() -> None:
    rows = synthetic(40)
    first, again = K.compute(rows, NOW), K.compute(list(reversed(rows)), NOW)
    assert first == again  # the same data (in any order), the same report
    other = K.compute(rows, NOW, seed=K.SEED + 1)
    assert other.diff == first.diff and (other.ci_low, other.ci_high) != (
        first.ci_low, first.ci_high,
    )  # fmt: skip


def test_the_bootstrap_resamples_batches_and_rescores_their_observations() -> None:
    """Against a plain loop over the same draws: each resample's Brier scores and AUC are
    recomputed over the observations of the batches drawn (with their multiplicity), the AUC
    over pairs of the same cell."""
    rng = np.random.default_rng(3)
    k, sizes = 12, rng.integers(1, 4, size=12)
    groups = np.repeat(np.arange(k), sizes)
    n = len(groups)
    err_model, err_baseline = rng.random(n), rng.random(n)
    p, y = np.round(rng.random(n), 1), (rng.random(n) < 0.5).astype(float)  # ties included
    cells = rng.integers(0, 2, n).astype(np.intp)
    boot = K.bootstrap(groups, err_model - err_baseline, p, y, cells, seed=5, resamples=300)
    draws = np.random.default_rng(5).integers(0, k, size=(300, k))  # one chunk: the same draws
    d, a = [], []
    for draw in draws:
        idx = np.concatenate([np.flatnonzero(groups == b) for b in draw])
        d.append(err_model[idx].mean() - err_baseline[idx].mean())
        pi, yi, ci = p[idx], y[idx], cells[idx]
        pairs = (yi[:, None] == 1) & (yi[None, :] == 0) & (ci[:, None] == ci[None, :])
        score = (pi[:, None] > pi[None, :]) + 0.5 * (pi[:, None] == pi[None, :])
        a.append((score * pairs).sum() / pairs.sum() if pairs.any() else K.UNDEFINED_AUC)
    assert (boot.ci_low, boot.ci_high) == pytest.approx(tuple(np.quantile(d, [0.05, 0.95])))
    assert boot.auc_low == pytest.approx(float(np.quantile(a, 0.05)))


def test_repeated_tastings_do_not_narrow_the_interval() -> None:
    """Batch-level resampling: tasting every batch three times the same gives the same
    estimate and the same CI (three times the observations, the same batches)."""
    once = synthetic(40)
    thrice = [dataclasses.replace(r, tasting_id=f"{r.tasting_id}/{i}") for r in once
              for i in range(3)]  # fmt: skip
    a, b = K.compute(once, NOW), K.compute(thrice, NOW)
    assert (b.n_observations, b.n_tastings, b.n_batches) == (120, 120, 40)
    assert (a.diff, a.ci_low, a.ci_high, a.auc, a.auc_low, a.passed) == (
        b.diff, b.ci_low, b.ci_high, b.auc, b.auc_low, b.passed,
    )  # fmt: skip


def test_reliability_bins() -> None:
    p = np.array([0.0, 0.1, 0.2, 0.39, 0.5, 0.99, 1.0])
    y = np.array([0.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0])
    got = [(b.lo, b.hi, b.n, b.mean_p, b.observed) for b in K.reliability(p, y)]
    assert got == [
        (0.0, 0.2, 2, 0.05, 0.0), (0.2, 0.4, 2, 0.295, 0.5), (0.4, 0.6, 1, 0.5, 1.0),
        (0.6, 0.8, 0, None, None), (0.8, 1.0, 2, 0.995, 1.0),
    ]  # fmt: skip
    report = K.compute(synthetic(40), NOW)
    assert sum(b.n for b in report.bins) == report.n_observations
    assert [b.n > 0 for b in report.bins] == [True, False, False, False, True]


def test_the_report_round_trips_through_json() -> None:
    for report in (passed_report(), K.compute(synthetic(5), NOW), K.compute([], NOW)):
        body = K.report_json(report)
        assert set(body) == REPORT_KEYS
        assert K.report_from_json(json.loads(json.dumps(body))) == report
        CalibrationReportOut.model_validate(body)
        CalibrationReportOut.model_validate(K.public_json(report))
    body = K.report_json(passed_report())
    assert not K.report_from_json(body | {"passed": "yes"}).passed  # only a true bool passes


def test_the_public_report_hides_what_could_show_one_tasting() -> None:
    small = K.compute(synthetic(12), NOW)
    public = K.public_json(small)
    assert {k: public[k] for k in K.SCORES} == dict.fromkeys(K.SCORES)  # below 30 batches
    assert [(b["n"], b["mean_p"], b["observed"]) for b in public["bins"]] == [
        (b.n, None, None) for b in small.bins
    ]
    assert {k: public[k] for k in ("n_batches", "passed", "reason")} == {
        "n_batches": 12, "passed": False, "reason": K.TOO_FEW,
    }  # fmt: skip
    rows = [*synthetic(31), row("odd", {"sour": 2}, {"sour": [0.5] * 3})]  # 1 rating in a bin
    big = K.compute(rows, NOW)
    public = K.public_json(big)
    full = K.report_json(big)
    assert {k: public[k] for k in K.SCORES} == {k: full[k] for k in K.SCORES}  # 30+ batches
    for b, f in zip(public["bins"], full["bins"], strict=True):
        shown = f["n"] >= K.PUBLIC_BIN_MIN
        assert b == (f if shown else f | {"mean_p": None, "observed": None})
    assert [b["n"] for b in public["bins"]] == [16, 0, 1, 0, 15]  # counts always stay


# ── stored reports, the schedule, the admin trigger ─────────────────────


async def _tasted(
    db: AsyncSession,
    ratings: list[dict[str, int]],
    p: dict[str, list[float]] | None = None,
    *,
    ftype: str = LACTO,
    owner: str = TEST_USER_ID,
) -> Batch:
    """A batch with its tastings at 10 h (with notes), linked to a card with this P series."""
    culture = Culture(name="my ferment", type=ftype, owner_id=owner)
    db.add(culture)
    await db.flush()
    batch = Batch(
        culture_id=culture.id, started_at=START, current_stage="ferment", stage_entered_at=START,
    )  # fmt: skip
    db.add(batch)
    await db.flush()
    if p is not None:
        db.add(RecommendationLink(
            batch_id=batch.id, source_kind="library", recipe_key=KRAUT, operators=[],
            mode="proven", temperature_c=20.0, window={"peak_h": 10.0}, targets=[],
            p_series={"t_h": AXIS, "p": p}, grid_version="test",
        ))  # fmt: skip
    for r in ratings:
        db.add(Tasting(batch_id=batch.id, t_h=10.0, ratings=r, liking=4, notes=NOTE))
    await db.commit()
    return batch


async def _store(db: AsyncSession, rows: list[K.TastingRow]) -> list[Batch]:
    """The synthetic rows as batches, tastings and links in the database."""
    out = []
    for r in rows:
        p = None if r.p_series is None else {s: list(v) for s, v in r.p_series["p"].items()}
        out.append(await _tasted(db, [dict(r.ratings)], p, ftype=r.fermentation_type))
    return out


async def _reports(db: AsyncSession) -> int:
    found = await db.execute(select(func.count()).select_from(CalibrationReport))
    return int(found.scalar_one())


async def test_recompute_reads_the_database_and_stores_the_report(
    db_session: AsyncSession,
) -> None:
    rows = synthetic(31)
    await _store(db_session, rows)
    await _tasted(db_session, [{"sour": 1}, {"sour": 0}])  # not linked: the baseline's only
    await _tasted(db_session, [{"sour": 1}], {"umami": [0.5] * 3})  # sour is not its target
    report = await K.recompute(db_session, NOW)
    assert report.passed and report.n_batches == 31 and report.n_observations == 31
    assert report == K.cached()
    stored = (await db_session.execute(select(CalibrationReport))).scalar_one()
    assert (stored.passed, stored.n_batches, stored.report) == (True, 31, K.report_json(report))
    assert await K.latest(db_session) == report


async def test_only_the_newest_reports_are_kept(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(K, "REPORTS_KEPT", 2)
    for days in (3, 2, 1):
        await K.recompute(db_session, NOW - timedelta(days=days))
    assert await _reports(db_session) == 2
    latest = await K.latest(db_session)
    assert latest is not None and latest.computed_at == NOW - timedelta(days=1)


async def test_a_fresh_report_is_loaded_and_a_stale_one_recomputed(
    db_session: AsyncSession, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await _store(db_session, synthetic(31))
    fresh = await K.recompute(db_session, NOW - timedelta(days=6))
    K.remember(None)  # a new process
    assert await K.refresh(sessions, NOW) == fresh == K.cached()
    assert await _reports(db_session) == 1  # loaded, not recomputed
    later = NOW + timedelta(days=1, seconds=1)  # seven days after the last
    again = await K.refresh(sessions, later)
    assert again.computed_at == later and again == K.cached()
    assert await _reports(db_session) == 2


async def test_an_unreadable_report_is_recomputed(
    db_session: AsyncSession, sessions: async_sessionmaker[AsyncSession]
) -> None:
    before_auc = {k: v for k, v in K.report_json(passed_report()).items() if "auc" not in k}
    for broken in ({}, before_auc):  # garbage; a report of the format before the AUC condition
        db_session.add(CalibrationReport(computed_at=NOW, passed=True, n_batches=31, report=broken))
        await db_session.commit()
        assert await K.latest(db_session) is None and K.cached() is None  # never shown as passed
        report = await K.refresh(sessions, NOW + timedelta(hours=1))
        assert report.computed_at == NOW + timedelta(hours=1) and not report.passed
        assert await K.latest(db_session) == report
        await db_session.execute(sa_delete(CalibrationReport))
        await db_session.commit()


async def test_the_schedule_recomputes_a_stale_report_at_startup(
    db_session: AsyncSession, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await K.recompute(db_session, datetime.now(UTC) - timedelta(days=8))
    K.remember(None)

    def recomputed() -> bool:  # the task caches its report once committed
        cached = K.cached()
        return cached is not None and datetime.now(UTC) - cached.computed_at < timedelta(1)

    task = asyncio.create_task(K.run_schedule(sessions))
    try:
        for _ in range(500):
            if recomputed():
                break
            await asyncio.sleep(0.01)
        assert recomputed()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task  # it was asleep until the report turns a week old
    assert await _reports(db_session) == 2


async def test_the_schedule_retries_after_an_error(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(jobs, "RETRY_S", 0.0)
    monkeypatch.setattr(K, "ERROR_RETRY_S", 0.0)
    errors: list[Exception] = [
        IntegrityError("INSERT", {}, Exception("a data error")),
        OperationalError("SELECT 1", {}, Exception("the database is down")),
    ]
    calls: list[int] = []
    slept = asyncio.Event()

    async def refresh(_: Any) -> K.Report:
        calls.append(1)
        if errors:
            raise errors.pop()
        slept.set()
        return passed_report()

    monkeypatch.setattr(K, "refresh", refresh)
    task = asyncio.create_task(K.run_schedule(sessions))
    await asyncio.wait_for(slept.wait(), 5)
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) == 3  # both errors retried; then asleep until the next week


async def test_the_app_runs_the_schedule(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[Any] = []
    stopped = asyncio.Event()

    async def schedule(factory: Any) -> None:
        started.append(factory)
        try:
            await asyncio.sleep(3600)
        finally:
            stopped.set()

    monkeypatch.setattr(K, "run_schedule", schedule)
    monkeypatch.setattr(C, "recompute_at_startup", lambda _: asyncio.sleep(0))
    monkeypatch.setattr(database, "async_session_maker", sessions)
    async with app.router.lifespan_context(app):
        for _ in range(100):
            if started:
                break
            await asyncio.sleep(0.01)
    assert started == [sessions]
    assert stopped.is_set()  # cancelled with the app


# ── the API ─────────────────────────────────────────────────────────────


async def test_the_report_holds_aggregates_only(
    client: AsyncClient, db_session: AsyncSession, as_admin: None
) -> None:
    batches = await _store(db_session, synthetic(31))
    mine = await _tasted(db_session, [{"sour": 1}], {"sour": [0.9] * 3}, owner=OTHER)
    assert (await client.get("/recommendations/calibration")).status_code == 404  # none yet

    resp = await client.post("/admin/calibration/recompute")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == REPORT_KEYS
    assert (body["passed"], body["n_batches"], body["reason"]) == (True, 32, None)
    assert [set(b) for b in body["bins"]] == [{"lo", "hi", "n", "mean_p", "observed"}] * 5

    with as_user(OTHER):  # any signed-in user reads the same report
        got = await client.get("/recommendations/calibration")
    # 30+ batches and no bin under 3 ratings but the empty ones: the public report is the full one
    assert got.status_code == 200 and got.json() == body
    assert (await client.get("/admin/calibration")).json() == body
    text = got.text
    ids = [str(b.id) for b in [*batches, mine]] + [str(b.culture_id) for b in [*batches, mine]]
    ids += [str(t) for t in (await db_session.execute(select(Tasting.id))).scalars()]
    leaks = [s for s in [*ids, TEST_USER_ID, OTHER, NOTE, "Grandma"] if s in text]
    assert leaks == []
    assert await _reports(db_session) == 1


async def test_one_person_s_tasting_stays_hidden_from_other_users(
    client: AsyncClient, db_session: AsyncSession, as_admin: None
) -> None:
    """A single tasting: the public report shows that it counts, never its P or its outcome;
    the admins' full report has them."""
    await _tasted(db_session, [{"sour": 3}], {"sour": [0.72] * 3}, owner=OTHER)
    full = (await client.post("/admin/calibration/recompute")).json()
    assert full["brier_model"] == pytest.approx(0.0784) and full["auc"] is None
    assert [(b["n"], b["mean_p"], b["observed"]) for b in full["bins"]][3] == (1, 0.72, 1.0)
    with as_user(TEST_USER_ID + "-not-admin"):
        public = (await client.get("/recommendations/calibration")).json()
    assert {k: public[k] for k in K.SCORES} == dict.fromkeys(K.SCORES)
    assert [(b["n"], b["mean_p"], b["observed"]) for b in public["bins"]] == [
        (0, None, None), (0, None, None), (0, None, None), (1, None, None), (0, None, None),
    ]  # fmt: skip
    assert {k: public[k] for k in ("n_tastings", "n_observations", "n_batches", "passed")} == {
        "n_tastings": 1, "n_observations": 1, "n_batches": 1, "passed": False,
    }  # fmt: skip
    assert public["reason"] == K.TOO_FEW and "0.72" not in json.dumps(public)


async def test_only_admins_recompute_and_only_signed_in_users_read(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert (await client.post("/admin/calibration/recompute")).status_code == 403
    assert (await client.get("/admin/calibration")).status_code == 403
    assert await _reports(db_session) == 0
    monkeypatch.setattr(settings, "admin_user_ids", TEST_USER_ID)
    assert (await client.get("/admin/calibration")).status_code == 404  # none yet
    override = app.dependency_overrides.pop(get_current_user_id)  # the real bearer check
    try:
        assert (await client.get("/recommendations/calibration")).status_code == 401
        assert (await client.get("/admin/calibration")).status_code == 401
        assert (await client.post("/admin/calibration/recompute")).status_code == 401
    finally:
        app.dependency_overrides[get_current_user_id] = override


async def test_a_started_batch_tasted_at_its_peak_is_scored(
    client: AsyncClient, db_session: AsyncSession, catalogue: None  # noqa: F811
) -> None:
    """End to end: Start batch writes the card's P series, a tasting is scored against it."""
    ask = {"recipe_key": KIMCHI, "aromas": ["pungent"], "tastes": ["sour"], "temperature_c": 22}
    body = (await client.post("/batches/from-recommendation", json=ask)).json()
    batch = await db_session.get(Batch, uuid.UUID(body["batch"]["id"]))
    assert batch is not None
    batch.started_at = datetime.now(UTC) - timedelta(days=5)
    await db_session.commit()
    tasted_at = batch.started_at + timedelta(hours=body["link"]["window"]["peak_h"])
    resp = await client.post(
        f"/batches/{batch.id}/tastings",
        json={"tasted_at": tasted_at.isoformat(), "ratings": {"sour": 2, "umami": 1}},
    )
    assert resp.status_code == 201, resp.text
    report = await K.recompute(db_session)
    assert (report.n_tastings, report.n_observations, report.n_batches) == (1, 1, 1)
    stats = grid.interp_temp(KIMCHI, 22.0)
    p = float(np.interp(resp.json()["t_h"], stats.t_h, stats.p["sour"]))
    assert report.brier_model == pytest.approx((p - 1.0) ** 2, abs=1e-3)
    assert report.brier_baseline == pytest.approx(0.25)  # nobody else tasted: 0.5


# ── the cards' numbers ──────────────────────────────────────────────────


def _strip(body: dict[str, Any]) -> dict[str, Any]:
    """A response without the calibrated additions."""
    out = json.loads(json.dumps(body))
    for section in ("proven", "experimental", "community"):
        for card in (out.get(section) or {}).get("cards", []):
            card.pop("p_peak", None)
            card.pop("calibrated_on", None)
            card["trust"]["labels"] = [
                x for x in card["trust"]["labels"] if not x.startswith("calibrated on")
            ]
            for t in card["targets"]:
                t.pop("p_peak", None)
    return out


async def test_cards_show_numbers_only_while_the_gate_passes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    before = await client.post("/recommendations", json=ASK)
    assert before.status_code == 200
    K.remember(K.compute(synthetic(40, good=False), NOW))  # a report that failed
    failed = await client.post("/recommendations", json=ASK)
    K.remember(K.compute(synthetic(12), NOW))  # too few batches
    small = await client.post("/recommendations", json=ASK)
    assert failed.content == small.content == before.content  # byte-identical: no numbers

    K.remember(passed_report(31))
    body = (await client.post("/recommendations", json=ASK)).json()
    cards = body["proven"]["cards"] + body["experimental"]["cards"]
    assert cards and body["proven"]["cards"] and body["experimental"]["cards"]
    for card in cards:
        assert card["calibrated_on"] == 31
        assert card["trust"]["labels"][-1] == "calibrated on 31 batches"
        assert card["level"] in {"Low", "Med", "High"}  # the levels stay
        modelled = [t for t in card["targets"] if t["modelled"]]
        assert modelled and all(0.0 <= t["p_peak"] <= 1.0 for t in modelled)
        if len(modelled) == len(card["targets"]):
            mean = np.mean([t["p_peak"] for t in modelled])
            assert card["p_peak"] == pytest.approx(mean, abs=0.006)
        else:
            assert "p_peak" not in card
    assert _strip(body) == before.json()  # nothing else changes (safety lines included)

    K.remember(K.compute(synthetic(40, good=False), NOW))  # the next run fails: numbers off
    assert (await client.post("/recommendations", json=ASK)).content == before.content
    stale = K.compute(synthetic(31), datetime.now(UTC) - K.DISPLAY_FOR - timedelta(minutes=1))
    K.remember(stale)  # passed, but the weekly recompute has failed since: numbers off
    assert stale.passed
    assert (await client.post("/recommendations", json=ASK)).content == before.content


async def test_the_forecast_and_cards_without_targets_never_change(client: AsyncClient) -> None:
    ask = {"ingredients": ["Napa cabbage"]}
    forecast = {"recipe_key": KIMCHI, "aromas": ["pungent"], "tastes": ["sour"]}
    before = [
        (await client.post("/recommendations", json=ask)).content,
        (await client.post("/recommendations/forecast", json=forecast)).content,
    ]
    K.remember(passed_report())
    after = [
        (await client.post("/recommendations", json=ask)).content,
        (await client.post("/recommendations/forecast", json=forecast)).content,
    ]
    assert after == before


def test_p_peak_is_p_noticeable_at_the_peak() -> None:
    recipe = S.active_recipe(KIMCHI)
    card, _ = S.build_card(recipe, S.parse_targets(["pungent", "caramel"], ["sour"]), 22.0)
    assert card is not None
    ev = card.evaluation
    plain, numbers = S.card_json(card), S.card_json(card, 34)
    assert S.card_json(card, None) == plain
    stats = grid.interp_temp(KIMCHI, 22.0)
    expected = {}
    for t, s in zip(numbers["targets"], ev.targets, strict=True):
        if s.modelled:
            expected[s.target.key] = round(float(np.interp(ev.peak_h, stats.t_h,
                                                           stats.p[s.target.key])), 2)
            assert t["p_peak"] == pytest.approx(expected[s.target.key], abs=0.0051)
        else:
            assert "p_peak" not in t and t["level"] is None  # caramel: not modelled
    assert "p_peak" not in numbers  # no card-level mean over a target the model cannot see
    assert [t["level"] for t in numbers["targets"]] == [t["level"] for t in plain["targets"]]
    assert numbers["safety_lines"] == plain["safety_lines"]
    assert numbers["window"] == plain["window"]
    both, _ = S.build_card(recipe, S.parse_targets(["pungent"], ["sour"]), 22.0)
    assert both is not None
    peak = both.evaluation.peak_h
    mean = np.mean([np.interp(peak, stats.t_h, stats.p[k]) for k in ("pungent", "sour")])
    assert S.card_json(both, 34)["p_peak"] == pytest.approx(mean, abs=0.0051)
    none, _ = S.build_card(recipe, (), 22.0)
    assert none is not None and S.card_json(none, 34) == S.card_json(none)  # no score


def test_community_cards_carry_the_numbers_after_their_own_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = library.get(KRAUT)
    assert recipe is not None
    card, _ = S.build_card(recipe, S.parse_targets([], ["sour"]), None)
    assert card is not None
    c = C.Candidate(
        uuid.uuid4(), "Bright kraut", "Ana", recipe,
        (grid.entry(KRAUT, grid.recipe(KRAUT).temps[0]),), made=2, mean_liking=None,
    )  # fmt: skip
    body = C.card_json(card, c, 31)
    assert body["trust"]["labels"][-1] == "calibrated on 31 batches"
    assert C.SECTION_LABEL in body["trust"]["labels"]
    assert body["calibrated_on"] == 31 and 0.0 <= body["targets"][0]["p_peak"] <= 1.0
    plain = _strip({"community": {"cards": [body]}})["community"]["cards"][0]
    assert C.card_json(card, c) == plain

    monkeypatch.setattr(C, "community_card", lambda *a, **k: card)
    section = C.section([c], [], [], ["sour"], None, calibrated=31)
    assert section["cards"] == [body]
    assert C.section([c], [], [], ["sour"], None)["cards"] == [C.card_json(card, c)]
