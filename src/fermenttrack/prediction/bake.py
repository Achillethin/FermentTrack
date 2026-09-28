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
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from fermenttrack.prediction.engine import PI, SimulationError, Trajectories
from fermenttrack.prediction.inference import (
    MIN_ESS,
    OBS_SIGMA,
    Observation,
    weighted_quantiles,
)
from fermenttrack.prediction.inference import run as run_inference
from fermenttrack.prediction.priors import FloatArray, Prior
from fermenttrack.prediction.service import (
    DISCLAIMER,
    MAX_OBS_PER_KEY,
    PredictionUnavailable,
    _first_crossing,
    _LRU,
    _organism_out,
    _OrganismPlan,
    _resample,
    OrganismIn,
    _SOLVE_LOCK,
)
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from fermenttrack.prediction.sourdough import (
    STYLES,
    Build,
    Compiled,
    Plan,
    SourdoughModel,
    compile_plan,
    plan_to_dict,
)

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


def posterior_for(fp: str) -> tuple[SourdoughModel, FloatArray, FloatArray] | None:
    """(model, z, weights) of a batch forecast computed in this process, for pooling."""
    return _POSTERIORS.get(fp)


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


def _natural_ends(
    compiled: Compiled,
    known: list[float],
    z: FloatArray,
    w: FloatArray,
    now_h: float,
    priors: dict[str, dict[str, Prior]],
    measured: dict[int, float],
    warnings: list[str],
) -> tuple[list[float], list[dict[str, Any]], float | None]:
    """Phase starts for every phase, the rise milestones, and the natural end (p95) of an
    open-ended last phase. A levain ends at its peak, a bulk at the target rise, unless the
    plan fixes the time or the batch logged the next stage. Each natural end comes from the
    phase run on past its own end (the peak is not cut short by an early mix)."""
    bounds = list(known)
    milestones: list[dict[str, Any]] = []
    n = len(z)
    tail: float | None = None
    for k, ph in enumerate(compiled.phases):
        start = bounds[k]
        times: FloatArray | None = None
        search = PEAK_SEARCH_H if ph.key == "levain" else BULK_SEARCH_H
        if ph.key in ("levain", "bulk"):
            model = SourdoughModel(compiled, bounds[: k + 1], priors, measured)
            t = np.linspace(start, start + search, 241)
            rise = _simulate(model, z, t).extra["rise"]
            if ph.key == "levain":
                doubled = _first_crossing(t, rise, np.full(n, 100.0), below=False)
                times = _peak_times(t, rise)
                milestones += [
                    _milestone("levain_doubled", f"{ph.label} doubled",
                               "ready to use for most breads", "rise", 100.0, "above", doubled, w),
                    _milestone("levain_peak", f"{ph.label} at its peak",
                               "most leavening power; it falls after this", "rise", 0.0, "max",
                               times, w),
                ]  # fmt: skip
                what = f"the {ph.label.lower()} to peak"
            else:
                target = compiled.plan.dough.target_rise_pct if compiled.plan.dough else 75.0
                times = _first_crossing(t, rise, np.full(n, target), below=False)
                milestones.append(
                    _milestone("bulk_target", f"Bulk: +{target:g} % rise",
                               "shape now (aliquot jar)", "rise", target, "above", times, w)
                )  # fmt: skip
                what = f"the dough to rise {target:g} %"
        q = _q(times, w)[0] if times is not None else None
        if k + 1 < len(compiled.phases):
            if k + 1 < len(bounds):
                continue  # logged
            if ph.hours is not None:
                end = start + ph.hours
            elif q is not None and q["p50"] is not None:
                end = float(q["p50"])
            else:
                end = start + search
                warnings.append(
                    f"Most model runs do not expect {what} within {search:g} h: the next step "
                    "was placed at that limit. Check the temperature and the amounts."
                )
            bounds.append(max(end, now_h))
        elif ph.hours is None and q is not None:
            tail = q["p95"] or q["p50"] or (start + search)
    return bounds, milestones, tail


def _forecast(plan: Plan, inputs: BakeInputs, fp: str) -> dict[str, Any]:
    compiled = compile_plan(plan, inputs.extra_organisms)
    warnings: list[str] = []
    obs, shown = _observations(inputs)
    priors = inputs.population_priors
    known = [0.0, *[b for b in inputs.known_bounds if b > 0]][: len(compiled.phases)]
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
    _POSTERIORS.put(fp, (model, post.z, post.weights))

    # 2. future phase boundaries and the rise milestones from the calibrated ensemble
    bounds, milestones, tail = _natural_ends(
        compiled, known, z, w, inputs.now_h, priors, measured, warnings
    )
    last = compiled.phases[-1]
    if last.hours is not None:
        horizon = bounds[-1] + last.hours
    else:
        horizon = (tail or bounds[-1] + 12.0) + (2.0 if last.key == "bulk" else 0.15 * (tail or 12.0))
    horizon = round(max(horizon, inputs.now_h + 1.0, 2.0), 1)

    # 3. the full chain over the display window
    full = SourdoughModel(compiled, bounds, priors, measured)
    grid = np.linspace(0.0, horizon, GRID_POINTS)
    t_eval = np.unique(np.concatenate([grid, obs_t]))
    gi = np.searchsorted(t_eval, grid)
    tr = _simulate(full, z, t_eval)
    n = len(z)
    for v, note in ((4.2, "noticeably sour"), (4.0, "well acidified")):
        milestones.append(_milestone(
            f"ph_below_{str(v).replace('.', '_')}", f"pH below {v}", note, "ph", v, "below",
            _first_crossing(t_eval, tr.ph, np.full(n, v), below=True), w,
        ))  # fmt: skip

    series = _series(tr, full, gi, t_eval[gi], w)
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

    phases = [
        {
            "key": ph.key,
            "label": ph.label,
            "start_h": round(bounds[k], 2),
            "end_h": round(bounds[k + 1] if k + 1 < len(bounds) else horizon, 2),
            "temperature_c": measured.get(k, ph.temperature_c),
        }
        for k, ph in enumerate(compiled.phases)
    ]
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
    }


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
    members: int = 40,
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
    rows = []
    rng = np.random.default_rng(int(hashlib.sha256(key.encode()).hexdigest()[:8], 16))
    z = None
    with _SOLVE_LOCK:
        for r in ratios:
            plan = Plan(
                style_key,
                Build(100.0, 100.0 * r, 100.0 * r * hydration_pct / 100.0, flour, temperature_c),
                starter=starter,  # type: ignore[arg-type]
            )
            model = SourdoughModel(compile_plan(plan), [0.0], population_priors)
            if z is None:
                z = rng.standard_normal((members, model.dim))
            t = np.linspace(0.0, PEAK_SEARCH_H, 241)
            tr = _simulate(model, z, t)
            w = np.full(members, 1.0 / members)
            peak = _peak_times(t, tr.extra["rise"])
            doubled = _first_crossing(t, tr.extra["rise"], np.full(members, 100.0), below=False)
            pq, _ = _q(peak, w)
            dq, _ = _q(doubled, w)
            i_peak = np.clip(np.searchsorted(t, np.where(np.isfinite(peak), peak, t[-1])), 0, len(t) - 1)
            ph_at = tr.ph[np.arange(members), i_peak]
            rise_at = tr.extra["rise"][np.arange(members), i_peak]
            rows.append(
                {
                    "ratio": r,
                    "label": f"1:{r:g}:{r * hydration_pct / 100:g}",
                    "peak_h": pq,
                    "doubled_h": dq,
                    "ph_at_peak": round(float(np.median(ph_at)), 2),
                    "rise_at_peak_pct": round(float(np.median(rise_at)), 0),
                }
            )
    out = {"temperature_c": temperature_c, "style": style.key, "rows": rows}
    _CHARTS.put(key, out)
    return dict(out)


def plan_json(plan: Plan) -> dict[str, Any]:
    return plan_to_dict(plan)
