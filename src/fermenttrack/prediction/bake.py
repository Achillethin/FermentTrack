"""A sourdough plan (planner or tracked batch) -> forecast shaped like PredictionOut, plus
phases and a summary; and the feeding chart (seed ratio -> peak time) in one stacked solve.

Phase boundaries: logged ones (the batch's stage changes) are facts; the rest are decided
from the calibrated ensemble in order: mix at the median levain peak (unless the plan
fixes the build time), end bulk at the median time to the target rise (unless fixed).
Readings only ever fall in phases that have started, so calibration runs on the known
phases first and the future boundaries follow from its posterior.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from fermenttrack.prediction import aroma, derived, population
from fermenttrack.prediction.engine import PI, SimulationError, Trajectories, simulate
from fermenttrack.prediction.inference import (
    MIN_ESS,
    OBS_SIGMA,
    Observation,
    weighted_quantiles,
)
from fermenttrack.prediction.inference import run as run_inference
from fermenttrack.prediction.priors import FloatArray, Prior
from fermenttrack.prediction.profiles import profile_for
from fermenttrack.prediction.service import (
    DISCLAIMER,
    MAX_OBS_PER_KEY,
    PredictionUnavailable,
    _first_crossing,
    _LRU,
    _milestone as _service_milestone,
    _organism_out,
    _OrganismPlan,
    _resample,
    learning_evidence,
    OrganismIn,
    _SOLVE_LOCK,
)
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from fermenttrack.prediction.sourdough import (
    STYLES,
    Build,
    Compiled,
    PhaseTrace,
    Plan,
    SourdoughModel,
    catalogue_flours,
    compile_plan,
    levain_rise,
    plan_to_dict,
    stack_params,
)

logger = logging.getLogger(__name__)

MODEL_VERSION = "sourdough-v1"
N_MEMBERS = 160
N_FALLBACK = 64
N_RESAMPLE = 128
GRID_POINTS = 161
PEAK_SEARCH_H = 48.0
BULK_SEARCH_H = 36.0
PEAKED = 0.97  # a peak counts once the rise has fallen 3 % below its maximum
METHOD = (
    "Levain -> dough -> proof as chained multi-species Monod / Luedeking-Piret ODE ensembles "
    "(cardinal temperature and pH, undissociated-acid inhibition, charge-balance pH on a "
    "flour-ash buffer, heterolactic ethanol/acetate split by hydration and temperature), a "
    "CO2 gas balance for the rise; literature priors, per-starter learned priors and your "
    "readings (adaptive multiple importance sampling)"
)
SD_DISCLAIMER = (
    "Model estimate from literature kinetics, not a measurement. Bands show the 90 % range "
    "over plausible starters; watch the dough, not only the clock."
)
LABELS = {
    "rise": "Rise (jar)",
    "ph": "pH",
    "tta": "TTA (mL 0.1 N / 10 g)",
    "fq": "Lactic : acetic (FQ)",
    "lactic_acid": "Lactic acid",
    "acetic_acid": "Acetic acid",
    "ethanol": "Ethanol",
    "maltose": "Maltose",
    "hexoses": "Glucose + fructose",
}
READING_KEYS = {"ph": "ph", "rise": "rise", "rise %": "rise", "tta": "tta"}
READING_RANGE = {"ph": (2.5, 7.5), "rise": (-20.0, 400.0), "tta": (0.0, 40.0)}


@dataclass(frozen=True)
class BakeInputs:
    plan: dict[str, Any]  # plan_to_dict(plan): hashable via JSON
    now_h: float = 0.0
    measurements: tuple[tuple[str, float, float], ...] = ()  # (type, t_h, value)
    known_bounds: tuple[float, ...] = ()  # logged phase starts after the levain (h)
    organisms: tuple[OrganismIn, ...] = ()  # tracked batch: resolved organisms (provenance)
    extra_organisms: tuple[str, ...] = ()  # custom attachments to model too
    population_priors: dict[str, dict[str, Prior]] = field(default_factory=dict)
    finished: bool = False

    def fingerprint(self) -> str:
        d = {
            "plan": self.plan,
            "now_h": round(self.now_h),
            "m": self.measurements,
            "b": self.known_bounds,
            "o": [(o.name, o.ec_numbers) for o in self.organisms],
            "x": self.extra_organisms,
            "pp": {
                org: {k: [v.median, v.lo, v.hi, v.scale] for k, v in ps.items()}
                for org, ps in sorted(self.population_priors.items())
            },
            "f": self.finished,
        }
        blob = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(f"{MODEL_VERSION}|{blob}".encode()).hexdigest()


_OUTPUTS = _LRU(32)
_POSTERIORS: _LRU = _LRU(16)


def forecast(plan: Plan, inputs: BakeInputs) -> dict[str, Any]:
    fp = inputs.fingerprint()
    hit = _OUTPUTS.get(fp)
    if hit is None:
        with _SOLVE_LOCK:
            hit = _OUTPUTS.get(fp)
            if hit is None:
                hit = _forecast(plan, inputs, fp)
                _OUTPUTS.put(fp, hit)
    return dict(hit)


def evidence_for(fp: str) -> list[population.Evidence] | None:
    """A finished batch's evidence if its forecast ran in this process ([] when it may not
    teach anything: tempered, misfitting readings, unlogged phase starts); None if not."""
    return _POSTERIORS.get(fp)


def phases_out(compiled: Compiled, bounds: list[float], horizon: float,
               measured: dict[int, float]) -> list[dict[str, Any]]:  # fmt: skip
    return [
        {
            "key": ph.key,
            "label": ph.label,
            "start_h": round(bounds[k], 2),
            "end_h": round(bounds[k + 1] if k + 1 < len(bounds) else horizon, 2),
            "temperature_c": measured.get(k, ph.temperature_c),
        }
        for k, ph in enumerate(compiled.phases)
    ]


def _observations(inputs: BakeInputs) -> tuple[list[Observation], list[dict[str, Any]]]:
    by_key: dict[str, list[tuple[float, float]]] = {}
    shown: list[dict[str, Any]] = []
    for typ, t, v in inputs.measurements:
        if not math.isfinite(v) or t < -1.0 or t > inputs.now_h + 1.0:
            continue
        t = max(t, 0.0)
        typ = typ.strip().lower()
        if typ == "temperature":
            continue  # forcing, not an observation (_measured_temps)
        key = READING_KEYS.get(typ)
        if key is None:
            continue
        lo, hi = READING_RANGE[key]
        if lo <= v <= hi:
            by_key.setdefault(key, []).append((t, v))
        else:
            shown.append({"key": key, "t_h": round(t, 3), "value": v, "used": False, "fits": None})
    used: list[Observation] = []
    for key, pts in by_key.items():
        pts.sort()
        pts = pts[-MAX_OBS_PER_KEY:]  # ponytail: keep the latest; bin like service if streams appear
        for t, v in pts:
            used.append(Observation(key, round(t, 3), v))
            shown.append({"key": key, "t_h": round(t, 3), "value": v, "used": True, "fits": True})
    shown.sort(key=lambda o: (o["key"], o["t_h"]))
    return used, shown


def _measured_temps(inputs: BakeInputs, bounds: list[float]) -> dict[int, float]:
    """Mean logged temperature per phase (ponytail: a constant per phase; a within-phase
    profile if bakers log several readings per phase)."""
    out: dict[int, list[float]] = {}
    for typ, t, v in inputs.measurements:
        if typ.strip().lower() != "temperature" or not (-5.0 <= v <= 60.0) or t > inputs.now_h + 1:
            continue
        k = int(np.searchsorted(bounds, t, side="right")) - 1
        out.setdefault(max(k, 0), []).append(v)
    return {k: float(np.mean(v)) for k, v in out.items()}


def _peak_times(t: FloatArray, rise: FloatArray) -> FloatArray:
    """(N,) time of each member's maximum rise, inf if it has not turned down yet."""
    i = np.argmax(rise, axis=1)
    top = rise[np.arange(len(i)), i]
    fell = rise[:, -1] < PEAKED * top
    return np.where(fell & (top > 5.0), t[i], np.inf)


def _q(times: FloatArray, w: FloatArray) -> tuple[dict[str, float | None], float]:
    q = weighted_quantiles(times, w, (0.05, 0.5, 0.95))

    def fmt(x: float) -> float | None:
        return None if not math.isfinite(x) else round(float(x), 2)

    return (
        {"p05": fmt(q[0]), "p50": fmt(q[1]), "p95": fmt(q[2])},
        round(float(np.sum(w[np.isfinite(times)])), 3),
    )


def _window(t: FloatArray, a: float, b: float) -> FloatArray:
    return np.asarray((t >= a - 1e-9) & (t <= b + 1e-9))


def _simulate(model: SourdoughModel, z: FloatArray, t: FloatArray) -> Trajectories:
    try:
        return model.simulate_z(z, t)
    except SimulationError as exc:
        raise PredictionUnavailable(str(exc)) from exc


# Search windows (h) for a phase's natural end: first window, hard cap. A window is extended
# while more than UNRESOLVED of the members have not reached their end yet.
SEARCH = {"levain": (24.0, PEAK_SEARCH_H), "bulk": (12.0, BULK_SEARCH_H)}
UNRESOLVED = 0.04  # the p95 of a band needs >= 95 % of members resolved
FINE_DT = 0.1  # h: phase grids, hence boundary resolution (6 min)


def _grid(a: float, b: float, extra: list[float] | tuple[float, ...] = ()) -> FloatArray:
    pts = [a, b, *(x for x in extra if a <= x <= b)]
    return np.unique(np.r_[np.arange(a, b, FINE_DT), pts])


@dataclass
class _Chain:
    traces: list[PhaseTrace]  # per phase, cut at the next phase's start
    bounds: list[float]
    milestones: list[dict[str, Any]]
    peak: FloatArray | None  # per-member levain peak (h), for downstream bands


def _run_chain(
    model: SourdoughModel,
    compiled: Compiled,
    known: list[float],
    z: FloatArray,
    w: FloatArray,
    now_h: float,
    obs_t: list[float],
    warnings: list[str],
) -> _Chain:
    """Each phase solved once, on a fine grid, from the state where the previous one ended.
    A phase ends where the batch logged the next stage, else after the plan's fixed hours,
    else at the ensemble's median natural end (levain peak, bulk target rise), never before
    now. Levain and bulk run on past their end so their milestones are not cut short."""
    n = len(z)
    bounds = list(known)
    traces: list[PhaseTrace] = []
    milestones: list[dict[str, Any]] = []
    peak: FloatArray | None = None
    prev: PhaseTrace | None = None
    pi: int | None = None
    phases = compiled.phases
    for k, ph in enumerate(phases):
        start = bounds[k]
        logged = bounds[k + 1] if k + 1 < len(bounds) else None
        fixed = start + ph.hours if ph.hours is not None else None
        stop = logged if logged is not None else fixed
        extra = [t for t in obs_t if t >= start] + [x for x in (logged, fixed) if x is not None]
        times: FloatArray | None = None
        if ph.key in ("levain", "bulk"):
            first, cap = SEARCH[ph.key]
            until = max(start + first, stop or 0.0, max(extra, default=0.0), now_h)
            tr = model.run_phase(k, z, _grid(start, until, extra), prev, pi)

            def natural(tr: PhaseTrace) -> FloatArray:
                if ph.key == "levain":
                    return _peak_times(tr.t, tr.rise)
                target = compiled.plan.dough.target_rise_pct if compiled.plan.dough else 75.0
                return _first_crossing(tr.t, tr.rise, np.full(n, target), below=False)

            times = natural(tr)
            while np.mean(~np.isfinite(times)) > UNRESOLVED and tr.t[-1] < start + cap - 1e-9:
                more_to = min(tr.t[-1] + first, start + cap)
                more = model.run_phase(k, z, _grid(tr.t[-1], more_to), tr, len(tr.t) - 1, extend=True)
                tr = tr.join(more)
                times = natural(tr)
            if ph.key == "levain":
                peak = times
                doubled = _first_crossing(tr.t, tr.rise, np.full(n, 100.0), below=False)
                milestones += [
                    _milestone("levain_doubled", f"{ph.label} doubled",
                               "ready to use for most breads", "rise", 100.0, "above", doubled, w),
                    _milestone("levain_peak", f"{ph.label} at its peak",
                               "most leavening power; it falls after this", "rise", 0.0, "max",
                               times, w),
                ]  # fmt: skip
            else:
                target = compiled.plan.dough.target_rise_pct if compiled.plan.dough else 75.0
                band = times
                if peak is not None and k == 1 and logged is None and phases[0].hours is None:
                    # each member would be mixed at its own peak, not at the median one
                    band = times + np.where(np.isfinite(peak), peak - start, 0.0)
                milestones.append(
                    _milestone("bulk_target", f"Bulk: +{target:g} % rise",
                               "shape now (aliquot jar)", "rise", target, "above", band, w)
                )  # fmt: skip
        else:  # proof / retard: a fixed duration (or up to now for a logged batch)
            until = max(fixed or start, now_h, max(extra, default=start))
            tr = model.run_phase(k, z, _grid(start, until, extra), prev, pi)
        q = _q(times, w)[0] if times is not None else None
        last = k + 1 == len(phases)
        if last:
            if fixed is not None:
                end = fixed
            elif q is not None:
                p50 = q["p50"] or tr.t[-1]
                end = (q["p95"] or tr.t[-1]) + (2.0 if ph.key == "bulk" else 0.15 * (p50 - start))
            else:
                end = tr.t[-1]
            end = max(end, now_h + 1.0)
        elif stop is not None:
            end = stop
        elif q is not None and q["p50"] is not None:
            end = max(float(q["p50"]), now_h)
        else:
            end = max(tr.t[-1], now_h)
            what = "peak" if ph.key == "levain" else "reach its target rise"
            warnings.append(
                f"Most model runs do not expect the {ph.label.lower()} to {what} within "
                f"{tr.t[-1] - start:g} h: the next step was placed there. Check the temperature "
                "and the amounts."
            )
        if end > tr.t[-1] + 1e-9:  # run on (a logged batch past its search window)
            more = model.run_phase(k, z, _grid(tr.t[-1], end, extra), tr, len(tr.t) - 1, extend=True)
            tr = tr.join(more)
        i = int(min(np.searchsorted(tr.t, end - 1e-9), len(tr.t) - 1))
        if last:
            traces.append(tr.cut(0, i + 1))
        else:
            if len(bounds) == k + 1:
                bounds.append(float(tr.t[i]))
            traces.append(tr.cut(0, i))  # the next phase starts at t[i]
            prev, pi = tr, i
    return _Chain(traces, bounds, milestones, peak)


def member_values(plan: Plan, inputs: BakeInputs) -> tuple[FloatArray, dict[str, FloatArray], FloatArray]:
    """(t, {ph, rise, tta} -> (members, len(t)), weights) behind forecast(plan, inputs), on
    its fine chain up to its horizon: for scoring held-out readings member by member
    (scripts/validate_forecasts.py). Not cached."""
    keep: dict[str, Any] = {}
    with _SOLVE_LOCK:
        _forecast(plan, inputs, inputs.fingerprint(), keep)
    return keep["t"], keep["values"], keep["weights"]


def _forecast(plan: Plan, inputs: BakeInputs, fp: str, keep: dict[str, Any] | None = None) -> dict[str, Any]:
    compiled = compile_plan(plan, inputs.extra_organisms)
    warnings: list[str] = []
    obs, shown = _observations(inputs)
    priors = inputs.population_priors
    known = _known_starts(compiled, inputs)
    measured = _measured_temps(inputs, known)
    seed = int(fp[:8], 16) % 2**31

    # 1. calibrate on the phases that have started (readings can only be there)
    model = SourdoughModel(compiled, list(known), priors, measured)
    obs_t = np.asarray(sorted({o.t_h for o in obs}), dtype=float)
    t_cal = np.unique(np.r_[0.0, obs_t, max(inputs.now_h, 1.0)])
    post = None
    for n in (N_MEMBERS, N_FALLBACK):
        try:
            post = run_inference(model, obs, t_cal, n=n, seed=seed)  # type: ignore[arg-type]
            break
        except SimulationError:
            continue
    if post is None:
        raise PredictionUnavailable("The model could not be computed for this bake within its budget.")
    z = _resample(post.z, post.weights, N_RESAMPLE, seed=int(fp[8:16], 16) % 2**31)
    w = np.full(len(z), 1.0 / len(z))
    learnable = inputs.finished and anchored(compiled, inputs)

    # 2. every phase once, from the calibrated ensemble: boundaries, rise milestones
    full = SourdoughModel(compiled, None, priors, measured)
    chain = _run_chain(full, compiled, known, z, w, inputs.now_h, list(obs_t), warnings)
    bounds, milestones = chain.bounds, chain.milestones
    tr, t_eval = _stitch(chain.traces, len(full.organisms))
    if keep is not None:  # member_values
        keep.update(t=t_eval, values={"ph": tr.ph, **{k: tr.extra[k] for k in ("rise", "tta")}}, weights=w)
    horizon = round(float(t_eval[-1]), 2)
    gi = _display_index(t_eval, bounds, obs_t)
    n = len(z)
    for v, note in ((4.2, "noticeably sour"), (4.0, "well acidified")):
        milestones.append(_milestone(
            f"ph_below_{str(v).replace('.', '_')}", f"pH below {v}", note, "ph", v, "below",
            _first_crossing(t_eval, tr.ph, np.full(n, v), below=True), w,
        ))  # fmt: skip

    series = _series(tr, full, gi, t_eval[gi], w)
    sd_profile = profile_for("sourdough")
    ar: aroma.AromaResult | None = None
    try:  # aroma must never break a bake forecast, nor taste and nutrition
        segs = _aroma_segments(full, chain.traces, z)
        ar = aroma.evaluate(segs, sd_profile, [], seed + 2, co2_escapes=False)
    except Exception:
        logger.exception("aroma layer failed for a sourdough plan")
    der: derived.Derived | None = None
    try:  # a dough keeps its gas, and a plan logs no recipe composition
        der = derived.evaluate(
            tr.pools, tr.ph, sd_profile, derived.UNKNOWN, seed=seed + 1, co2_escapes=False,
            aroma=ar,
        )
    except Exception:  # never break a bake forecast on the derived layer
        logger.exception("derived layer failed for a sourdough plan")
        warnings.append(derived.FAILED_WARNING)
    if der is not None:
        series += derived.series_out(der, gi, t_eval[gi], w)
        milestones += [
            m
            for ms in derived.taste_milestones(sd_profile)
            if (m := _service_milestone(ms, t_eval, der.values, w)) is not None
        ]
    fits = _check_fit(obs, tr, t_eval, w)
    for s in shown:
        if s["used"]:
            s["fits"] = (s["key"], s["t_h"]) not in fits
    if fits:
        warnings.append(
            f"{len(fits)} of your readings fall outside what the model explains for this bake "
            "(typo, or a starter unlike any the model knows): the calibration is approximate."
        )
    elif obs and (post.tempered < 1.0 or post.ess < 2 * MIN_ESS):
        warnings.append("Calibration is approximate: few model runs explain your readings well.")
    if inputs.finished and not anchored(compiled, inputs):
        warnings.append(
            "Log the move to bulk (and shaping) next time: without those times the app cannot "
            "learn from this bake."
        )
    temps = [p["temperature_c"] for p in phases_out(compiled, bounds, horizon, measured)]
    _POSTERIORS.put(
        fp,
        learning_evidence(model, obs, t_cal, post, seed, max(temps) - min(temps))
        if learnable and not fits
        else [],
    )

    phases = phases_out(compiled, bounds, horizon, measured)
    style = compiled.style
    plans = [
        _OrganismPlan(
            next((o for o in inputs.organisms if o.name == name), OrganismIn(name, ORGANISM_KINETICS[name].kingdom, ())),
            ORGANISM_KINETICS[name], True, None,
        )
        for name in compiled.organisms
    ]  # fmt: skip
    series_keys = {s["key"] for s in series}
    ph0 = float(weighted_quantiles(tr.ph[:, 0], w, (0.5,))[0])
    temps = [ph.temperature_c for ph in compiled.phases]
    assumptions = [
        f"Style: {style.name} ({style.native_name}), Type {style.type}: {style.description}",
        *(
            f"{p['label']}: {p['temperature_c']:g} °C from {_hm(p['start_h'])} to {_hm(p['end_h'])}."
            for p in phases
        ),
        "Flour buffering follows its ash (T-number); hydration and flour set how far the acids "
        "move pH and TTA.",
        "Rise is what a jar sample marked at mixing would show; a shaped loaf degassed at shaping "
        "rises less during the proof.",
    ]
    if plan.starter == "refrigerated":
        assumptions.append("Starter straight from the fridge: a longer lag than a ripe, active one.")
    if priors:
        assumptions.append("Your starter's own history shifted the priors (learned from past bakes).")
    if obs:
        assumptions.append(f"Calibrated on {len(obs)} of your readings.")
    assumptions += list(style.notes)
    sources = sorted(set(style.sources) | {s for p in plans if p.kin for s in p.kin.sources})
    return {
        "model": {
            "name": "FermentTrack sourdough engine",
            "version": MODEL_VERSION,
            "method": METHOD,
            "members": int(len(z)),
            "effective_members": round(min(float(post.ess), float(len(z))), 1),
            "confidence": "established" if style.seed != "dried" else "exploratory",
            "confidence_note": None,
            "validated": False,
            "sources": sources,
        },
        "fermentation_type": "sourdough",
        "started_at": None,
        "now_h": round(inputs.now_h, 3),
        "horizon_h": horizon,
        "horizon_options_h": [horizon],
        "temperature": {
            "forecast_c": temps[-1],
            "source": "expected",
            "type_default_c": style.temperature_c,
            "range_c": [min(temps), max(temps)],
            "readings": sum(1 for m in inputs.measurements if m[0].lower() == "temperature"),
        },
        "status": "calibrated" if obs else "prior_only",
        "series": series,
        "observations": shown,
        "milestones": milestones,
        "reference_lines": [],
        "organisms": [_organism_out(p, series_keys) for p in plans],
        "initial": {"source": "plan", "values": {"ph": round(ph0, 2)}},
        "assumptions": assumptions,
        "warnings": warnings,
        "disclaimer": SD_DISCLAIMER,
        "phases": phases,
        "summary": compiled.summary,
        "sensory": (
            derived.sensory_block(der, t_eval, w, gi, inputs.now_h, len(t_eval) - 1)
            if der is not None
            else None
        ),
    }


def _aroma_segments(
    model: SourdoughModel, traces: list[PhaseTrace], z: FloatArray
) -> list[aroma.Segment]:
    """One aroma segment per phase trace: its parameters and clock, the carried share and
    the phase's fresh flour. ponytail: a trace is cut just before the next mix, so the state
    carried into it is its last point (<= FINE_DT early); keep the boundary point if a
    fast-changing tracer ever needs it."""
    return [
        aroma.Segment(
            model.phase_params(k, z),
            Trajectories(t_h=x.t, pools=x.pools, biomass_g=x.biomass, ph=x.ph, y=x.y),
            catalogue_flours(model.phases[k]), x.start, model.phases[k].carry,
        )  # fmt: skip
        for k, x in enumerate(traces)
    ]


def _known_starts(compiled: Compiled, inputs: BakeInputs) -> list[float]:
    """Phase starts that are facts: logged stage changes, and plan-fixed durations that
    have already elapsed (a baker who mixed on schedule but never tapped "bulk")."""
    logged = [b for b in inputs.known_bounds if b > 0]
    known = [0.0]
    for k, ph in enumerate(compiled.phases[:-1]):
        if k < len(logged):
            known.append(logged[k])
        elif ph.hours is not None and known[-1] + ph.hours <= inputs.now_h:
            known.append(known[-1] + ph.hours)
        else:
            break
    return known


def anchored(compiled: Compiled, inputs: BakeInputs) -> bool:
    """A finished batch can teach the model only if every phase start is a fact: readings
    after an unlogged mix would otherwise be fitted to the wrong phase."""
    return len(_known_starts(compiled, inputs)) == len(compiled.phases)


def _stitch(traces: list[PhaseTrace], m: int) -> tuple[Trajectories, FloatArray]:
    t = np.concatenate([tr.t for tr in traces])
    cat = np.concatenate
    tr = Trajectories(
        t_h=t,
        pools=cat([x.pools for x in traces], axis=1),
        biomass_g=cat([x.biomass for x in traces], axis=1),
        ph=cat([x.ph for x in traces], axis=1),
        extra={k: cat([getattr(x, k) for x in traces], axis=1) for k in ("rise", "tta", "fq")},
    )
    return tr, t


def _display_index(t: FloatArray, bounds: list[float], obs_t: FloatArray) -> FloatArray:
    """~GRID_POINTS indices into the fine chain, always keeping phase starts and readings."""
    keep = set(np.linspace(0, len(t) - 1, GRID_POINTS).astype(int).tolist())
    for x in (*bounds, *obs_t.tolist()):
        keep.add(int(min(np.searchsorted(t, x - 1e-9), len(t) - 1)))
    return np.asarray(sorted(keep))


def _hm(h: float) -> str:
    return f"{int(h)}:{int(round((h % 1) * 60)):02d} h"


def _series(tr: Trajectories, model: SourdoughModel, gi: FloatArray, t_grid: FloatArray, w: FloatArray) -> list[dict[str, Any]]:
    values: dict[str, tuple[FloatArray, str, str]] = {
        "rise": (tr.extra["rise"], "rise", "%"),
        "ph": (tr.ph, "ph", ""),
        "tta": (tr.extra["tta"], "acidity", "mL"),
        "fq": (tr.extra["fq"], "acidity", "mol/mol"),
        "lactic_acid": (tr.pools[:, :, PI["lactic_acid"]], "products", "g/kg"),
        "acetic_acid": (tr.pools[:, :, PI["acetic_acid"]], "products", "g/kg"),
        "ethanol": (tr.pools[:, :, PI["ethanol"]], "products", "g/kg"),
        "maltose": (tr.pools[:, :, PI["maltose"]], "substrates", "g/kg"),
        "hexoses": (tr.pools[:, :, PI["hexoses"]], "substrates", "g/kg"),
    }
    for j, o in enumerate(model.organisms):
        assert o.cell_mass_g is not None
        x = tr.biomass_g[:, :, j]
        pop = np.maximum(np.log10(np.maximum(x, 1e-30) / o.cell_mass_g / 1000.0), 0.0)
        values[f"pop:{o.name}"] = (pop, "population", "log CFU/g")
    out = []
    for key, (v, group, unit) in values.items():
        q = weighted_quantiles(v[:, gi], w, (0.05, 0.5, 0.95))
        digits = 1 if key in ("rise", "fq") else 3
        out.append(
            {
                "key": key,
                "label": LABELS.get(key) or key.removeprefix("pop:"),
                "unit": unit,
                "group": group,
                "t_h": [round(float(x), 3) for x in t_grid],
                "p05": [round(float(x), digits) for x in q[0]],
                "p50": [round(float(x), digits) for x in q[1]],
                "p95": [round(float(x), digits) for x in q[2]],
            }
        )
    return out


def _check_fit(obs: list[Observation], tr: Trajectories, t_eval: FloatArray, w: FloatArray) -> set[tuple[str, float]]:
    idx = {float(t): i for i, t in enumerate(t_eval)}
    bad = set()
    for o in obs:
        pred = (tr.ph if o.key == "ph" else tr.extra[o.key])[:, idx[o.t_h]]
        med = float(weighted_quantiles(pred, w, (0.5,))[0])
        spread = float(np.sqrt(np.sum(w * (pred - np.sum(w * pred)) ** 2)))
        s_meas, s_model = OBS_SIGMA[o.key]
        if abs(o.value - med) > 3.0 * math.sqrt(spread**2 + s_meas**2 + s_model**2):
            bad.add((o.key, o.t_h))
    return bad


def _milestone(key: str, title: str, note: str, series: str, value: float, kind: str,
               times: FloatArray, w: FloatArray) -> dict[str, Any]:  # fmt: skip
    q, prob = _q(times, w)
    return {
        "key": key,
        "label": f"{title} ({note})",
        "title": title,
        "note": note,
        "threshold": {"series": series, "value": value, "kind": kind},
        "t_h": q,
        "probability": prob,
    }


# ── feeding chart ───────────────────────────────────────────────────────

_CHARTS = _LRU(32)


def feeding_chart(
    style_key: str,
    flour: tuple[tuple[str, float], ...],
    hydration_pct: float,
    temperature_c: float,
    starter: str,
    ratios: tuple[float, ...],
    population_priors: dict[str, dict[str, Prior]],
    members: int = 64,
) -> dict[str, Any]:
    """Peak time per seed ratio 1:r:r·h. One ensemble per ratio sharing the same z draws, so
    the ratios differ only by the dilution (common random numbers: the chart is monotone)."""
    key = json.dumps([style_key, flour, hydration_pct, temperature_c, starter, ratios,
                      {o: {k: [v.median, v.lo, v.hi] for k, v in p.items()} for o, p in sorted(population_priors.items())}],
                     default=str)  # fmt: skip
    hit = _CHARTS.get(key)
    if hit is not None:
        return dict(hit)
    style = STYLES[style_key]
    rng = np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    t = np.linspace(0.0, PEAK_SEARCH_H, 241)
    models, params = [], []
    z = None
    for r in ratios:
        plan = Plan(
            style_key,
            Build(100.0, 100.0 * r, 100.0 * r * hydration_pct / 100.0, flour, temperature_c),
            starter=starter,  # type: ignore[arg-type]
        )
        model = SourdoughModel(compile_plan(plan), [0.0], population_priors)
        if z is None:  # common random numbers: the ratios differ only by the dilution
            z = rng.standard_normal((members, model.dim))
        models.append(model)
        params.append(model.phase_params(0, z))
    assert z is not None
    with _SOLVE_LOCK:  # one stacked solve for every ratio
        try:
            tr = simulate(stack_params(params), t)
        except SimulationError as exc:
            raise PredictionUnavailable(str(exc)) from exc
    w = np.full(members, 1.0 / members)
    rows = []
    idx = np.arange(members)
    for i, (r, model, p) in enumerate(zip(ratios, models, params, strict=True)):
        blk = slice(i * members, (i + 1) * members)
        part = Trajectories(t_h=t, pools=tr.pools[blk], biomass_g=tr.biomass_g[blk], ph=tr.ph[blk])
        rise = levain_rise(model, part, p, z)
        peak = _peak_times(t, rise)
        doubled = _first_crossing(t, rise, np.full(members, 100.0), below=False)
        pq, _ = _q(peak, w)
        dq, _ = _q(doubled, w)
        i_peak = np.clip(np.searchsorted(t, np.where(np.isfinite(peak), peak, t[-1])), 0, len(t) - 1)
        rows.append(
            {
                "ratio": r,
                "label": f"1:{r:g}:{r * hydration_pct / 100:g}",
                "peak_h": pq,
                "doubled_h": dq,
                "ph_at_peak": round(float(np.median(part.ph[idx, i_peak])), 2),
                "rise_at_peak_pct": round(float(np.median(rise[idx, i_peak])), 0),
            }
        )
    out = {"temperature_c": temperature_c, "style": style.key, "rows": rows}
    _CHARTS.put(key, out)
    return dict(out)


def plan_json(plan: Plan) -> dict[str, Any]:
    return plan_to_dict(plan)
