"""Batch -> fermentation forecast: gather inputs, compile the kinetic model, condition it on
the batch's readings, and shape the bands, milestones and provenance the UI shows.

Pure (no DB): the router builds PredictionInputs. Design:
docs/superpowers/specs/2026-09-24-fermentation-prediction-design.md.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from fermenttrack.composition import to_grams
from fermenttrack.prediction.engine import PI, Trajectories, simulate
from fermenttrack.prediction.inference import (
    OBS_SIGMA,
    Observation,
    density_series,
    plato_to_sg,
    solids_offset,
    weighted_quantiles,
)
from fermenttrack.prediction.inference import run as run_inference
from fermenttrack.prediction.model import ModelSpec, TemperatureSchedule
from fermenttrack.prediction.organisms import ORGANISM_KINETICS, Channel, OrganismKinetics
from fermenttrack.prediction.priors import FloatArray, Prior
from fermenttrack.prediction.profiles import (
    ADDED_MOLD_INOCULUM,
    ADDED_ORGANISM_INOCULUM,
    FermentProfile,
    Milestone,
    profile_for,
)

MODEL_VERSION = "kinetic-v1"
N_MEMBERS = 160  # prior draws per inference round
N_WHATIF = 96  # posterior members re-simulated for a what-if temperature
GRID_POINTS = 161
MAX_HORIZON_H = 8760.0
MAX_OBS_PER_KEY = 30  # denser streams (iSpindel) are binned: correlated errors
TEMP_RANGE_C = (-5.0, 60.0)

DISCLAIMER = (
    "Model estimate from literature kinetics, not a measurement. Bands show the 90 % range "
    "over plausible parameters; real batches vary more. Never use this to decide food "
    "safety: measure pH."
)
METHOD = (
    "Multi-species Monod / Luedeking-Piret ODE ensemble with cardinal temperature, pH and "
    "water-activity models, undissociated-acid inhibition and charge-balance pH, compiled "
    "from the batch's organism set; literature priors reweighted on your readings by "
    "adaptive multiple importance sampling"
)

LABELS: dict[str, str] = {
    "ph": "pH",
    "sugars_total": "Sugars (total)",
    "sucrose": "Sucrose",
    "hexoses": "Glucose + fructose",
    "lactose": "Lactose",
    "maltose": "Maltose",
    "starch": "Starch",
    "protein": "Protein",
    "amino_acids": "Amino acids (free)",
    "ethanol": "Ethanol",
    "lactic_acid": "Lactic acid",
    "acetic_acid": "Acetic acid",
    "gluconic_acid": "Gluconic acid",
    "co2": "CO₂ (cumulative)",
    "gravity": "Specific gravity",
    "brix": "Brix (refractometer)",
    "mycelium": "Mycelium growth",
    "koji_enzyme": "Koji enzyme activity",
}
SUBSTRATES = ("sugars_total", "sucrose", "hexoses", "lactose", "maltose", "starch", "protein")
PRODUCTS = ("lactic_acid", "acetic_acid", "gluconic_acid", "ethanol", "co2", "amino_acids")
SUGAR_KEYS = ("sucrose", "hexoses", "lactose", "maltose")
MEASUREMENT_KEYS = {"ph": "ph", "gravity": "gravity", "brix": "brix", "sg": "gravity"}
DENSITY_TYPES_IGNORED = "milk and solid ferments"

# Marker enzymes per pathway, to check against the batch's KEGG reference graph.
_LDH = ("1.1.1.27", "1.1.1.28")
_ALCOHOLIC = ("4.1.1.1", "1.1.1.1")
_AAB = ("1.1.5.5", "1.2.5.2", "1.2.1.3")
_GLUCONATE = ("1.1.5.2",)
_AMYLASES = ("3.2.1.1", "3.2.1.3", "3.2.1.20")


# ── inputs ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RecipeIn:
    name: str
    quantity: float | None
    unit: str | None
    per_100g: dict[str, float]
    role: str


@dataclass(frozen=True)
class MeasurementIn:
    type: str
    t_h: float
    value: float | None


@dataclass(frozen=True)
class OrganismIn:
    name: str
    kingdom: str
    ec_numbers: tuple[str, ...]  # KEGG enzymes the reference graph links to it


@dataclass(frozen=True)
class PredictionInputs:
    fermentation_type: str
    now_h: float
    expected_temperature_c: float | None
    organisms: tuple[OrganismIn, ...]
    organism_source: str  # "default" | "custom"
    recipe: tuple[RecipeIn, ...]
    measurements: tuple[MeasurementIn, ...]
    finished: bool = False

    def fingerprint(self) -> str:
        d = asdict(self)
        d["now_h"] = round(self.now_h)  # the forecast moves on hourly, not per request
        blob = json.dumps(d, sort_keys=True, default=str)
        return hashlib.sha256(f"{MODEL_VERSION}|{blob}".encode()).hexdigest()


# ── output (plain dicts shaped like schemas.PredictionOut) ──────────────


@dataclass
class _Initial:
    pools: dict[str, float]
    protein_total: float
    salt_wps: float
    source: str  # recipe | typical_recipe
    coverage: float | None
    starter_fraction: float | None
    starter_logged: bool
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _initial_state(profile: FermentProfile, recipe: tuple[RecipeIn, ...]) -> _Initial:
    total = water = salt = starter = mapped = 0.0
    pools: dict[str, float] = {}
    unmapped: list[str] = []
    unquantified: list[str] = []
    starch_estimated: list[str] = []

    def add(k: str, g: float) -> None:
        pools[k] = pools.get(k, 0.0) + g

    for item in recipe:
        grams = to_grams(item.quantity, item.unit)
        if grams is None:
            unquantified.append(item.name)
            continue
        total += grams
        n = item.per_100g
        if item.role == "starter":
            starter += grams
        if item.name == "Salt" or n.get("sodium", 0.0) >= 30.0:
            salt += grams
            continue
        if not n:
            unmapped.append(item.name)
            water += 0.9 * grams  # starters, tea, cultures: assume mostly water
            continue
        mapped += grams
        f = grams / 100.0
        water += n.get("water", 0.0) * f
        known = 0.0
        for src, dst in (
            ("sucrose", "sucrose"), ("glucose", "hexoses"), ("fructose", "hexoses"),
            ("galactose", "hexoses"), ("lactose", "lactose"), ("maltose", "maltose"),
        ):  # fmt: skip
            if src in n:
                add(dst, n[src] * f)
                known += n[src] * f
        unexplained = n.get("sugars_total", 0.0) * f - known
        if unexplained > 0:
            add(profile.sugar_default, unexplained)
        starch = n.get("starch")
        if starch is None and "carbohydrate" in n:
            # SR Legacy often omits starch for grains/flours: carbohydrate by difference
            # minus fiber and sugars is mostly starch there.
            est = n["carbohydrate"] - n.get("fiber", 0.0) - n.get("sugars_total", 0.0)
            if est > 1.0:
                starch = est
                starch_estimated.append(item.name)
        add("starch", (starch or 0.0) * f * profile.starch_accessible)
        add("protein", n.get("protein", 0.0) * f)
        add("ethanol", n.get("alcohol", 0.0) * f)

    warnings: list[str] = []
    notes: list[str] = []
    if starch_estimated:
        notes.append(
            "Starch estimated as carbohydrate - fiber - sugars (USDA reports no starch) for: "
            f"{', '.join(starch_estimated)}."
        )
    coverage = mapped / total if total else 0.0  # of the logged mass, before any added water
    if profile.min_water_fraction and total > 0 and water < profile.min_water_fraction * total:
        added = (profile.min_water_fraction * total - water) / (1.0 - profile.min_water_fraction)
        water += added
        total += added
        warnings.append(
            "Your recipe looks like dry weights, so the grains/beans were assumed soaked and "
            f"cooked (water brought to {round(profile.min_water_fraction * 100)} % of the mass). "
            "Log cooked weights for a closer forecast."
        )
    fermentable = sum(pools.get(k, 0.0) for k in (*SUGAR_KEYS, "starch", "ethanol"))
    if total <= 0 or fermentable <= 0:
        rec = dict(profile.typical_recipe)
        water_g = rec.pop("water")
        salt_g = rec.pop("salt", 0.0)
        pools0 = {
            k: v * (profile.starch_accessible if k == "starch" else 1.0) for k, v in rec.items()
        }
        why = (
            "no quantified ingredients with USDA data"
            if total <= 0
            else "the logged ingredients have no fermentable sugar in USDA data"
        )
        warnings.append(f"Starting point: {why}, so a typical {profile.type} recipe was assumed.")
        init = _Initial(
            pools=pools0,
            protein_total=pools0.get("protein", 0.0),
            salt_wps=100.0 * salt_g / (salt_g + water_g) if salt_g else 0.0,
            source="typical_recipe",
            coverage=None,
            starter_fraction=profile.starter_fraction,
            starter_logged=False,
            warnings=warnings,
            notes=notes,
        )
    else:
        kg = total / 1000.0
        pools0 = {k: v / kg for k, v in pools.items()}
        if coverage < 0.8 and unmapped:
            warnings.append(
                f"Only {round(coverage * 100)} % of the recipe mass has USDA reference data "
                f"(no data: {', '.join(unmapped)}); starting sugars may be underestimated."
            )
        if unquantified:
            warnings.append(
                f"Not counted (no quantity or unit): {', '.join(unquantified)}."
            )
        init = _Initial(
            pools=pools0,
            protein_total=pools0.get("protein", 0.0),
            salt_wps=100.0 * salt / (salt + water) if salt and (salt + water) > 0 else 0.0,
            source="recipe",
            coverage=coverage,
            starter_fraction=(starter / total) if starter else profile.starter_fraction,
            starter_logged=starter > 0,
            warnings=warnings,
            notes=notes,
        )
        if init.salt_wps > 26.4:
            warnings.append(
                f"The logged salt ({init.salt_wps:.0f} % of the water) is above saturation: "
                "is some water or a cooked weight missing from the recipe?"
            )

    if init.starter_fraction and profile.starter_acids:
        for acid, conc in profile.starter_acids.items():
            init.pools[acid] = init.pools.get(acid, 0.0) + conc * init.starter_fraction
    return init


def _shift(prior: Prior, delta: float) -> Prior:
    if prior.scale == "lin":
        return Prior(prior.median + delta, prior.lo + delta, prior.hi + delta, "lin")
    k = 10.0**delta
    return Prior(prior.median * k, prior.lo * k, prior.hi * k, "log")


@dataclass
class _OrganismPlan:
    source: OrganismIn
    kin: OrganismKinetics | None
    can_grow: bool
    note: str | None


def _plan_organisms(inputs: PredictionInputs, profile: FermentProfile) -> list[_OrganismPlan]:
    plans = []
    for o in inputs.organisms:
        kin = ORGANISM_KINETICS.get(o.name)
        note = None
        can_grow = True
        if kin is None:
            note = "no kinetic profile yet: not modelled"
            can_grow = False
        elif kin.obligate_aerobe and not profile.aerobic:
            can_grow = False
            note = (
                "its enzymes (carried in by the koji) are modelled; the mold itself cannot "
                "grow in this closed, airless ferment"
                if kin.makes_enzymes
                else "needs air: cannot grow in this closed ferment"
            )
        plans.append(_OrganismPlan(o, kin, can_grow, note))
    return plans


def _schedule(
    inputs: PredictionInputs, profile: FermentProfile, override: float | None, horizon: float
) -> tuple[TemperatureSchedule, float, str, int, int]:
    readings = sorted(
        (max(m.t_h, 0.0), m.value)
        for m in inputs.measurements
        if m.type == "temperature" and m.value is not None and m.t_h <= inputs.now_h + 1.0
    )
    valid = [(t, v) for t, v in readings if TEMP_RANGE_C[0] <= v <= TEMP_RANGE_C[1]]
    ignored = len(readings) - len(valid)
    if override is not None:
        forecast, source, est_future = override, "override", 0.0
    elif inputs.expected_temperature_c is not None:
        forecast, source, est_future = inputs.expected_temperature_c, "expected", 1.0
    elif valid:
        forecast, source, est_future = valid[-1][1], "measured", 1.0
    else:
        forecast, source, est_future = profile.temp_c, "type_default", 1.0

    now = max(inputs.now_h, 0.0)
    past_estimate = (
        inputs.expected_temperature_c
        if inputs.expected_temperature_c is not None
        else profile.temp_c
    )
    # (hours, °C, estimated) knots; `estimated` spans get the ensemble's temperature offset.
    # Before the first reading the first reading is held (half-trusted); readings are exact.
    k: list[tuple[float, float, float]] = []
    if valid:
        k.append((0.0, valid[0][1], 0.5))
        k += [(t, v, 0.0) for t, v in valid]
        k.append((now, valid[-1][1], 0.0))
    else:
        k += [(0.0, past_estimate, 1.0), (now, past_estimate, 1.0)]
    k += [(now + 0.01, forecast, est_future), (max(horizon, now + 0.02), forecast, est_future)]
    # np.interp needs increasing knots: the last value wins at duplicate times
    knots = {round(t, 6): (v, e) for t, v, e in k}
    ts = sorted(knots)
    sched = TemperatureSchedule(ts, [knots[t][0] for t in ts], [knots[t][1] for t in ts])
    return sched, forecast, source, len(valid), ignored


@dataclass
class _ObsPlan:
    used: list[Observation]
    shown: list[dict[str, Any]]
    ignored_density: int


def _observations(
    inputs: PredictionInputs, profile: FermentProfile, horizon: float
) -> _ObsPlan:
    by_key: dict[str, list[tuple[float, float]]] = {}
    shown: list[dict[str, Any]] = []
    ignored_density = 0
    # An iSpindel set to °Plato reads e.g. 12 -> 0.8: decide the unit per stream, not per
    # reading, or the low end of a Plato stream would pass for specific gravity.
    plato = any(
        m.value is not None and m.value > 1.5
        for m in inputs.measurements
        if MEASUREMENT_KEYS.get(m.type.strip().lower()) == "gravity"
    )
    for m in inputs.measurements:
        key = MEASUREMENT_KEYS.get(m.type.strip().lower())
        if key is None or m.value is None or m.t_h < -1.0:
            continue
        v = m.value
        t = max(m.t_h, 0.0)
        if key == "gravity" and plato:
            v = plato_to_sg(v)
        valid = {
            "ph": 1.5 <= v <= 9.0,
            "gravity": 0.95 <= v <= 1.2,
            "brix": 0.0 <= v <= 60.0,
        }[key]
        usable = valid and t <= horizon and (key == "ph" or profile.show_density)
        if key != "ph" and not profile.show_density:
            ignored_density += 1
        if usable:
            by_key.setdefault(key, []).append((t, v))
        else:
            shown.append({"key": key, "t_h": round(t, 3), "value": v, "used": False})

    used: list[Observation] = []
    for key, pts in by_key.items():
        pts.sort()
        if len(pts) > MAX_OBS_PER_KEY:
            span = pts[-1][0] - pts[0][0]
            width = max(6.0, span / MAX_OBS_PER_KEY)
            bins: dict[int, list[tuple[float, float]]] = {}
            for t, v in pts:
                bins.setdefault(int((t - pts[0][0]) // width), []).append((t, v))
            pts = [
                (sum(t for t, _ in b) / len(b), sum(v for _, v in b) / len(b))
                for b in bins.values()
            ]
        for t, v in pts:
            t = round(t, 3)
            used.append(Observation(key, t, v))
            shown.append({"key": key, "t_h": t, "value": round(v, 4), "used": True})
    shown.sort(key=lambda o: (o["key"], o["t_h"]))
    return _ObsPlan(used, shown, ignored_density)


def _spec(
    profile: FermentProfile,
    plans: list[_OrganismPlan],
    init: _Initial,
    schedule: TemperatureSchedule,
) -> tuple[ModelSpec, list[_OrganismPlan]]:
    modelled = [p for p in plans if p.kin is not None]
    inoculum = []
    shift = 0.0
    if init.starter_logged and profile.starter_fraction and init.starter_fraction:
        shift = max(-1.5, min(1.0, math.log10(init.starter_fraction / profile.starter_fraction)))
    for p in modelled:
        assert p.kin is not None
        base = profile.inoculum.get(p.kin.name)
        if base is None:
            base = ADDED_MOLD_INOCULUM if p.kin.is_mold else ADDED_ORGANISM_INOCULUM
        elif shift and not p.kin.is_mold:
            base = _shift(base, shift)
        inoculum.append(base)
    spec = ModelSpec(
        profile=profile,
        organisms=[p.kin for p in modelled if p.kin is not None],
        can_grow=[p.can_grow for p in modelled],
        inoculum=inoculum,
        pools0=init.pools,
        salt_water_phase_pct=init.salt_wps,
        schedule=schedule,
    )
    return spec, modelled


@dataclass(frozen=True)
class _PosteriorLite:
    z: FloatArray
    weights: FloatArray
    tempered: float


def _resample(z: FloatArray, weights: FloatArray, k: int, seed: int) -> FloatArray:
    """Systematic resampling of posterior z-vectors (duplicates are fine)."""
    rng = np.random.default_rng(seed)
    cw = np.cumsum(weights)
    cw[-1] = 1.0
    u = (rng.random() + np.arange(k)) / k
    return np.asarray(z[np.searchsorted(cw, u)])


# ── series, milestones ──────────────────────────────────────────────────


def _series_values(
    tr: Trajectories,
    spec: ModelSpec,
    z: FloatArray,
    want_density: bool,
) -> dict[str, FloatArray]:
    out: dict[str, FloatArray] = {}
    if spec.profile.show_ph:
        out["ph"] = tr.ph
    for k in ("sucrose", "hexoses", "lactose", "maltose", "starch", "protein", *PRODUCTS):
        out[k] = tr.pools[:, :, PI[k]]
    out["sugars_total"] = np.asarray(sum(tr.pools[:, :, PI[k]] for k in SUGAR_KEYS))
    if want_density:
        out["gravity"], out["brix"] = density_series(tr.pools, solids_offset(z))
    params = spec.params(z[:, : spec.dim])
    for j, o in enumerate(spec.organisms):
        if not spec.can_grow[j]:
            continue
        x = tr.biomass_g[:, :, j]
        if o.is_mold:
            out["mycelium"] = np.asarray(100.0 * x / params.organisms[j].x_max_g[:, None])
        else:
            assert o.cell_mass_g is not None
            out[f"pop:{o.name}"] = np.asarray(
                np.maximum(np.log10(np.maximum(x, 1e-30) / o.cell_mass_g / 1000.0), 0.0)
            )
    if any(o.makes_enzymes for o in spec.organisms):
        out["koji_enzyme"] = np.asarray(100.0 * tr.pools[:, :, PI["koji_enzyme"]])
    return out


def _relevant(key: str, q: FloatArray, init: FloatArray) -> bool:
    if key in ("ph", "gravity", "brix", "mycelium", "koji_enzyme") or key.startswith("pop:"):
        return True
    if key in SUBSTRATES:
        return float(np.max(q[2])) >= 0.3
    return float(np.max(q[2])) >= 0.3 and float(np.max(q[2]) - np.min(init)) >= 0.2


def _first_crossing(t: FloatArray, v: FloatArray, target: FloatArray, below: bool) -> FloatArray:
    """(K,) first time each member's series crosses `target` (inf if never)."""
    hit = v <= target[:, None] if below else v >= target[:, None]
    any_hit = hit.any(axis=1)
    i = np.argmax(hit, axis=1)
    out = np.full(v.shape[0], np.inf)
    for m in np.nonzero(any_hit)[0]:
        k = int(i[m])
        if k == 0:
            out[m] = t[0]
            continue
        v0, v1 = v[m, k - 1], v[m, k]
        frac = 0.0 if v1 == v0 else float((target[m] - v0) / (v1 - v0))
        out[m] = t[k - 1] + min(max(frac, 0.0), 1.0) * (t[k] - t[k - 1])
    return out


def _milestone(
    ms: Milestone, t: FloatArray, values: dict[str, FloatArray], w: FloatArray
) -> dict[str, Any] | None:
    v = values.get(ms.series)
    if v is None:
        return None
    n = v.shape[0]
    if ms.kind == "below":
        times = _first_crossing(t, v, np.full(n, ms.threshold), below=True)
    elif ms.kind == "above":
        times = _first_crossing(t, v, np.full(n, ms.threshold), below=False)
    elif ms.kind == "consumed_fraction":
        start = v[:, 0]
        if float(np.max(start)) <= 0.1:
            return None
        times = _first_crossing(t, v, (1.0 - ms.threshold) * start, below=True)
    else:
        ref = values.get(ms.ref or "")
        if ref is None or float(np.max(ref[:, 0])) <= 0.1:
            return None
        times = _first_crossing(t, v, ms.threshold * ref[:, 0], below=False)
    reached = np.isfinite(times)
    q = weighted_quantiles(times, w, (0.05, 0.5, 0.95))

    def fmt(x: float) -> float | None:
        return None if not math.isfinite(x) else round(x, 2)

    return {
        "key": ms.key,
        "label": f"{ms.title} ({ms.note})",
        "title": ms.title,
        "note": ms.note,
        "threshold": {"series": ms.series, "value": ms.threshold, "kind": ms.kind},
        "t_h": {"p05": fmt(float(q[0])), "p50": fmt(float(q[1])), "p95": fmt(float(q[2]))},
        "probability": round(float(np.sum(w[reached])), 3),
    }


def _channel_label(ch: Channel) -> str:
    names = {"hexoses": "glucose/fructose", "co2": "CO₂", "lactic_acid": "lactic acid",
             "acetic_acid": "acetic acid", "gluconic_acid": "gluconic acid"}  # fmt: skip
    subs = ", ".join(names.get(s, s) for s in ch.substrates)
    prods = " + ".join(names.get(p, p) for p in ch.products)
    return f"{subs} → {prods}"


def _channel_ecs(ch: Channel) -> tuple[str, ...]:
    if "lactic_acid" in ch.products:
        return _LDH
    if "acetic_acid" in ch.products and "ethanol" in ch.substrates:
        return _AAB
    if "gluconic_acid" in ch.products:
        return _GLUCONATE
    if "ethanol" in ch.products:
        return _ALCOHOLIC
    if "starch" in ch.substrates:
        return _AMYLASES
    return ()


def _organism_out(plan: _OrganismPlan, series_keys: set[str]) -> dict[str, Any]:
    kin = plan.kin
    pathways = []
    if kin is not None:
        known = set(plan.source.ec_numbers)
        for ch in kin.channels:
            ecs = _channel_ecs(ch)
            pathways.append(
                {
                    "label": _channel_label(ch),
                    "ec_numbers": list(ecs),
                    "in_reference_graph": bool(known & set(ecs)),
                }
            )
        if kin.inverts_sucrose is not None:
            pathways.append(
                {"label": "sucrose → glucose + fructose (invertase)", "ec_numbers": ["3.2.1.26"],
                 "in_reference_graph": "3.2.1.26" in known}  # fmt: skip
            )
    key = None
    if kin is not None and plan.can_grow:
        key = "mycelium" if kin.is_mold else f"pop:{kin.name}"
    return {
        "name": plan.source.name,
        "kingdom": plan.source.kingdom,
        "modelled": kin is not None,
        "growing": kin is not None and plan.can_grow,
        "role": kin.role if kin else "no kinetic profile yet",
        "note": plan.note,
        "series_key": key if key in series_keys else None,
        "pathways": pathways,
        "sources": list(kin.sources) if kin else [],
    }


def _group(key: str) -> tuple[str, str]:
    if key == "ph":
        return "ph", ""
    if key in SUBSTRATES:
        return "substrates", "g/kg"
    if key in PRODUCTS:
        return "products", "g/kg"
    if key == "gravity":
        return "density", "SG"
    if key == "brix":
        return "density", "°Bx"
    if key in ("mycelium", "koji_enzyme"):
        return "growth", "%"
    return "population", "log CFU/g"


def _round(a: FloatArray, key: str) -> list[float]:
    digits = 4 if key == "gravity" else 3
    return [round(float(x), digits) for x in a]


# ── entry point ─────────────────────────────────────────────────────────

_CACHE: OrderedDict[str, Any] = OrderedDict()
_CACHE_SIZE = 64
_LOCK = threading.Lock()


def _cached(key: str) -> Any:
    with _LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    return None


def _store(key: str, value: Any) -> None:
    with _LOCK:
        _CACHE[key] = value
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_SIZE:
            _CACHE.popitem(last=False)


def default_horizon(profile: FermentProfile, now_h: float) -> float:
    h = profile.horizon_h
    if now_h > 0.85 * h:  # an older batch: keep "now" inside the window
        h = now_h * 1.15
    return min(h, MAX_HORIZON_H)


def predict(
    inputs: PredictionInputs,
    temperature_c: float | None = None,
    horizon_h: float | None = None,
) -> dict[str, Any]:
    """Forecast for one batch. Deterministic for identical inputs (seeded), cached."""
    profile = profile_for(inputs.fermentation_type)
    horizon = min(horizon_h, MAX_HORIZON_H) if horizon_h else default_horizon(profile, inputs.now_h)
    fp = inputs.fingerprint()
    out_key = f"{fp}|{temperature_c}|{horizon}"
    hit = _cached(out_key)
    if hit is not None:
        return dict(hit)

    init = _initial_state(profile, inputs.recipe)
    plans = _plan_organisms(inputs, profile)
    obs = _observations(inputs, profile, horizon)
    obs_t = [o.t_h for o in obs.used]
    t_eval = np.unique(
        np.concatenate([np.linspace(0.0, horizon, GRID_POINTS), np.asarray(obs_t, dtype=float)])
    )
    grid_idx = np.searchsorted(t_eval, np.linspace(0.0, horizon, GRID_POINTS))

    base_sched, forecast_c, t_source, n_temp, temp_ignored = _schedule(
        inputs, profile, None, horizon
    )
    spec, modelled = _spec(profile, plans, init, base_sched)

    # Only z-vectors and weights are cached (a few hundred KB); trajectories are ~10 MB.
    post_key = f"{fp}|post|{horizon}"
    lite: _PosteriorLite | None = _cached(post_key)
    tempered = 1.0
    if temperature_c is None or lite is None:
        post = run_inference(spec, obs.used, t_eval, n=N_MEMBERS, seed=int(fp[:8], 16) % 2**31)
        lite = _PosteriorLite(post.z, post.weights, post.tempered)
        _store(post_key, lite)
        z, weights, tr = post.z, post.weights, post.traj
    tempered = lite.tempered

    if temperature_c is not None:
        what_sched, forecast_c, t_source, _, _ = _schedule(inputs, profile, temperature_c, horizon)
        spec, _ = _spec(profile, plans, init, what_sched)
        z = _resample(lite.z, lite.weights, N_WHATIF, seed=int(fp[8:16], 16) % 2**31)
        tr = simulate(spec.params(z[:, : spec.dim]), t_eval)
        weights = np.full(N_WHATIF, 1.0 / N_WHATIF)
    members = len(weights)

    want_density = profile.show_density
    values = _series_values(tr, spec, z, want_density)
    t_grid = t_eval[grid_idx]
    series: list[dict[str, Any]] = []
    for key, v in values.items():
        vg = v[:, grid_idx]
        q = weighted_quantiles(vg, weights, (0.05, 0.5, 0.95))
        if not _relevant(key, q, vg[:, 0]):
            continue
        group, unit = _group(key)
        label = LABELS.get(key) or key.removeprefix("pop:")
        series.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "group": group,
                "t_h": [round(float(x), 3) for x in t_grid],
                "p05": _round(q[0], key),
                "p50": _round(q[1], key),
                "p95": _round(q[2], key),
            }
        )
    order = [*SUBSTRATES, *PRODUCTS]
    series.sort(
        key=lambda s: (
            ["ph", "density", "substrates", "products", "growth", "population"].index(s["group"]),
            order.index(s["key"]) if s["key"] in order else 0,
        )
    )
    # one sugar pool is just "sugars (total)" twice; protein is flat without proteolysis
    keys = {s["key"] for s in series}
    drop = set(SUGAR_KEYS) if len(keys & set(SUGAR_KEYS)) <= 1 else set()
    if "amino_acids" not in keys:
        drop.add("protein")
    series = [s for s in series if s["key"] not in drop]
    series_keys = {s["key"] for s in series}

    milestones = [
        m
        for ms in profile.milestones
        if (m := _milestone(ms, t_eval, values, weights)) is not None
    ]

    ph0 = weighted_quantiles(tr.ph[:, 0], weights, (0.5,))[0]
    initial_values = {
        "sugars_total": round(sum(init.pools.get(k, 0.0) for k in SUGAR_KEYS), 2),
        "starch": round(init.pools.get("starch", 0.0), 2),
        "protein": round(init.protein_total, 2),
        "ethanol": round(init.pools.get("ethanol", 0.0), 2),
        "salt_water_phase_pct": round(init.salt_wps, 2),
        "ph": round(float(ph0), 2),
    }
    for acid in ("lactic_acid", "acetic_acid", "gluconic_acid"):
        if init.pools.get(acid):
            initial_values[acid] = round(init.pools[acid], 2)

    warnings = list(init.warnings)
    not_modelled = [p.source.name for p in plans if p.kin is None]
    if not modelled:
        warnings.append(
            "None of this batch's organisms has a kinetic profile, so nothing grows in the "
            "model: the curves only show the starting state."
        )
    elif not_modelled:
        warnings.append(f"Not modelled (no kinetic profile yet): {', '.join(not_modelled)}.")
    if temp_ignored:
        warnings.append(
            f"{temp_ignored} temperature reading(s) outside -5 to 60 °C were ignored "
            "(logged in °F?)."
        )
    if obs.ignored_density:
        warnings.append(
            "Gravity/Brix readings are not used for this ferment type (solids and fat "
            "dominate them); pH readings are."
        )
    if tempered < 1.0:
        warnings.append(
            "Your readings sit outside what the model's plausible parameter range explains, "
            "so their influence was reduced and the bands widened. Check the readings, or "
            "treat this forecast as rough."
        )
    if profile.confidence == "exploratory":
        warnings.append(
            f"Exploratory: {profile.type} is driven by enzymes and salt-tolerant microbes with "
            "little published kinetic data. Read the curves as a sketch of the mechanism, "
            "not a calibrated forecast."
        )
    if inputs.finished:
        warnings.append("This batch is marked finished; the forecast runs as if it continued.")

    n_used = len(obs.used)
    counts: dict[str, int] = {}
    for o in obs.used:
        counts[o.key] = counts.get(o.key, 0) + 1
    assumptions = []
    if init.source == "recipe":
        assumptions.append(
            "Starting sugars, starch, protein and salt from your recipe × USDA FoodData "
            f"Central ({round((init.coverage or 0) * 100)} % of the mass has reference data)."
        )
    temp_text = {
        "override": f"what-if: {forecast_c:g} °C from now on (not saved)",
        "expected": f"your estimate of {forecast_c:g} °C from now on",
        "measured": f"{forecast_c:g} °C from now on (your last reading; no estimate set)",
        "type_default": f"{forecast_c:g} °C from now on (typical for {profile.type}; set an "
        "estimate for a better forecast)",
    }[t_source]
    if n_temp:
        temp_text += f"; your {n_temp} logged temperature reading(s) for the past"
    assumptions.append(f"Temperature: {temp_text}.")
    who = "set for this batch" if inputs.organism_source == "custom" else "reference defaults"
    assumptions.append(
        f"Organisms: {profile.type} {who} ({', '.join(p.source.name for p in plans) or 'none'})."
    )
    if profile.starter_fraction:
        if init.starter_logged:
            assumptions.append(
                f"Starter: {round((init.starter_fraction or 0) * 100, 1)} % of the batch "
                "(logged); its acids and microbes are carried over."
            )
        else:
            assumptions.append(
                f"Starter: none logged, so a typical {round(profile.starter_fraction * 100)} % "
                "starter was assumed (its acids and microbes are carried over)."
            )
    if init.salt_wps:
        assumptions.append(
            f"Salt: {init.salt_wps:.1f} % in the water phase (drives water activity)."
        )
    assumptions += init.notes
    assumptions += list(profile.notes)
    if n_used:
        detail = ", ".join(f"{v} {k if k != 'ph' else 'pH'}" for k, v in counts.items())
        assumptions.append(
            f"Calibrated on {n_used} of your readings ({detail}); pH readings are assumed "
            f"accurate to about ±{OBS_SIGMA['ph'][0]}."
        )

    sources = sorted(
        set(profile.sources) | {s for p in modelled if p.kin for s in p.kin.sources}
    )
    reference_lines = (
        [{"series": "ph", "value": 4.6, "label": "4.6 food-safety reference"}]
        if profile.ph_safety_line and profile.show_ph
        else []
    )
    base_h = profile.horizon_h
    options = sorted(
        {round(min(base_h * f, MAX_HORIZON_H), 1) for f in (0.25, 0.5, 1.0, 2.0)} | {horizon}
    )
    result = {
        "model": {
            "name": "FermentTrack kinetic ensemble",
            "version": MODEL_VERSION,
            "method": METHOD,
            "members": int(members),
            "effective_members": round(
                float(1.0 / np.sum(weights**2)), 1
            ),
            "confidence": profile.confidence,
            "validated": False,
            "sources": sources,
        },
        "fermentation_type": inputs.fermentation_type,
        "now_h": round(inputs.now_h, 3),
        "horizon_h": horizon,
        "horizon_options_h": options,
        "temperature": {
            "forecast_c": forecast_c,
            "source": t_source,
            "type_default_c": profile.temp_c,
            "range_c": list(profile.temp_range),
            "readings": n_temp,
        },
        "status": "calibrated" if n_used else "prior_only",
        "series": series,
        "observations": obs.shown,
        "milestones": milestones,
        "reference_lines": reference_lines,
        "organisms": [_organism_out(p, series_keys) for p in plans],
        "initial": {"source": init.source, "values": initial_values},
        "assumptions": assumptions,
        "warnings": warnings,
        "disclaimer": DISCLAIMER,
    }
    _store(out_key, result)
    return dict(result)
