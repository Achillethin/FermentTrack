"""Derived readouts of a forecast ensemble: nutrition per 100 g and taste over time.

Pure numpy, no DB. Computed per ensemble member from the trajectories after the kinetic
solve (the solve is unchanged), so the posterior your readings shaped carries over and a
what-if temperature moves these curves too. Aroma joins in increment B.
Design: docs/superpowers/specs/2026-10-02-flavour-nutrition-design.md § 2, 3, 7, 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from fermenttrack.prediction import compounds as C
from fermenttrack.prediction.engine import ACIDS, PI
from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.prediction.priors import FloatArray, Prior
from fermenttrack.prediction.profiles import FermentProfile, Milestone, TasteSpec

DERIVED_VERSION = "sensory-v1"
DISCLAIMER = (
    "Taste shows which tastes may be above their detection threshold for people tasting in "
    "water, not how it will taste to you. Spoilage off-flavours are not modelled: trust your "
    "nose and your pH reading over this view. Nutrition is a model estimate, not a lab "
    "analysis; not for labelling products for sale."
)
FAILED_WARNING = (
    "Taste and nutrition could not be computed for this batch; the forecast itself is "
    "unaffected."
)
ASSUMPTIONS = (
    "Per 100 g of what is in the jar: the CO₂ that escapes is subtracted; ethanol "
    "evaporation is ignored.",
    "Energy uses the EU labelling factors (Regulation (EU) 1169/2011, Annex XIV).",
    "Taste thresholds are measured in water; in a food other tastes mask each other, so "
    "real thresholds are higher.",
    "Glucose and fructose are one pool in the model, so their sweetness is uncertain.",
    "Not modelled yet: bitterness, fizz (dissolved CO₂), aroma.",
)
SUGARS = ("sucrose", "hexoses", "lactose", "maltose")
TASTES = ("sour", "sweet", "umami", "alcohol")
_ACID_IDX = np.array([PI[a] for a, _, _ in ACIDS])
_ACID_MW = np.array([mw for _, mw, _ in ACIDS])
# ponytail: pKa at I = 0; salt shifts it by <= 0.2 (engine.acid_ka), well inside the sour
# threshold's spread. Pass the batch's Ka' if a salty ferment ever needs it.
_ACID_KA = np.array([10.0**-pka for _, _, pka in ACIDS])
_LACTIC_MW = 90.08
FLOOR = -3.0  # log10 activity floor (a thousandth of the threshold): keeps log axes finite

# Nutrition-label rows in declaration order (Regulation (EU) 1169/2011): key, label, unit.
LABEL_ROWS: tuple[tuple[str, str, str], ...] = (
    ("energy_kj", "Energy", "kJ"),
    ("energy_kcal", "Energy", "kcal"),
    ("fat", "Fat", "g"),
    ("carbohydrate", "Carbohydrate", "g"),
    ("sugars", "of which sugars", "g"),
    ("lactose", "of which lactose", "g"),
    ("fibre", "Fibre", "g"),
    ("protein", "Protein", "g"),
    ("free_amino_acids", "of which free amino acids", "g"),
    ("salt", "Salt", "g"),
    ("alcohol", "Alcohol", "% ABV"),
    ("organic_acids", "Organic acids", "g"),
)


@dataclass(frozen=True)
class Carried:
    """Recipe nutrients the ferment does not change, g per kg of starting batch. None = no
    ingredient reports it (unknown, never zero); `lower` = label rows that are lower bounds
    (an ingredient without data, or one that does not report that nutrient)."""

    fat: float | None = None
    fibre: float | None = None
    sodium: float | None = None
    other_carbohydrate: float | None = None  # carbohydrate the model does not track
    lower: frozenset[str] = frozenset()


UNKNOWN = Carried()


def mass_left(pools: FloatArray, co2_escapes: bool) -> FloatArray:
    """(N, T) share of the starting mass still in the jar: the CO2 that escapes leaves."""
    co2 = pools[:, :, PI["co2"]]
    if not co2_escapes:
        return np.ones_like(co2)
    return np.asarray(1.0 - np.clip(co2, 0.0, 500.0) / 1000.0)


def nutrition(
    pools: FloatArray, carried: Carried, co2_escapes: bool
) -> tuple[dict[str, FloatArray], frozenset[str]]:
    """Label rows per 100 g of what remains, (N, T) each; unknown rows are absent."""
    left = mass_left(pools, co2_escapes)

    def p(k: str) -> FloatArray:
        return np.asarray(pools[:, :, PI[k]])

    def per100(g_per_kg: FloatArray) -> FloatArray:
        return np.asarray(g_per_kg / (10.0 * left))

    sugars = p("sucrose") + p("hexoses") + p("lactose") + p("maltose")
    ethanol = per100(p("ethanol"))
    rows: dict[str, FloatArray] = {
        "carbohydrate": per100(sugars + p("starch") + (carried.other_carbohydrate or 0.0)),
        "sugars": per100(sugars),
        "lactose": per100(p("lactose")),
        "protein": per100(p("protein") + p("peptides") + p("amino_acids")),
        "free_amino_acids": per100(p("amino_acids")),
        "organic_acids": per100(p("lactic_acid") + p("acetic_acid") + p("gluconic_acid")),
        "alcohol": np.asarray(ethanol * 10.0 / C.ETHANOL_G_PER_L_PER_ABV),
    }
    if carried.fat is not None:
        rows["fat"] = per100(np.full_like(left, carried.fat))
    if carried.fibre is not None:
        rows["fibre"] = per100(np.full_like(left, carried.fibre))
    if carried.sodium is not None:
        rows["salt"] = per100(np.full_like(left, carried.sodium * C.SALT_PER_SODIUM))
    zero = np.zeros_like(left)
    parts = {
        "carbohydrate": rows["carbohydrate"],
        "protein": rows["protein"],
        "fat": rows.get("fat", zero),
        "alcohol": ethanol,
        "organic_acid": rows["organic_acids"],
        "fibre": rows.get("fibre", zero),
    }
    rows["energy_kcal"] = np.asarray(sum(C.ENERGY[k][0] * v for k, v in parts.items()))
    rows["energy_kj"] = np.asarray(sum(C.ENERGY[k][1] * v for k, v in parts.items()))
    lower = set(carried.lower)
    if carried.other_carbohydrate is None:
        lower.add("carbohydrate")
    if carried.fat is None or carried.fibre is None or lower & {"fat", "fibre", "carbohydrate"}:
        lower |= {"energy_kcal", "energy_kj"}
    return rows, frozenset(lower & rows.keys())


# Displayed series: key -> (label, group, unit). Constant rows are label-only.
META: dict[str, tuple[str, str, str]] = {
    "nut:energy_kcal": ("Energy", "nutrition", "kcal/100 g"),
    "nut:sugars": ("Sugars", "nutrition", "g/100 g"),
    "nut:lactose": ("Lactose", "nutrition", "g/100 g"),
    "nut:organic_acids": ("Organic acids", "nutrition", "g/100 g"),
    "nut:free_amino_acids": ("Free amino acids", "nutrition", "g/100 g"),
    "nut:alcohol": ("Alcohol", "nutrition", "% ABV"),
    "taste:sour": ("Sour", "taste", "× threshold"),
    "taste:sweet": ("Sweet", "taste", "× threshold"),
    "taste:umami": ("Umami", "taste", "× threshold"),
    "taste:alcohol": ("Alcohol", "taste", "× threshold"),
}
# A series is shown only if its 95th percentile ever reaches this (absent: always shown).
_SHOW_IF = {
    "nut:lactose": 0.05, "nut:free_amino_acids": 0.05, "nut:alcohol": 0.05,
    "taste:sweet": -1.0, "taste:umami": -1.0, "taste:alcohol": -1.0,
}  # fmt: skip
_OPTIONAL_ROWS = {"lactose", "free_amino_acids", "alcohol"}  # left out when always ~0


@dataclass
class Derived:
    values: dict[str, FloatArray]  # (N, T): "nut:*" per 100 g, "taste:*" log10 activity,
    #                                "taste_phase" (phase index) when there is a ladder
    nutrition: dict[str, FloatArray]  # label row -> (N, T); unknown rows absent
    lower: frozenset[str]  # label rows that are lower bounds
    activity: dict[str, FloatArray]  # taste -> (N, T) concentration / threshold
    phases: tuple[str, ...] = ()


def _draws(n: int, spec: TasteSpec | None, seed: int) -> dict[str, FloatArray]:
    """Per-member thresholds, sweetness factors, glutamate share and ladder boundaries:
    nothing observes them, so prior draws are their posterior. Shaped (N, 1)."""
    priors: dict[str, Prior] = {
        "sweet": C.SWEET_THRESHOLD, "sour": C.SOUR_THRESHOLD,
        "umami": C.UMAMI_THRESHOLD, "alcohol": C.ALCOHOL_THRESHOLD,
        **{f"x:{k}": v for k, v in C.SWEETNESS.items()},
        "glu": C.GLUTAMATE_SHARE[spec.glutamate if spec else "soy"],
    }  # fmt: skip
    if spec is not None:
        priors.update({f"b{i}": b.threshold for i, b in enumerate(spec.boundaries)})
    z = np.random.default_rng(seed).standard_normal((n, len(priors)))
    return {k: np.asarray(p.value(z[:, j]))[:, None] for j, (k, p) in enumerate(priors.items())}


def evaluate(
    pools: FloatArray, ph: FloatArray, profile: FermentProfile, carried: Carried, seed: int,
    co2_escapes: bool = True,
) -> Derived:  # fmt: skip
    """Nutrition and taste for every member at every time of the trajectory."""
    rows, lower = nutrition(pools, carried, co2_escapes)
    spec = profile.taste
    d = _draws(pools.shape[0], spec, seed)
    left = mass_left(pools, co2_escapes)

    def p(k: str) -> FloatArray:
        return np.asarray(pools[:, :, PI[k]])

    sweet_raw = np.asarray(sum(d[f"x:{k}"] * p(k) for k in SUGARS))  # g sucrose-eq / kg start
    h = np.asarray(10.0**-ph)[..., None]  # mol/kg ~ mol/L
    mol = np.maximum(pools[:, :, _ACID_IDX], 0.0) / _ACID_MW  # (N, T, 3) mol/kg
    protonated = np.sum(mol * h / (h + _ACID_KA), axis=2)
    glu_mm = p("amino_acids") * d["glu"] / C.GLUTAMATE_MW * 1000.0 / left
    activity = {
        "sour": np.asarray((protonated + h[..., 0]) * 1000.0 / left / d["sour"]),
        "sweet": np.asarray(sweet_raw / left / d["sweet"]),
        "umami": np.asarray(glu_mm / d["umami"]),
        "alcohol": np.asarray(rows["alcohol"] / d["alcohol"]),
    }
    shown = ("energy_kcal", "sugars", "lactose", "organic_acids", "free_amino_acids", "alcohol")
    values = {f"nut:{k}": rows[k] for k in shown}
    values.update(
        {f"taste:{k}": np.log10(np.maximum(a, 10.0**FLOOR)) for k, a in activity.items()}
    )
    if spec is None:
        return Derived(values, rows, lower, activity)
    acids = p("lactic_acid") + p("acetic_acid") + p("gluconic_acid")
    metrics = {
        "sugar_acid": np.asarray(sweet_raw / np.maximum(acids, 1e-3)),  # g/g, both per kg
        "acetic": np.asarray(p("acetic_acid") / left),
        "acidity_pct": np.asarray(np.sum(mol, axis=2) * _LACTIC_MW / (10.0 * left)),
        "umami": activity["umami"],
    }
    phase = np.zeros_like(left)
    ok = np.ones(left.shape, dtype=bool)
    for i, b in enumerate(spec.boundaries):
        m, thr = metrics[b.metric], d[f"b{i}"]
        ok &= (m > thr) if b.kind == "above" else (m < thr)
        phase += ok
    values["taste_phase"] = phase
    return Derived(values, rows, lower, activity, spec.phases)


def taste_milestones(profile: FermentProfile) -> tuple[Milestone, ...]:
    """One loose milestone per taste phase after the first: first time a member is there."""
    spec = profile.taste
    if spec is None:
        return ()
    return tuple(
        Milestone(
            f"taste_{name.replace(' ', '_')}", f"{name.capitalize()} phase", note,
            "taste_phase", "above", k - 0.5, lens="taste",
        )  # fmt: skip
        for k, (name, note) in enumerate(zip(spec.phases[1:], spec.notes, strict=True), start=1)
    )


def series_out(
    der: Derived, idx: NDArray[np.intp], t_grid: FloatArray, w: FloatArray
) -> list[dict[str, Any]]:
    """PredictionSeriesOut-shaped bands on the display grid (`idx` into the trajectory)."""
    out: list[dict[str, Any]] = []
    for key, (label, group, unit) in META.items():
        v = der.values.get(key)
        if v is None:
            continue
        q = weighted_quantiles(v[:, idx], w, (0.05, 0.5, 0.95))
        if key in _SHOW_IF and float(np.max(q[2])) < _SHOW_IF[key]:
            continue
        digits = 0 if key == "nut:energy_kcal" else 2
        out.append(
            {
                "key": key, "label": label, "unit": unit, "group": group,
                "t_h": [round(float(x), 3) for x in t_grid],
                "p05": [round(float(x), digits) for x in q[0]],
                "p50": [round(float(x), digits) for x in q[1]],
                "p95": [round(float(x), digits) for x in q[2]],
            }
        )  # fmt: skip
    return out


def sensory_block(
    der: Derived, t: FloatArray, w: FloatArray, idx: NDArray[np.intp], now_h: float,
    end_i: int,
) -> dict[str, Any]:  # fmt: skip
    """PredictionOut.sensory. `t` is the trajectory's time axis, `idx` the display grid in
    it, `end_i` the last index inside the window; "now" clamps into [0, end_i]."""
    wn = w / w.sum()
    i_now = int(np.clip(np.searchsorted(t, now_h + 1e-9, side="right") - 1, 0, end_i))
    points = (("start", 0), ("now", i_now), ("end", end_i))

    def cell(v: FloatArray, i: int, key: str) -> dict[str, Any]:
        q = weighted_quantiles(v[:, i], w, (0.05, 0.5, 0.95))
        return {
            "p05": round(float(q[0]), 2), "p50": round(float(q[1]), 2),
            "p95": round(float(q[2]), 2), "lower_bound": key in der.lower,
        }  # fmt: skip

    label = []
    for key, name, unit in LABEL_ROWS:
        v = der.nutrition.get(key)
        cells = {when: (cell(v, i, key) if v is not None else None) for when, i in points}
        if key in _OPTIONAL_ROWS and all(c is not None and c["p95"] < 0.01 for c in cells.values()):
            continue
        label.append({"key": key, "label": name, "unit": unit, **cells})
    phases = None
    if der.phases:
        at = der.values["taste_phase"][:, idx]
        phases = {
            "vocabulary": list(der.phases),
            "t_h": [round(float(x), 3) for x in t[idx]],
            "prob": {
                name: [round(float(x), 3) for x in wn @ (at == k)]
                for k, name in enumerate(der.phases)
            },
        }
    noticeable = {
        when: {k: round(float(wn[der.activity[k][:, i] > 1.0].sum()), 3) for k in TASTES}
        for when, i in points[1:]
    }
    return {
        "derived_version": DERIVED_VERSION,
        "validated": False,
        "disclaimer": DISCLAIMER,
        "now_h": round(float(t[i_now]), 3),
        "end_h": round(float(t[end_i]), 3),
        "taste_phases": phases,
        "nutrition_label": label,
        "noticeable": noticeable,
        "assumptions": list(ASSUMPTIONS),
    }
