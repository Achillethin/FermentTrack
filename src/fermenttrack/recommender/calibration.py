"""The calibration gate (design § 13.2, R4): do the cards' probabilities beat a plain baseline
on what people noticed when they tasted their batches, and do they tell noticed from not
noticed? Until a report passes, cards show Low / Med / High only (§ 5.4). While the latest
report passes, they add the numbers and the label "calibrated on n batches"
(service.calibrated_json). The numbers turn off again when a later report fails.

**Data** (`load_rows`): every tasting (models.Tasting) with its batch's fermentation type
(cultures.type). When the batch was started from a card, the row also carries its
recommendation link's P series: P (noticeable) per modelled target on the card's time axis, in
hours since the batch started (RecommendationLink.p_series). Nothing else is read: no owner and
no notes. Batch and tasting ids are used only to group and order the rows, and the report holds
aggregates only.

**Observations** (`observations`): take a tasting of a linked batch that has a P series, at a
t_h inside its time axis [first, last]. For each series s that is both a target in the series
and rated in the tasting: P = np.interp(t_h, axis, P_s), and y = 1 when the rating is ≥ 1
("noticed"), else 0. Anything doubtful is skipped, never clamped or guessed:
- a tasting outside the axis;
- a series that is not both rated and a target;
- a link without a P series (written before migration 0022, or with no modelled target);
- an axis that is not finite and strictly increasing;
- a P list of another length than the axis;
- a P that is not a finite probability (a null entry next to t_h);
- a rating that is not 0-3.

**Baseline** (`baseline_rates`): for each observation, the noticed rate of its series in its
fermentation type, over every OTHER tasted batch, linked or not (leave-one-batch-out). The rate
is the share of their ratings of s that are ≥ 1, so it is the constant with the lowest squared
error on those ratings. Fallbacks, in order:
- no other batch of the type rated s: the series' rate over every other batch of any type;
- no other batch rated s at all: 0.5.

**Several tastings of one batch** all count as observations, each scored on what it rated. The
batch is still the unit for everything else, so repeated tastings are never treated as
independent:
- the gate counts batches (n_batches: linked batches with at least one observation);
- the baseline leaves a whole batch out;
- the bootstrap resamples batches.

**Gate** (`compute`): Brier_model = mean (P − y)² and Brier_baseline = mean (b − y)², over the
same observations; d = Brier_model − Brier_baseline. AUC: the chance that a noticed rating had a
higher P than a rating that was not, ties counting one half (Mann–Whitney with average ranks),
over pairs of ratings in the same baseline cell (type, series) only (`auc`).
- Why within cells: across cells, P tells types and series apart, and so does the baseline. A
  model that only knew each type's base rate would earn a pooled AUC above 0.5 wherever types
  differ: in simulation it passed both conditions 30–42 % of the time with 2–3 types, against
  0 % within cells. Skilled models kept the same power either way (B11 review round 2).
- With at least MIN_BATCHES (30) batches, one paired, batch-level bootstrap (`bootstrap`):
  RESAMPLES (2 000) draws of n_batches batches with replacement; on each draw's observations
  (with their multiplicity) both d and the AUC are recomputed. numpy's default_rng is seeded with
  SEED, so the same data gives the same report.
- It passes iff BOTH hold: the upper bound of the 90 % CI of d (its 95th percentile) is below 0,
  and the 5th percentile of the AUC (auc_low) is above 0.5. The AUC condition stops a model that
  only knows the base rates from passing on the leave-one-out baseline's built-in penalty of
  about π(1 − π)/n (B11 review).
- A draw where no cell holds both classes has no AUC. It counts as 0.5, "no discrimination
  shown": conservative, since it can only pull auc_low down to 0.5 and so towards failing,
  never towards passing.
- With fewer batches there is no bootstrap, and the gate does not pass ("fewer than 30 tasted
  batches").

**Reliability** (`reliability`): 5 equal-width bins of P on [0, 1] (P = 1 goes in the last).
Each bin reports its n, its mean P and its observed noticed rate (None when empty).

**Privacy** (`public_json`): the report GET /recommendations/calibration gives every signed-in
user hides what could show one person's tastings:
- below MIN_BATCHES, every score (Brier, d, CI, AUC) and every bin's mean P and observed rate;
- at any size, the mean P and observed rate of a bin with fewer than PUBLIC_BIN_MIN (3) ratings.

Counts, the decision and its reason stay. Admins get the full report (GET
/admin/calibration, POST /admin/calibration/recompute). **Residual limit:** two consecutive
public reports that differ by a single new tasting can still be compared, once there are 30
batches. The change in the Brier score and in the bins would hint at that tasting's P and
outcome. Reports are weekly (an admin's recompute aside), so this is the same kind of
differencing B10 documents for the community's mean liking.

**Stored** in calibration_reports (migration 0023), one row per run, the newest REPORTS_KEPT
kept: the gate's decisions over time.

**Run**:
- `run_schedule` is the app's lifespan task. At startup it loads the latest report, or
  recomputes it when it is missing, unreadable or STALE_AFTER (7 days) old. It then recomputes
  whenever the report turns 7 days old: weekly, or at the next start once the instance has
  slept.
- POST /admin/calibration/recompute (admins) recomputes at once.
- The computation itself runs in a worker thread.

**Cache** (`cached`): the latest report, in process memory (one process, like the job worker).
Every recompute and every read of the latest row sets it. Cards read the cache, never the
database, so the switch costs nothing per request; until it is loaded they show Low / Med /
High. Numbers also turn off when the cached report is older than DISPLAY_FOR (2 × STALE_AFTER):
the weekly recompute is failing, so the pass is no longer current (`calibrated_on`).
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import numpy.typing as npt
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fermenttrack.models import Batch, CalibrationReport, Culture, RecommendationLink, Tasting
from fermenttrack.recommender import jobs
from fermenttrack.schemas import CalibrationReportOut

logger = logging.getLogger(__name__)

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.intp]

MIN_BATCHES = 30  # tasted linked batches before the gate can pass
RESAMPLES = 2000  # batch-level bootstrap resamples
SEED = 132  # the bootstrap's seed (design § 13.2): the same data gives the same report
CI_LEVEL = 0.9  # the CI of d: 5th to 95th percentiles; auc_low: the 5th
AUC_MIN = 0.5  # auc_low must be above it
UNDEFINED_AUC = 0.5  # a resample with one class only: no discrimination shown
N_BINS = 5  # reliability bins of equal width on [0, 1]
PUBLIC_BIN_MIN = 3  # ratings in a bin before the public report shows its mean P and rate
NOTICED = 1  # a rating this high or higher: noticed (0 not noticed ... 3 strong)
MAX_RATING = 3
NO_DATA_RATE = 0.5  # the baseline when no other batch rated the series
DIGITS = 6  # the report's numbers are rounded to this many decimals
DRAWS_PER_CHUNK = 1_000_000  # bootstrap values per chunk (memory bound)
STALE_AFTER = timedelta(days=7)
DISPLAY_FOR = 2 * STALE_AFTER  # a passed report older than this turns the numbers off
REPORTS_KEPT = 52  # a year of weekly runs
ERROR_RETRY_S = 3600.0  # after an error that is not the connection's
MIN_SLEEP_S = 60.0
TOO_FEW = f"fewer than {MIN_BATCHES} tasted batches"
NOT_BETTER = "the model does not beat the baseline (the 90 % CI's upper bound is not below 0)"
NO_SKILL = (
    "the model does not tell noticed from not noticed (the AUC's 5th percentile is not above 0.5)"
)
SCORES = ("brier_model", "brier_baseline", "diff", "ci_low", "ci_high", "auc", "auc_low")


# ── the computation: plain values in, a report out ──────────────────────


@dataclass(frozen=True)
class TastingRow:
    """One tasting, as the gate reads it. p_series: its batch's link's (None: the batch was not
    started from a card, or its link has no P series)."""

    tasting_id: str
    batch_id: str
    fermentation_type: str
    t_h: float
    ratings: Mapping[str, Any]
    p_series: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class Observation:
    """One rated target at one tasting: the card's P then, and whether it was noticed."""

    batch_id: str
    tasting_id: str
    fermentation_type: str
    series: str
    p: float
    y: int  # 1 noticed (rating ≥ 1), 0 not


@dataclass(frozen=True)
class Bin:
    """A reliability bin: P in [lo, hi) ([lo, hi] for the last)."""

    lo: float
    hi: float
    n: int
    mean_p: float | None  # None when empty
    observed: float | None  # the noticed rate


@dataclass(frozen=True)
class Report:
    """A run of the gate (the full report: admins'). n_tastings: the tastings with at least one
    observation; n_observations: the ratings scored; n_batches: the linked batches they come
    from. Brier scores, d and auc are None without observations (auc also when no baseline cell
    holds both classes); the CI and auc_low are None below MIN_BATCHES. reason: why it did not
    pass (None when it passed)."""

    computed_at: datetime
    n_tastings: int
    n_observations: int
    n_batches: int
    brier_model: float | None
    brier_baseline: float | None
    diff: float | None
    ci_low: float | None
    ci_high: float | None
    auc: float | None
    auc_low: float | None
    passed: bool
    reason: str | None
    bins: tuple[Bin, ...]


@dataclass(frozen=True)
class Bootstrap:
    ci_low: float  # d's 5th percentile
    ci_high: float  # d's 95th percentile
    auc_low: float  # the AUC's 5th percentile


def _rating(value: Any) -> int | None:
    """y for a 0-3 rating: 1 when noticed (≥ 1), else 0. None: not a rating (skipped)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if not (math.isfinite(value) and 0 <= value <= MAX_RATING):
        return None
    return int(value >= NOTICED)


def _floats(values: Any) -> FloatArray | None:
    """A JSON list of numbers as floats, a null as nan; None when it is not such a list."""
    if not isinstance(values, list) or not values:
        return None
    out = []
    for v in values:
        if v is None:
            out.append(math.nan)
        elif isinstance(v, bool) or not isinstance(v, int | float):
            return None
        else:
            out.append(float(v))
    return np.asarray(out, dtype=np.float64)


def _axis(p_series: Mapping[str, Any]) -> FloatArray | None:
    """The P series' time axis: finite and strictly increasing (a card's), else None."""
    axis = _floats(p_series.get("t_h"))
    if axis is None or not np.all(np.isfinite(axis)) or np.any(np.diff(axis) <= 0):
        return None
    return axis


def observations(rows: Iterable[TastingRow]) -> list[Observation]:
    """The scored ratings (see the module docstring), ordered by batch, tasting and series."""
    out = []
    for r in sorted(rows, key=lambda r: (r.batch_id, r.tasting_id)):
        if not isinstance(r.p_series, Mapping) or not isinstance(r.ratings, Mapping):
            continue
        axis = _axis(r.p_series)
        p_by_series = r.p_series.get("p")
        if axis is None or not isinstance(p_by_series, Mapping):
            continue
        if not (math.isfinite(r.t_h) and axis[0] <= r.t_h <= axis[-1]):
            continue  # outside the card's time axis: skipped, never clamped
        for s in sorted(set(p_by_series) & set(r.ratings)):
            y = _rating(r.ratings[s])
            values = _floats(p_by_series[s])
            if y is None or values is None or len(values) != len(axis):
                continue
            p = float(np.interp(r.t_h, axis, values))
            if math.isfinite(p) and 0.0 <= p <= 1.0:
                out.append(Observation(r.batch_id, r.tasting_id, r.fermentation_type, s, p, y))
    return out


def baseline_rates(rows: Iterable[TastingRow], obs: Sequence[Observation]) -> FloatArray:
    """Each observation's baseline: the leave-one-batch-out noticed rate of its series in its
    fermentation type over every tasted batch (linked or not), else over every type, else 0.5.
    A batch has one culture, so one type."""
    # [noticed, rated] per ("type", type, series), ("series", series) and ("batch", batch, series)
    counts: dict[tuple[str, ...], list[int]] = {}
    for r in rows:
        if not isinstance(r.ratings, Mapping):
            continue
        for s, value in r.ratings.items():
            y = _rating(value)
            if y is None:
                continue
            for key in (("type", r.fermentation_type, s), ("series", s), ("batch", r.batch_id, s)):
                row = counts.setdefault(key, [0, 0])
                row[0] += y
                row[1] += 1
    rates = []
    for o in obs:
        own_k, own_n = counts.get(("batch", o.batch_id, o.series), (0, 0))
        rate = NO_DATA_RATE
        for key in (("type", o.fermentation_type, o.series), ("series", o.series)):
            k, n = counts.get(key, (0, 0))
            if n - own_n > 0:
                rate = (k - own_k) / (n - own_n)
                break
        rates.append(rate)
    return np.asarray(rates, dtype=np.float64)


def _runs(p: FloatArray, strata: IntArray) -> tuple[IntArray, IntArray, IntArray, IntArray]:
    """For the AUC: the order sorting the observations by (stratum, P); where each run of equal
    (stratum, P) starts in it; where each stratum starts among the runs; each run's stratum's
    first run."""
    order = np.lexsort((p, strata)).astype(np.intp)
    sorted_p, sorted_s = p[order], strata[order]
    new_stratum = np.concatenate(([True], sorted_s[1:] != sorted_s[:-1]))
    new_p = np.concatenate(([True], sorted_p[1:] != sorted_p[:-1]))
    run_starts = np.flatnonzero(new_stratum | new_p)
    stratum_starts = np.flatnonzero(new_stratum[run_starts])
    first_run = stratum_starts[np.cumsum(new_stratum[run_starts]) - 1]
    return order, run_starts.astype(np.intp), stratum_starts.astype(np.intp), first_run


def _auc_rows(
    weights: FloatArray, y: FloatArray, runs: tuple[IntArray, IntArray, IntArray, IntArray]
) -> FloatArray:
    """The AUC for each row of observation weights (rows × observations; a weight is how many
    times the observation is drawn), over pairs in the same stratum only:
    Σ_noticed Σ_not, same stratum, w_i w_j (1[P_i > P_j] + ½ 1[P_i = P_j]) / Σ_strata W_noticed
    W_not, the Mann–Whitney U with average ranks. nan where no stratum has both classes."""
    order, run_starts, stratum_starts, first_run = runs
    w, ys = weights[:, order], y[order]
    pos = np.add.reduceat(w * ys, run_starts, axis=1)  # noticed weight per run, ascending P
    neg = np.add.reduceat(w * (1.0 - ys), run_starts, axis=1)
    before = np.cumsum(neg, axis=1) - neg  # not-noticed weight in the earlier runs
    below = before - before[:, first_run]  # ... of the same stratum: a lower P there
    num = (pos * (below + 0.5 * neg)).sum(axis=1)
    pairs = np.add.reduceat(pos, stratum_starts, axis=1) * np.add.reduceat(
        neg, stratum_starts, axis=1
    )
    den = pairs.sum(axis=1)
    out = np.full(len(den), np.nan)
    np.divide(num, den, out=out, where=den > 0)
    return out


def auc(p: FloatArray, y: FloatArray, strata: IntArray | None = None) -> float | None:
    """The AUC of P against noticed, ties counting one half, over pairs in the same stratum
    (None: one stratum, the plain AUC); None when no stratum has both classes."""
    if len(p) == 0:
        return None
    strata = np.zeros(len(p), dtype=np.intp) if strata is None else strata
    value = float(_auc_rows(np.ones((1, len(p))), y, _runs(p, strata))[0])
    return None if math.isnan(value) else value


def bootstrap(
    groups: IntArray,
    delta: FloatArray,
    p: FloatArray,
    y: FloatArray,
    strata: IntArray | None = None,
    *,
    seed: int = SEED,
    resamples: int = RESAMPLES,
    level: float = CI_LEVEL,
) -> Bootstrap:
    """The paired, batch-level bootstrap of d = Brier_model − Brier_baseline and of the AUC, on
    the same resamples. groups: each observation's batch (0 .. k − 1, every batch with at least
    one observation); delta: its (P − y)² − (b − y)²; strata: its AUC stratum (`auc`). A
    resample draws k batches with replacement; its observations are those of the batches drawn,
    each as many times as its batch: d = Σ c_b Δ_b / Σ c_b n_b (c_b: the times batch b is
    drawn), and the AUC weighted by c_b (UNDEFINED_AUC without a stratum of both classes)."""
    k, n_obs = int(groups.max()) + 1, len(groups)
    delta_sum = np.bincount(groups, weights=delta, minlength=k)
    n_sum = np.bincount(groups, minlength=k).astype(np.float64)
    runs = _runs(p, np.zeros(n_obs, dtype=np.intp) if strata is None else strata)
    rng = np.random.default_rng(seed)
    d = np.empty(resamples, dtype=np.float64)
    a = np.empty(resamples, dtype=np.float64)
    chunk = max(1, DRAWS_PER_CHUNK // max(k, n_obs))
    for start in range(0, resamples, chunk):
        rows = min(chunk, resamples - start)
        draw = rng.integers(0, k, size=(rows, k))
        flat = (draw + k * np.arange(rows)[:, None]).ravel()
        c = np.bincount(flat, minlength=rows * k).reshape(rows, k).astype(np.float64)
        d[start : start + rows] = (c @ delta_sum) / (c @ n_sum)
        found = _auc_rows(c[:, groups], y, runs)
        a[start : start + rows] = np.where(np.isnan(found), UNDEFINED_AUC, found)
    lo, hi = np.quantile(d, [(1.0 - level) / 2.0, (1.0 + level) / 2.0])
    return Bootstrap(float(lo), float(hi), float(np.quantile(a, (1.0 - level) / 2.0)))


def _r(x: float) -> float:
    return round(float(x), DIGITS)


def reliability(p: FloatArray, y: FloatArray, n_bins: int = N_BINS) -> tuple[Bin, ...]:
    """The reliability diagram: n_bins equal-width bins of P on [0, 1], P = 1 in the last."""
    index = np.minimum((p * n_bins).astype(np.intp), n_bins - 1)
    bins = []
    for i in range(n_bins):
        inside = index == i
        n = int(inside.sum())
        bins.append(Bin(
            _r(i / n_bins), _r((i + 1) / n_bins), n,
            _r(float(p[inside].mean())) if n else None, _r(float(y[inside].mean())) if n else None,
        ))  # fmt: skip
    return tuple(bins)


def compute(
    rows: Iterable[TastingRow],
    computed_at: datetime,
    *,
    seed: int = SEED,
    resamples: int = RESAMPLES,
) -> Report:
    """The gate's report on these tastings (see the module docstring)."""
    rows = list(rows)
    obs = observations(rows)
    p = np.asarray([o.p for o in obs], dtype=np.float64)
    y = np.asarray([o.y for o in obs], dtype=np.float64)
    bins = reliability(p, y)
    batches = sorted({o.batch_id for o in obs})
    at = computed_at if computed_at.tzinfo is not None else computed_at.replace(tzinfo=UTC)
    if not obs:
        return Report(at, 0, 0, 0, None, None, None, None, None, None, None, False, TOO_FEW, bins)
    err_model = (p - y) ** 2
    err_baseline = (baseline_rates(rows, obs) - y) ** 2
    brier_model, brier_baseline = float(err_model.mean()), float(err_baseline.mean())
    cells: dict[tuple[str, str], int] = {}  # the AUC's strata: the baseline's own cells
    strata = np.asarray(
        [cells.setdefault((o.fermentation_type, o.series), len(cells)) for o in obs],
        dtype=np.intp,
    )
    point_auc = auc(p, y, strata)
    boot = None
    reasons = [TOO_FEW]
    if len(batches) >= MIN_BATCHES:
        index = {b: i for i, b in enumerate(batches)}
        groups = np.asarray([index[o.batch_id] for o in obs], dtype=np.intp)
        boot = bootstrap(
            groups, err_model - err_baseline, p, y, strata, seed=seed, resamples=resamples
        )
        reasons = [why for why, failed in (
            (NOT_BETTER, not boot.ci_high < 0.0), (NO_SKILL, not boot.auc_low > AUC_MIN),
        ) if failed]  # fmt: skip
    return Report(
        computed_at=at, n_tastings=len({o.tasting_id for o in obs}), n_observations=len(obs),
        n_batches=len(batches), brier_model=_r(brier_model), brier_baseline=_r(brier_baseline),
        diff=_r(brier_model - brier_baseline), ci_low=None if boot is None else _r(boot.ci_low),
        ci_high=None if boot is None else _r(boot.ci_high),
        auc=None if point_auc is None else _r(point_auc),
        auc_low=None if boot is None else _r(boot.auc_low), passed=not reasons,
        reason="; ".join(reasons) or None, bins=bins,
    )  # fmt: skip


def calibrated_on(report: Report | None, now: datetime | None = None) -> int | None:
    """The cards' switch: the batch count when the report passed and is at most DISPLAY_FOR
    old; else None (Low / Med / High only)."""
    if report is None or not report.passed:
        return None
    if (now or datetime.now(UTC)) - report.computed_at > DISPLAY_FOR:
        return None  # the weekly recompute is failing: the pass is no longer current
    return report.n_batches


def report_json(r: Report) -> dict[str, Any]:
    """The full report, as stored and as admins get it (schemas.CalibrationReportOut)."""
    return {
        "computed_at": r.computed_at.isoformat(), "n_tastings": r.n_tastings,
        "n_observations": r.n_observations, "n_batches": r.n_batches,
        "brier_model": r.brier_model, "brier_baseline": r.brier_baseline, "diff": r.diff,
        "ci_low": r.ci_low, "ci_high": r.ci_high, "auc": r.auc, "auc_low": r.auc_low,
        "passed": r.passed, "reason": r.reason,
        "bins": [
            {"lo": b.lo, "hi": b.hi, "n": b.n, "mean_p": b.mean_p, "observed": b.observed}
            for b in r.bins
        ],
    }  # fmt: skip


def public_json(r: Report) -> dict[str, Any]:
    """The report every signed-in user gets (see Privacy in the module docstring): below
    MIN_BATCHES no score and no bin value; at any size no value for a bin of fewer than
    PUBLIC_BIN_MIN ratings. Counts, the decision and its reason stay."""
    body = report_json(r)
    small = r.n_batches < MIN_BATCHES
    if small:
        body |= dict.fromkeys(SCORES)
    body["bins"] = [
        b | {"mean_p": None, "observed": None} if small or b["n"] < PUBLIC_BIN_MIN else b
        for b in body["bins"]
    ]
    return body


def report_from_json(d: Mapping[str, Any]) -> Report:
    at = datetime.fromisoformat(str(d["computed_at"]))
    bins = tuple(
        Bin(float(b["lo"]), float(b["hi"]), int(b["n"]), b["mean_p"], b["observed"])
        for b in d["bins"]
    )
    return Report(
        computed_at=at if at.tzinfo is not None else at.replace(tzinfo=UTC),
        n_tastings=int(d["n_tastings"]), n_observations=int(d["n_observations"]),
        n_batches=int(d["n_batches"]), brier_model=d["brier_model"],
        brier_baseline=d["brier_baseline"], diff=d["diff"], ci_low=d["ci_low"],
        ci_high=d["ci_high"], auc=d["auc"], auc_low=d["auc_low"], passed=d["passed"] is True,
        reason=d["reason"], bins=bins,
    )  # fmt: skip


# ── the in-process cache: what the cards read ───────────────────────────

_latest: Report | None = None


def cached() -> Report | None:
    """The latest report this process has read or computed (None: none yet)."""
    return _latest


def remember(report: Report | None) -> None:
    global _latest
    _latest = report


# ── the database: rows in, reports stored ───────────────────────────────


async def load_rows(db: AsyncSession) -> list[TastingRow]:
    """Every tasting with its batch's type and its link's P series (None without one)."""
    found = await db.execute(
        select(
            Tasting.id, Tasting.batch_id, Culture.type, Tasting.t_h, Tasting.ratings,
            RecommendationLink.p_series,
        )
        .join(Batch, Batch.id == Tasting.batch_id)
        .join(Culture, Culture.id == Batch.culture_id)
        .outerjoin(RecommendationLink, RecommendationLink.batch_id == Tasting.batch_id)
    )  # fmt: skip
    return [
        TastingRow(str(tid), str(bid), ftype, float(t_h), ratings or {}, p_series)
        for tid, bid, ftype, t_h, ratings, p_series in found.tuples()
    ]


async def latest(db: AsyncSession) -> Report | None:
    """The newest stored report (None: never computed); the cache follows it. A row that does
    not validate as a report (another report format, e.g. one before the AUC condition) counts
    as none, so the schedule recomputes it."""
    found = await db.execute(
        select(CalibrationReport.report)
        .order_by(CalibrationReport.computed_at.desc(), CalibrationReport.id.desc())
        .limit(1)
    )
    body = found.scalar_one_or_none()
    report = None
    if body is not None:
        try:
            CalibrationReportOut.model_validate(body)
            report = report_from_json(body)
        except (KeyError, TypeError, ValueError):  # a pydantic ValidationError is a ValueError
            logger.exception("calibration: the latest report cannot be read; it is recomputed")
    remember(report)
    return report


async def recompute(db: AsyncSession, now: datetime | None = None) -> Report:
    """Compute a report on every tasting (in a worker thread), store it, keep the newest
    REPORTS_KEPT, commit, and cache it. The decision is logged (aggregates only)."""
    rows = await load_rows(db)
    report = await asyncio.to_thread(compute, rows, now or datetime.now(UTC))
    db.add(CalibrationReport(
        computed_at=report.computed_at, passed=report.passed, n_batches=report.n_batches,
        report=report_json(report),
    ))  # fmt: skip
    await db.flush()
    newest = await db.execute(
        select(CalibrationReport.id).order_by(
            CalibrationReport.computed_at.desc(), CalibrationReport.id.desc()
        )
    )
    old = list(newest.scalars())[REPORTS_KEPT:]
    if old:
        await db.execute(delete(CalibrationReport).where(CalibrationReport.id.in_(old)))
    await db.commit()
    remember(report)
    logger.info(
        "calibration gate %s: %d batches, %d ratings, Brier %s vs baseline %s, 90 %% CI of the "
        "difference [%s, %s], AUC %s (5th percentile %s)%s",
        "passed" if report.passed else "not passed", report.n_batches, report.n_observations,
        report.brier_model, report.brier_baseline, report.ci_low, report.ci_high, report.auc,
        report.auc_low, f" ({report.reason})" if report.reason else "",
    )  # fmt: skip
    return report


async def refresh(
    sessions: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> Report:
    """The latest report, recomputed first when there is none or it is STALE_AFTER old."""
    now = now or datetime.now(UTC)
    async with sessions() as db:
        report = await latest(db)
        if report is None or now - report.computed_at >= STALE_AFTER:
            report = await recompute(db, now)
    return report


async def run_schedule(sessions: async_sessionmaker[AsyncSession]) -> None:
    """The app's lifespan task: `refresh` at startup, then again whenever the report turns
    STALE_AFTER old. A connection error is retried after jobs.RETRY_S (the app starts even when
    the database is not reachable yet); any other error is logged and retried after an hour.
    Runs until cancelled."""
    while True:
        try:
            report = await refresh(sessions)
        except Exception as exc:
            if jobs.transient(exc):
                logger.warning("calibration: database unreachable, retrying: %s", exc)
                await asyncio.sleep(jobs.RETRY_S)
            else:
                logger.exception("calibration: the recompute failed")
                await asyncio.sleep(ERROR_RETRY_S)
            continue
        due = report.computed_at + STALE_AFTER - datetime.now(UTC)
        await asyncio.sleep(max(due.total_seconds(), MIN_SLEEP_S))
