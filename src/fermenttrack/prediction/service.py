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
from fermenttrack.prediction.engine import PI, SimulationError, Trajectories, simulate
from fermenttrack.prediction.inference import (
    MIN_ESS,
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
N_FALLBACK = 64  # retry size when the full ensemble exceeds its solver budget
N_RESAMPLE = 128  # posterior members re-simulated for a what-if or another window
GRID_POINTS = 161
MAX_HORIZON_H = 3 * 8760.0  # multi-year miso and garum
MAX_OBS_PER_KEY = 30  # denser streams (iSpindel) are binned: correlated errors
MAX_MODELLED_ORGANISMS = 6  # each adds states and stiffness; defaults are kept first
TEMP_RANGE_C = (-5.0, 60.0)
READING_HOLD_H = 12.0  # a temperature reading stands for this long, then the estimate
MISFIT_SIGMAS = 3.0

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
    "soluble_protein": "Soluble protein (peptides + free amino acids)",
    "amino_acids": "Amino acids (free)",
    "ethanol": "Ethanol",
    "lactic_acid": "Lactic acid",
    "acetic_acid": "Acetic acid",
    "gluconic_acid": "Gluconic acid",
    "co2": "CO₂ (cumulative)",
    "gravity": "Specific gravity",
    "brix": "Brix (refractometer)",
    "mycelium": "Mycelium growth",
    "amylase": "Amylase activity",
    "protease": "Protease activity",
    "peptidase": "Peptidase activity",
    "fish_enzyme": "Fish enzyme activity",
}
SUBSTRATES = ("sugars_total", "sucrose", "hexoses", "lactose", "maltose", "starch", "protein")
PRODUCTS = (
    "lactic_acid", "acetic_acid", "gluconic_acid", "ethanol", "co2", "soluble_protein",
    "amino_acids",
)  # fmt: skip
# Enzyme activity series, % of a fully grown koji (fish: of fresh whole fish).
ENZYMES = ("amylase", "protease", "peptidase", "fish_enzyme")
SUGAR_KEYS = ("sucrose", "hexoses", "lactose", "maltose")
MEASUREMENT_KEYS = {"ph": "ph", "gravity": "gravity", "brix": "brix", "sg": "gravity"}


class PredictionUnavailable(RuntimeError):
    """No forecast could be computed within budget for this batch."""

# Marker enzymes per pathway, to check against the batch's KEGG reference graph
# (biochemistry v4 added invertase, phosphoketolase, PQQ glucose dehydrogenase, maltose
# phosphorylase and 6-phospho-beta-galactosidase for exactly this).
_LDH = ("1.1.1.27", "1.1.1.28")
_PHOSPHOKETOLASE = ("4.1.2.9",)  # the defining step of heterolactic fermentation
_ALCOHOLIC = ("4.1.1.1", "1.1.1.1")
_AAB = ("1.1.5.5", "1.2.5.2", "1.2.1.3")
_GLUCONATE = ("1.1.5.2",)
_AMYLASES = ("3.2.1.1", "3.2.1.3", "3.2.1.20")
# How a disaccharide enters metabolism: (label, enzymes, any of which backs it)
_ENTRY_STEPS = {
    "sucrose": ("sucrose → glucose + fructose (invertase)", ("3.2.1.26",)),
    "maltose": ("maltose → glucose (maltose phosphorylase / maltase)",
                ("2.4.1.8", "3.2.1.20", "3.2.1.10")),
    "lactose": ("lactose → glucose + galactose (beta-galactosidase, or 6-phospho- via PTS)",
                ("3.2.1.23", "3.2.1.85")),
}  # fmt: skip


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
    now_h: float  # hours since the batch started
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
        if grams is None or not math.isfinite(grams) or grams <= 0:
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
        if starch is None and "carbohydrate" in n and "starch" in profile.typical_recipe:
            # SR Legacy often omits starch for grains/flours: carbohydrate by difference
            # minus fiber and sugars is mostly starch there. Not elsewhere (wine: glycerol
            # and extract; soybeans: non-starch polysaccharides), hence the two guards.
            est = n["carbohydrate"] - n.get("fiber", 0.0) - n.get("sugars_total", 0.0)
            if est >= 20.0:
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
    if profile.fish_enzyme0 is not None or profile.koji_enzyme0 is not None:
        fermentable += pools.get("protein", 0.0)  # proteolysis ferments (garum: fish + salt)
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
    # the type's own organisms first, so a cap drops added extras, not the defaults
    ordered = sorted(inputs.organisms, key=lambda o: (o.name not in profile.inoculum, o.name))
    plans = []
    modelled = 0
    for o in ordered:
        kin = ORGANISM_KINETICS.get(o.name)
        note = None
        can_grow = True
        if kin is not None and modelled >= MAX_MODELLED_ORGANISMS:
            kin = None
            note = f"not modelled: a forecast models at most {MAX_MODELLED_ORGANISMS} organisms"
            can_grow = False
        elif kin is None:
            note = "no kinetic profile yet: not modelled"
            can_grow = False
        else:
            modelled += 1
            if kin.obligate_aerobe and not profile.aerobic:
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
    inputs: PredictionInputs, profile: FermentProfile, override: float | None, end_h: float
) -> tuple[TemperatureSchedule, float, str, int, int]:
    readings = sorted(
        (max(m.t_h, 0.0), m.value)
        for m in inputs.measurements
        if m.type == "temperature"
        and m.value is not None
        and math.isfinite(m.value)
        and m.t_h <= inputs.now_h + 1.0
    )
    valid = [(t, v) for t, v in readings if TEMP_RANGE_C[0] <= v <= TEMP_RANGE_C[1]]
    ignored = len(readings) - len(valid)
    now = max(inputs.now_h, 0.0)
    if inputs.expected_temperature_c is not None:
        estimate = inputs.expected_temperature_c
    elif valid:
        estimate = float(np.mean([v for _, v in valid]))
    else:
        estimate = profile.temp_c
    if override is not None:
        forecast, source, est_future = override, "override", 0.0
    elif inputs.expected_temperature_c is not None:
        forecast, source, est_future = inputs.expected_temperature_c, "expected", 1.0
    elif valid:
        # the last day's readings, not one noisy point, stand for the future
        recent = [v for t, v in valid if t >= valid[-1][0] - 24.0]
        forecast, source, est_future = float(np.median(recent)), "measured", 1.0
    else:
        forecast, source, est_future = profile.temp_c, "type_default", 1.0
    forecast = round(forecast, 1)

    # (hours, °C, estimated) knots; `estimated` spans get the ensemble's temperature offset.
    # A reading is exact at its time and stands for READING_HOLD_H; longer gaps go back to
    # the estimate (one warm reading on day 0 must not set the next three weeks).
    hold = READING_HOLD_H
    k: list[tuple[float, float, float]] = []
    if not valid:
        k += [(0.0, estimate, 1.0), (now, estimate, 1.0)]
    else:
        t0, v0 = valid[0]
        k += [(0.0, estimate, 1.0), (t0 - hold, estimate, 1.0)] if t0 > hold else [(0.0, v0, 0.5)]
        for i, (t, v) in enumerate(valid):
            k.append((t, v, 0.0))
            t_next = valid[i + 1][0] if i + 1 < len(valid) else now
            if t_next - t > 2 * hold:
                k += [(t + hold, estimate, 1.0), (t_next - hold, estimate, 1.0)]
        t_last, v_last = valid[-1]
        k.append((now, v_last if now - t_last <= 2 * hold else estimate, 0.0))
    k += [(now + 0.01, forecast, est_future), (max(end_h, now + 0.02), forecast, est_future)]
    # np.interp needs increasing knots: the last value wins at duplicate times
    knots = {round(max(t, 0.0), 6): (v, e) for t, v, e in k}
    ts = sorted(knots)
    sched = TemperatureSchedule(ts, [knots[t][0] for t in ts], [knots[t][1] for t in ts])
    return sched, forecast, source, len(valid), ignored


@dataclass
class _ObsPlan:
    used: list[Observation]
    shown: list[dict[str, Any]]
    ignored_density: int


def _observations(inputs: PredictionInputs, profile: FermentProfile) -> _ObsPlan:
    by_key: dict[str, list[tuple[float, float]]] = {}
    shown: list[dict[str, Any]] = []
    ignored_density = 0
    # An iSpindel set to °Plato reads e.g. 12 -> 0.8: decide the unit per stream, not per
    # reading, or the low end of a Plato stream would pass for specific gravity.
    finite = [m for m in inputs.measurements if m.value is not None and math.isfinite(m.value)]
    plato = any(
        m.value is not None and 1.5 < m.value < 40.0
        for m in finite
        if MEASUREMENT_KEYS.get(m.type.strip().lower()) == "gravity"
    )
    for m in finite:
        key = MEASUREMENT_KEYS.get(m.type.strip().lower())
        if key is None or m.value is None or m.t_h < -1.0 or m.t_h > inputs.now_h + 1.0:
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
        modelled = profile.show_ph if key == "ph" else profile.show_density
        usable = valid and modelled
        if key != "ph" and not profile.show_density:
            ignored_density += 1
        if usable:
            by_key.setdefault(key, []).append((t, v))
        else:
            shown.append(
                {"key": key, "t_h": round(t, 3), "value": v, "used": False, "fits": None}
            )

    used: list[Observation] = []
    for key, pts in by_key.items():
        pts.sort()
        if len(pts) > MAX_OBS_PER_KEY:
            span = pts[-1][0] - pts[0][0]
            width = max(6.0, span / (MAX_OBS_PER_KEY - 1))  # at most MAX_OBS_PER_KEY bins
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
            shown.append({"key": key, "t_h": t, "value": round(v, 4), "used": True, "fits": True})
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
    ess: float


def _check_fit(
    obs: _ObsPlan, tr: Trajectories, z: FloatArray, w: FloatArray, t_eval: FloatArray
) -> list[str]:
    """Flag readings the (weighted) ensemble cannot explain: more than MISFIT_SIGMAS
    predictive standard deviations (ensemble spread + reading error) from the median.
    Marks `fits` on the shown observations; returns short labels of the misfits."""
    if not obs.used:
        return []
    idx = {float(t): i for i, t in enumerate(t_eval)}
    sg = brix = None
    if any(o.key != "ph" for o in obs.used):
        sg, brix = density_series(tr.pools, solids_offset(z))
    bad: set[tuple[str, float]] = set()
    labels = []
    for o in obs.used:
        i = idx[o.t_h]
        pred = {"ph": tr.ph, "gravity": sg, "brix": brix}[o.key]
        assert pred is not None
        p = pred[:, i]
        med = float(weighted_quantiles(p, w, (0.5,))[0])
        spread = float(np.sqrt(np.sum(w * (p - np.sum(w * p)) ** 2)))
        s_meas, s_model = OBS_SIGMA[o.key]
        if abs(o.value - med) > MISFIT_SIGMAS * math.sqrt(spread**2 + s_meas**2 + s_model**2):
            bad.add((o.key, o.t_h))
            name = "pH" if o.key == "ph" else o.key
            when = (
                f"{o.t_h:.1f}".removesuffix(".0") + " h" if o.t_h < 48 else f"day {o.t_h / 24:.1f}"
            )
            labels.append(f"{name} {o.value:g} at {when}")
    for shown in obs.shown:
        if shown["used"]:
            shown["fits"] = (shown["key"], shown["t_h"]) not in bad
    return labels


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
        if k in PI:
            out[k] = tr.pools[:, :, PI[k]]
    out["soluble_protein"] = np.asarray(
        tr.pools[:, :, PI["peptides"]] + tr.pools[:, :, PI["amino_acids"]]
    )
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
    for c in spec.enzyme_classes:
        act = tr.pools[:, :, PI[c.key]]
        if c.key == "protease":
            act = act + tr.pools[:, :, PI["protease_ts"]]
        out[c.key] = np.asarray(100.0 * act)
    return out


def _relevant(key: str, q: FloatArray) -> bool:
    if key in ("ph", "gravity", "brix", "mycelium") or key.startswith("pop:"):
        return True
    if key in ENZYMES:  # koji added to a ferment with no koji enzymes stays at zero
        return float(np.max(q[2])) >= 0.5
    if key in SUBSTRATES:
        return float(np.max(q[2])) >= 0.3
    # products: present, and changing (rising acids, or ethanol consumed in vinegar)
    return float(np.max(q[2])) >= 0.3 and float(np.ptp(q[1])) >= 0.2


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
    if "lactic_acid" in ch.products and "ethanol" in ch.products:
        return _PHOSPHOKETOLASE
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
        entry = {s for ch in kin.channels for s in ch.substrates} & set(_ENTRY_STEPS)
        if kin.inverts_sucrose is not None:
            entry.add("sucrose")
        for sugar in sorted(entry):
            label, ecs = _ENTRY_STEPS[sugar]
            backed = bool(known & set(ecs))
            pathways.append({"label": label, "ec_numbers": list(ecs), "in_reference_graph": backed})
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
    if key == "mycelium" or key in ENZYMES:
        return "growth", "%"
    return "population", "log CFU/g"


def _round(a: FloatArray, key: str) -> list[float]:
    digits = 4 if key == "gravity" else 3
    return [round(float(x), digits) for x in a]


# ── entry point ─────────────────────────────────────────────────────────

class _LRU:
    """Tiny thread-safe LRU for forecast outputs and posteriors."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.data: OrderedDict[str, Any] = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self.lock:
            if key not in self.data:
                return None
            self.data.move_to_end(key)
            return self.data[key]

    def put(self, key: str, value: Any) -> None:
        with self.lock:
            self.data[key] = value
            self.data.move_to_end(key)
            while len(self.data) > self.size:
                self.data.popitem(last=False)

    def clear(self) -> None:
        with self.lock:
            self.data.clear()


# Outputs are ~0.3-0.6 MB, posteriors (z-vectors + weights) up to ~1.3 MB.
_OUTPUTS = _LRU(32)
_POSTERIORS = _LRU(16)
# One solve at a time: a small instance has one core, and concurrent solves would only
# multiply memory. A request waiting here for an identical one then hits the cache.
_SOLVE_LOCK = threading.Lock()


def clear_caches() -> None:
    _OUTPUTS.clear()
    _POSTERIORS.clear()


def _nice_horizon(h: float) -> float:
    """Window choices in whole days past two days, whole hours below."""
    h = min(h, MAX_HORIZON_H)
    return float(max(round(h / 24.0), 1) * 24 if h >= 48 else max(round(h), 1))


def default_horizon(profile: FermentProfile, now_h: float) -> float:
    h = profile.horizon_h
    if now_h > 0.85 * h:  # an older batch: keep "now" inside the window
        h = round(now_h) * 1.15  # from the hour, so the cache key is stable within it
    return _nice_horizon(h)


def predict(
    inputs: PredictionInputs,
    temperature_c: float | None = None,
    horizon_h: float | None = None,
) -> dict[str, Any]:
    """Forecast for one batch. Deterministic for identical inputs (seeded), cached.

    Raises PredictionUnavailable when even the fallback ensemble exceeds its solver budget.
    """
    profile = profile_for(inputs.fermentation_type)
    horizon = _nice_horizon(horizon_h) if horizon_h else default_horizon(profile, inputs.now_h)
    fp = inputs.fingerprint()
    out_key = f"{fp}|{temperature_c}|{horizon}"
    hit = _OUTPUTS.get(out_key)
    if hit is None:
        with _SOLVE_LOCK:
            hit = _OUTPUTS.get(out_key)
            if hit is None:
                hit = _forecast(inputs, profile, fp, temperature_c, horizon)
                _OUTPUTS.put(out_key, hit)
    return dict(hit)


def _forecast(
    inputs: PredictionInputs,
    profile: FermentProfile,
    fp: str,
    temperature_c: float | None,
    horizon: float,
) -> dict[str, Any]:
    init = _initial_state(profile, inputs.recipe)
    plans = _plan_organisms(inputs, profile)
    obs = _observations(inputs, profile)
    # Every reading calibrates, even past a short display window: simulate to the later of
    # the window and the last reading, then show only the window.
    obs_t = np.asarray([o.t_h for o in obs.used], dtype=float)
    grid = np.linspace(0.0, horizon, GRID_POINTS)
    t_eval = np.unique(np.concatenate([grid, obs_t]))
    grid_idx = np.searchsorted(t_eval, grid)
    in_window = int(np.searchsorted(t_eval, horizon, side="right"))
    end_h = float(t_eval[-1])

    base_sched, forecast_c, t_source, n_temp, temp_ignored = _schedule(
        inputs, profile, None, end_h
    )
    spec, modelled = _spec(profile, plans, init, base_sched)
    seed = int(fp[:8], 16) % 2**31

    # The posterior depends on the inputs, not on the display window or a what-if, so it
    # is cached per fingerprint; other windows and what-ifs re-simulate a resample of it.
    lite: _PosteriorLite | None = _POSTERIORS.get(fp)
    tr: Trajectories | None = None
    if lite is None:
        for n in (N_MEMBERS, N_FALLBACK):
            try:
                post = run_inference(spec, obs.used, t_eval, n=n, seed=seed)
                break
            except SimulationError:
                continue
        else:
            raise PredictionUnavailable(
                "The model could not be computed for this batch within its budget."
            )
        lite = _PosteriorLite(post.z, post.weights, post.tempered, post.ess)
        _POSTERIORS.put(fp, lite)
        if temperature_c is None:
            z, weights, tr = post.z, post.weights, post.traj

    if tr is None:
        if temperature_c is not None:
            what_sched, forecast_c, t_source, _, _ = _schedule(
                inputs, profile, temperature_c, end_h
            )
            spec, _ = _spec(profile, plans, init, what_sched)
        z = _resample(lite.z, lite.weights, N_RESAMPLE, seed=int(fp[8:16], 16) % 2**31)
        try:
            tr = simulate(spec.params(z[:, : spec.dim]), t_eval)
        except SimulationError as exc:
            raise PredictionUnavailable(str(exc)) from exc
        weights = np.full(len(z), 1.0 / len(z))
    tempered = lite.tempered
    members = len(weights)

    want_density = profile.show_density
    values = _series_values(tr, spec, z, want_density)
    t_grid = t_eval[grid_idx]
    series: list[dict[str, Any]] = []
    for key, v in values.items():
        vg = v[:, grid_idx]
        q = weighted_quantiles(vg, weights, (0.05, 0.5, 0.95))
        if not _relevant(key, q):
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
    order = [*SUBSTRATES, *PRODUCTS, "mycelium", *ENZYMES]
    series.sort(
        key=lambda s: (
            ["ph", "density", "substrates", "products", "growth", "population"].index(s["group"]),
            order.index(s["key"]) if s["key"] in order else 0,
        )
    )
    # one sugar pool is just "sugars (total)" twice; protein is flat without proteolysis
    keys = {s["key"] for s in series}
    drop = set(SUGAR_KEYS) if len(keys & set(SUGAR_KEYS)) <= 1 else set()
    if not keys & {"amino_acids", "soluble_protein"}:
        drop.add("protein")
    series = [s for s in series if s["key"] not in drop]
    series_keys = {s["key"] for s in series}

    window = {k: v[:, :in_window] for k, v in values.items()}
    milestones = [
        m
        for ms in profile.milestones
        if (m := _milestone(ms, t_eval[:in_window], window, weights)) is not None
    ]
    misfits = _check_fit(obs, tr, z, weights, t_eval)

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
    if misfits:
        listed = ", ".join(misfits[:4]) + (" …" if len(misfits) > 4 else "")
        warnings.append(
            f"{len(misfits)} of your readings ({listed}) fall outside what the model can "
            "explain for this batch, so the calibration is approximate. Check those readings "
            "(and the recipe and temperature), or treat this forecast as rough."
        )
    elif tempered < 1.0 or lite.ess < 2 * MIN_ESS:
        warnings.append(
            "Calibration is approximate: few plausible parameter sets explain your readings "
            "(they sit at the edge of what the model covers), so the bands are rough."
        )
    if inputs.finished:
        warnings.append(
            "This batch is marked finished: \"now\" is when it ended, and the curves after "
            "that show how it would have continued."
        )

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
    options = sorted(
        {_nice_horizon(profile.horizon_h * f) for f in (0.25, 0.5, 1.0, 2.0)} | {horizon}
    )
    result = {
        "model": {
            "name": "FermentTrack kinetic ensemble",
            "version": MODEL_VERSION,
            "method": METHOD,
            "members": int(members),
            # the posterior's, also for a resampled what-if (duplicates add no information)
            "effective_members": round(min(float(lite.ess), float(members)), 1),
            "confidence": profile.confidence,
            "confidence_note": profile.confidence_note,
            "validated": False,
            "sources": sources,
        },
        "fermentation_type": inputs.fermentation_type,
        "started_at": None,  # filled in by the router (not part of the cached model output)
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
    return result
