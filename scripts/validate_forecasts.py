"""Leave-future-out validation of the forecasts: the check the prediction design names before
any "validated" label (2026-09-24-fermentation-prediction-design.md § 5; sourdough spec § 6.2).

For every finished batch with >= 3 usable readings (pH, gravity, Brix; sourdough batches with
a plan: pH, rise, TTA), at each cut point tau = one of its distinct reading times (all but the
last; at most --max-cuts, evenly spaced), forecast from what was logged up to tau and score
every later reading:

  * no leakage: readings, temperatures and stage changes after tau are dropped before the
    inputs are built (the forecast modules' own +1 h reading slack is never reached); the
    batch is unfinished at tau (now = tau); learned priors use only evidence recorded before
    the cut's wall-clock time, never the batch's own. Not truncatable (no history in the DB):
    recipe, organism attachments, plan and expected temperature, taken as last edited.
  * predictive distribution of a reading: each posterior member's latent value plus the
    likelihood's own reading error (Student-t, nu = 4, sd from inference.OBS_SIGMA),
    NOISE_DRAWS per member, weights kept. `band90` is the coverage of the latent 90 % band
    the app draws (no reading error): expect it below 0.9.
  * scores: PIT, coverage of the central 50 % / 90 % predictive intervals, fair CRPS
    (prediction/scoring.py). Baselines: `prior` = the same inputs with the readings removed
    (what calibration on the batch's own readings adds); `clim` = other batches of the same
    type and style that ended before the cut, their readings interpolated at the target time
    (>= 2 needed; the fair CRPS keeps a small ensemble comparable). Skill = 1 - CRPS/CRPS_ref.
  * aggregates per type / style / reading, with 90 % intervals from a bootstrap over batches
    (the pairs of one batch are correlated).

Usage: FERMENTTRACK_DATABASE_URL=... python scripts/validate_forecasts.py [--out report.json]
       [--variances '{"global": 0.1, "style": 0.26, ...}']  (score a REML proposal instead)
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import math
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.models import Batch
from fermenttrack.prediction import bake, population, scoring, service
from fermenttrack.prediction.inference import NU, OBS_SIGMA, plato_to_sg
from fermenttrack.prediction.profiles import profile_for
from fermenttrack.prediction.sourdough import STYLES, compile_plan, plan_from_dict, plan_to_dict
from fermenttrack.routers.prediction import _known_bounds, _utc, forecast_context

NOISE_DRAWS = 16
MIN_READINGS = 3
READINGS = ("ph", "gravity", "brix", "rise", "tta")
_RANGE = {
    "ph": (1.5, 9.0),
    "gravity": (0.95, 1.2),
    "brix": (0.0, 60.0),
    "rise": (-20.0, 400.0),
    "tta": (0.0, 40.0),
}


@dataclass(frozen=True)
class Reading:
    key: str
    t_h: float
    value: float


def is_bake(batch: Batch) -> bool:
    return batch.culture.type == "sourdough" and bool(batch.sourdough_plan)


def style_of(batch: Batch) -> str:
    plan = batch.sourdough_plan or {}
    return (
        batch.culture.style or (plan.get("style") if is_bake(batch) else None) or batch.culture.type
    )


def readings(batch: Batch) -> list[Reading]:
    """The batch's readings the forecast can be scored on, in model units."""
    started = _utc(batch.started_at)
    if is_bake(batch):
        keys = dict(bake.READING_KEYS)
    else:
        prof = profile_for(batch.culture.type)
        keys = {
            k: v
            for k, v in service.MEASUREMENT_KEYS.items()
            if (v == "ph" and prof.show_ph) or (v != "ph" and prof.show_density)
        }
    out = []
    for m in batch.measurements:
        key = keys.get(m.type.strip().lower())
        if key is None or m.value_numeric is None or not math.isfinite(m.value_numeric):
            continue
        out.append(
            Reading(key, (_utc(m.measured_at) - started).total_seconds() / 3600.0, m.value_numeric)
        )
    if any(r.key == "gravity" and 1.5 < r.value < 40.0 for r in out):  # a °Plato stream
        out = [replace(r, value=plato_to_sg(r.value)) if r.key == "gravity" else r for r in out]
    return sorted(
        (r for r in out if _RANGE[r.key][0] <= r.value <= _RANGE[r.key][1]),
        key=lambda r: (r.t_h, r.key),
    )


async def inputs_at(
    db: AsyncSession, batch: Batch, ctx: tuple, tau: float, with_readings: bool = True
) -> tuple[Any, Any]:
    """(plan or None, forecast inputs) as the app would have built them at tau h: the
    router's construction (routers/prediction.py) with everything after tau dropped."""
    recipe, organisms, enzymes = ctx
    culture = batch.culture
    started = _utc(batch.started_at)

    def keep(typ: str, t: float) -> bool:
        return t <= tau and (
            with_readings
            or typ.strip().lower() not in bake.READING_KEYS
            and typ.strip().lower() not in service.MEASUREMENT_KEYS
        )

    timed = [
        (m, (_utc(m.measured_at) - started).total_seconds() / 3600.0)
        for m in sorted(batch.measurements, key=lambda m: m.measured_at)
    ]
    org_in = {
        o.name: service.OrganismIn(o.name, o.kingdom, tuple(sorted(enzymes.get(o.id, []))))
        for o, *_ in organisms
    }
    common = dict(
        ferment_type=culture.type,
        style=style_of(batch),
        baker=culture.owner_id,
        starter=culture.id,
        exclude_batch=batch.id,
        recorded_before=started + timedelta(hours=tau),
    )
    if is_bake(batch):
        plan = plan_from_dict(batch.sourdough_plan or {})
        style_names = set(STYLES[plan.style].organisms)
        extra = tuple(
            o.name for o, src, _ in organisms if src != "default" and o.name not in style_names
        )
        priors = await population.learned_priors(db, compile_plan(plan, extra).organisms, **common)
        return plan, bake.BakeInputs(
            plan=plan_to_dict(plan),
            now_h=tau,
            measurements=tuple(
                (m.type, t, m.value_numeric)
                for m, t in timed
                if m.value_numeric is not None and keep(m.type, t)
            ),
            known_bounds=tuple(
                itertools.takewhile(lambda b: b <= tau, _known_bounds(batch, started))
            ),
            organisms=tuple(org_in[o.name] for o, *_ in organisms),
            extra_organisms=extra,
            population_priors=priors,
        )
    priors = await population.learned_priors(db, [o.name for o, *_ in organisms], **common)
    return None, service.PredictionInputs(
        fermentation_type=culture.type,
        now_h=tau,
        expected_temperature_c=batch.expected_temperature_c,
        organisms=tuple(org_in[n] for n in sorted(org_in)),
        organism_source="custom" if any(t[1] != "default" for t in organisms) else "default",
        recipe=recipe,
        measurements=tuple(
            service.MeasurementIn(m.type, t, m.value_numeric)
            for m, t in timed
            if m.type != "note" and keep(m.type, t)
        ),
        population_priors=priors,
    )


def members(plan: Any, inputs: Any, horizon_h: float) -> tuple[np.ndarray, dict, np.ndarray]:
    if plan is not None:
        return bake.member_values(plan, inputs)
    return service.member_values(inputs, horizon_h)


def at(t: np.ndarray, values: np.ndarray, x: float) -> np.ndarray | None:
    """Members' values at x (linear in time), None past the forecast's end."""
    if not t[0] <= x <= t[-1]:
        return None
    i = int(np.clip(np.searchsorted(t, x), 1, len(t) - 1))
    f = (x - t[i - 1]) / (t[i] - t[i - 1]) if t[i] > t[i - 1] else 1.0
    return (1 - f) * values[:, i - 1] + f * values[:, i]


def predictive(latent: np.ndarray, w: np.ndarray, key: str, rng: np.random.Generator):
    s_meas, s_model = OBS_SIGMA[key]
    noise = math.hypot(s_meas, s_model) * rng.standard_t(NU, (len(latent), NOISE_DRAWS))
    return (latent[:, None] + noise).ravel(), np.repeat(w / NOISE_DRAWS, NOISE_DRAWS)


def cut_points(rs: list[Reading], max_cuts: int) -> list[float]:
    times = sorted({r.t_h for r in rs})[:-1]
    if len(times) > max_cuts:
        times = [times[i] for i in np.linspace(0, len(times) - 1, max_cuts).round().astype(int)]
    return times


async def evaluate(db: AsyncSession, max_cuts: int = 12, seed: int = 0) -> list[dict[str, Any]]:
    """One record per (batch, cut, later reading)."""
    rng = np.random.default_rng(seed)
    res = await db.execute(
        select(Batch)
        .where(Batch.outcome != "in_progress")
        .options(selectinload(Batch.measurements), selectinload(Batch.culture))
    )
    batches = [b for b in res.scalars() if len(readings(b)) >= MIN_READINGS]
    curves = {
        b.id: (
            b.culture.type,
            style_of(b),
            _utc(b.ended_at or b.stage_entered_at),
            {k: [(r.t_h, r.value) for r in readings(b) if r.key == k] for k in READINGS},
        )
        for b in batches
    }
    pairs: list[dict[str, Any]] = []
    for batch in batches:
        rs = readings(batch)
        ctx = await forecast_context(db, batch)
        typ, style, _, _ = curves[batch.id]
        for tau in cut_points(rs, max_cuts):
            later = [r for r in rs if r.t_h > tau]
            horizon = max(r.t_h for r in later) + 1.0
            wall = _utc(batch.started_at) + timedelta(hours=tau)
            try:
                plan, inp = await inputs_at(db, batch, ctx, tau)
                _, inp0 = await inputs_at(db, batch, ctx, tau, with_readings=False)
                fc, fc0 = members(plan, inp, horizon), members(plan, inp0, horizon)
            except service.PredictionUnavailable:
                continue
            for r in later:
                latent, latent0 = at(fc[0], fc[1][r.key], r.t_h), at(fc0[0], fc0[1][r.key], r.t_h)
                if latent is None or latent0 is None:
                    continue  # past the forecast's own horizon
                x, w = predictive(latent, fc[2], r.key, rng)
                x0, w0 = predictive(latent0, fc0[2], r.key, rng)
                clim = [
                    np.interp(r.t_h, *zip(*c[3][r.key], strict=True))
                    for bid, c in curves.items()
                    if bid != batch.id
                    and c[:2] == (typ, style)
                    and c[2] < wall
                    and len(c[3][r.key]) >= 2
                    and c[3][r.key][0][0] <= r.t_h <= c[3][r.key][-1][0]
                ]
                pairs.append(
                    {
                        "batch": str(batch.id),
                        "type": typ,
                        "style": style,
                        "key": r.key,
                        "cut_h": round(tau, 3),
                        "t_h": round(r.t_h, 3),
                        "lead_h": round(r.t_h - tau, 3),
                        "y": r.value,
                        "pit": scoring.pit(x, r.value, w),
                        "pit_latent": scoring.pit(latent, r.value, fc[2]),
                        "crps": scoring.crps_ensemble(x, r.value, w),
                        "crps_prior": scoring.crps_ensemble(x0, r.value, w0),
                        "crps_clim": scoring.crps_ensemble(clim, r.value)
                        if len(clim) >= 2
                        else None,
                    }
                )
    return pairs


def _metrics(ps: list[dict[str, Any]]) -> dict[str, float]:
    pit = [p["pit"] for p in ps]
    clim = [p for p in ps if p["crps_clim"] is not None]
    return {
        "cov50": float(np.mean(scoring.covered(pit, 0.5))),
        "cov90": float(np.mean(scoring.covered(pit, 0.9))),
        "band90": float(np.mean(scoring.covered([p["pit_latent"] for p in ps], 0.9))),
        "crps": float(np.mean([p["crps"] for p in ps])),
        "skill_prior": scoring.skill([p["crps"] for p in ps], [p["crps_prior"] for p in ps]),
        "skill_clim": scoring.skill([p["crps"] for p in clim], [p["crps_clim"] for p in clim])
        if clim
        else float("nan"),
    }


def summarise(pairs: list[dict[str, Any]], boot: int = 500, seed: int = 0) -> list[dict[str, Any]]:
    """Per (type, style, reading) and per (type, all styles, reading): metrics with 90 %
    bootstrap intervals over batches."""
    rng = np.random.default_rng(seed)
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for p in pairs:
        for style in (p["style"], "*"):
            groups.setdefault((p["type"], style, p["key"]), []).append(p)
    rows = []
    for (typ, style, key), ps in sorted(groups.items()):
        by: dict[str, list[dict[str, Any]]] = {}
        for p in ps:
            by.setdefault(p["batch"], []).append(p)
        ids = list(by)
        draws = (
            [
                _metrics([p for i in rng.choice(len(ids), len(ids)) for p in by[ids[i]]])
                for _ in range(boot)
            ]
            if len(ids) > 1
            else []
        )
        m = _metrics(ps)
        ci = (
            {
                k: [float(np.nanpercentile([d[k] for d in draws], q)) for q in (5, 95)]
                for k in ("cov90", "skill_prior", "skill_clim")
            }
            if draws
            else {}
        )
        rows.append(
            {
                "type": typ,
                "style": style,
                "key": key,
                "batches": len(ids),
                "pairs": len(ps),
                **m,
                "ci90": ci,
                "pit_hist": scoring.pit_histogram([p["pit"] for p in ps]),
            }
        )
    return rows


def _fmt(x: float | None) -> str:
    return "-" if x is None or not math.isfinite(x) else f"{x:.2f}"


def _ci(pair: list[float] | None) -> str:
    return f"[{_fmt(pair[0])}, {_fmt(pair[1])}]" if pair else "-"


async def main(out: str, max_cuts: int) -> None:
    from fermenttrack.database import async_session_maker

    async with async_session_maker() as db:
        pairs = await evaluate(db, max_cuts)
    table = summarise(pairs)
    print(f"{len(pairs)} forecast-reading pairs from {len({p['batch'] for p in pairs})} batches\n")
    head = (
        "type style key batches pairs cov50 cov90 cov90_ci band90 crps ss_prior ss_prior_ci ss_clim"
    )
    print("	".join(head.split()))
    for r in table:
        ci = r["ci90"]
        cells = [r["type"], r["style"], r["key"], str(r["batches"]), str(r["pairs"])]
        cells += [_fmt(r[k]) for k in ("cov50", "cov90")] + [_ci(ci.get("cov90"))]
        cells += [_fmt(r["band90"]), f"{r['crps']:.3f}", _fmt(r["skill_prior"])]
        cells += [_ci(ci.get("skill_prior")), _fmt(r["skill_clim"])]
        print("	".join(cells))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {"noise_draws": NOISE_DRAWS, "max_cuts": max_cuts, "table": table, "pairs": pairs},
            f,
            indent=1,
            default=str,
        )
    print(f"\nwritten: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default="forecast_validation.json")
    ap.add_argument("--max-cuts", type=int, default=12)
    ap.add_argument(
        "--variances", help="JSON: hierarchy variances to use instead of the fixed ones"
    )
    a = ap.parse_args()
    if a.variances:  # in place: population.predictive's default argument is this dict
        population.VARIANCES.update(json.loads(a.variances))
    asyncio.run(main(a.out, a.max_cuts))
