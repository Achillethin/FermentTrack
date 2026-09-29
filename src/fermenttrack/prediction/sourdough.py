"""Sourdough engine: levain styles and flours, a bake plan compiled into chained kinetic
phases (levain build -> dough bulk -> proof or cold retard), and the series bakers read
(rise, TTA, lactic:acetic ratio).

Every phase is one `engine.simulate` over the same z-vector per member, so a member keeps
its organism parameters from the levain into the dough. Mixing dilutes the ripe levain's
state (acids, sugars, cells, lag state) into the fresh dough ingredients. Design:
docs/superpowers/specs/2026-09-28-sourdough-engine-design.md.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from fermenttrack.prediction.engine import (
    N_POOLS,
    PI,
    EnsembleParams,
    Trajectories,
    acid_moles,
    charge_residual,
    initial_state,
    simulate,
)
from fermenttrack.prediction.model import (
    ModelSpec,
    ParamSpec,
    TemperatureFn,
    TemperatureSchedule,
)
from fermenttrack.prediction.organisms import (
    BAKERS_YEAST,
    ORGANISM_KINETICS,
    YEAST_CELL_G,
    OrganismKinetics,
)
from fermenttrack.prediction.priors import FloatArray, Prior
from fermenttrack.prediction.profiles import PROFILES


def _t(lo: float, med: float, hi: float) -> Prior:
    return Prior(med, lo, hi, "lin")


def _r(lo: float, med: float, hi: float) -> Prior:
    return Prior(med, lo, hi, "log")


# ── flours ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Flour:
    key: str
    name: str  # French grade: the T-number is the ash content x 1000
    us_name: str
    grain: Literal["wheat", "rye"]
    ash_pct: float
    protein_pct: float
    starch_pct: float
    sugars: dict[str, float]  # g/100 g: sucrose (rye: + accessible fructans), maltose, hexoses
    gluten: float  # rise cap relative to strong white wheat (rye has no gluten network)
    amylase: float  # cereal amylase activity relative to white wheat (rye: low falling number)
    water_pct: float = 13.0


_W = {"sucrose": 0.3, "maltose": 0.2, "hexoses": 0.1}
FLOURS: dict[str, Flour] = {
    f.key: f
    for f in [
        Flour("t45", "T45", "Pastry / Italian 00", "wheat", 0.45, 11.0, 72.0, _W, 1.0, 0.9),
        Flour("t55", "T55", "All-purpose flour", "wheat", 0.55, 11.0, 71.0, _W, 1.0, 1.0),
        Flour("t65", "T65", "Bread flour", "wheat", 0.65, 12.0, 69.0, _W, 1.0, 1.0),
        Flour("t80", "T80", "High-extraction flour", "wheat", 0.8, 12.5, 66.0, _W, 0.9, 1.1),
        Flour("t110", "T110", "Light whole wheat", "wheat", 1.1, 13.0, 63.0,
              {"sucrose": 0.4, "maltose": 0.2, "hexoses": 0.2}, 0.8, 1.2),
        Flour("t150", "T150", "Whole wheat flour", "wheat", 1.5, 13.2, 60.0,
              {"sucrose": 0.4, "maltose": 0.2, "hexoses": 0.2}, 0.7, 1.3),
        Flour("rye_t85", "T85 seigle", "Light rye", "rye", 0.85, 8.5, 68.0,
              {"sucrose": 1.0, "maltose": 0.3, "hexoses": 0.3}, 0.45, 2.0),
        Flour("rye_t130", "T130 seigle", "Medium rye", "rye", 1.3, 9.5, 62.0,
              {"sucrose": 1.2, "maltose": 0.3, "hexoses": 0.3}, 0.4, 2.0),
        Flour("rye_t170", "T170 seigle", "Whole rye (pumpernickel meal)", "rye", 1.7, 10.5, 56.0,
              {"sucrose": 1.4, "maltose": 0.3, "hexoses": 0.3}, 0.35, 2.0),
    ]
}  # fmt: skip


def buffer_per_kg_flour(ash_pct: float) -> Prior:
    """mmol H+ per kg flour per pH unit: minerals (phosphate, phytate) and protein buffer the
    dough, so buffering follows ash. A ripe white levain (~50 % flour, pH 6.1 -> 3.8 with
    TTA ~8-10) needs ~40/kg flour; whole grain buffers about twice that (est.)."""
    m = 22.0 + 30.0 * ash_pct
    return _r(0.6 * m, m, 1.6 * m)


# ── styles ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LevainStyle:
    key: str
    name: str
    native_name: str
    type: Literal["0", "I", "II", "III"]
    seed: Literal["starter", "yeast", "dried"]
    description: str
    # starter: log10 CFU/g in the ripe starter (the build's inoculum is this + log10 of the
    # seed's mass share). yeast/dried: empty (baker's yeast comes from the grams used).
    organisms: dict[str, Prior]
    acids: dict[str, float]  # g/kg in the ripe starter (dried: in the powder)
    hydration_pct: float
    seed_ratio: float  # g flour fed per g seed (yeast styles: per g yeast)
    temperature_c: float
    flour: str
    hours: float | None = None  # a fixed build time; None = use at the peak
    # An active starter fed at its peak restarts within ~1-2 h (a vegetable ferment's wild
    # flora needs ~10x longer): scales each organism's Baranyi h0.
    h0_factor: float = 0.15
    notes: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()


_SF = "Lactobacillus sanfranciscensis"
_KH = "Kazachstania humilis"
_SC = "Saccharomyces cerevisiae"
_LP = "Lactobacillus plantarum"
_LB = "Lactobacillus brevis"
_LR = "Lactobacillus reuteri"

STYLES: dict[str, LevainStyle] = {
    s.key: s
    for s in [
        LevainStyle(
            "home_starter", "Home wheat starter", "Home starter", "I", "starter",
            "The typical kitchen starter: wheat flour and water, fed daily. Mostly "
            "S. cerevisiae with L. plantarum and L. brevis (a 500-starter survey).",
            {_SC: _t(7.0, 7.7, 8.4), _LP: _t(8.2, 8.7, 9.2), _LB: _t(8.2, 8.7, 9.2)},
            {"lactic_acid": 7.0, "acetic_acid": 1.5}, 100.0, 5.0, 24.0, "t65",
            sources=("Landis et al. 2021 eLife 10:e61644",),
        ),
        LevainStyle(
            "levain_liquide", "Liquid levain", "Levain liquide", "I", "starter",
            "French bakery liquid levain (100-125 % hydration): fast, mild and lactic.",
            {_SF: _t(8.8, 9.2, 9.5), _SC: _t(6.9, 7.4, 7.9)},
            {"lactic_acid": 7.5, "acetic_acid": 1.2}, 100.0, 3.0, 26.0, "t65",
            sources=("Minervini et al. 2014 AEM 80:3161",),
        ),
        LevainStyle(
            "levain_dur", "Stiff levain", "Levain dur", "I", "starter",
            "Stiff levain (50-65 % hydration): slower, keeps longer, more acetic tang.",
            {_SF: _t(8.6, 9.0, 9.4), _KH: _t(6.8, 7.3, 7.8), _SC: _t(6.5, 7.0, 7.5)},
            {"lactic_acid": 9.0, "acetic_acid": 2.5}, 55.0, 3.0, 24.0, "t65",
            sources=("Minervini et al. 2014 AEM 80:3161",),
        ),
        LevainStyle(
            "lievito_madre", "Italian mother dough", "Lievito madre", "I", "starter",
            "Very stiff (45-50 %), warm (26-28 °C), refreshed every few hours and used young: "
            "mild acidity, strong leavening for panettone and pandoro.",
            {_SF: _t(8.5, 8.9, 9.3), _KH: _t(7.0, 7.5, 8.0)},
            {"lactic_acid": 5.0, "acetic_acid": 1.0}, 45.0, 1.0, 27.0, "t45",
            h0_factor=0.1,  # refreshed every few hours: barely any lag
            sources=("Carbonetto et al. 2020 Microorganisms 8:240",),
        ),
        LevainStyle(
            "san_francisco", "San Francisco sourdough", "San Francisco", "I", "starter",
            "The classic SF sponge: L. sanfranciscensis with K. humilis, rebuilt every ~8 h "
            "at ~27 °C; very sour.",
            {_SF: _t(8.9, 9.3, 9.6), _KH: _t(6.9, 7.4, 7.9)},
            {"lactic_acid": 8.0, "acetic_acid": 2.5}, 55.0, 2.5, 27.0, "t65", hours=8.0,
            sources=("Kline & Sugihara 1971 Appl Microbiol 21:459", "Gänzle et al. 1998 AEM 64:2616"),
        ),
        LevainStyle(
            "rye_sour", "Rye sour", "Roggensauerteig", "I", "starter",
            "Rye sourdough (80-100 % hydration, 26-30 °C, 12-20 h): high acidity is the goal; "
            "rye has no gluten, so it rises little.",
            {_SF: _t(8.6, 9.0, 9.4), _LB: _t(8.2, 8.7, 9.2), _KH: _t(6.7, 7.2, 7.7)},
            {"lactic_acid": 10.0, "acetic_acid": 3.0}, 90.0, 10.0, 28.0, "rye_t130", hours=16.0,
            sources=("Brandt et al. 2004 Eur Food Res Technol 218:333",),
        ),
        LevainStyle(
            "type_ii", "Liquid sour (Type II)", "Type II sourdough", "II", "starter",
            "Industrial liquid sour: warm (35-40 °C), long, thermophilic lactobacilli. An "
            "acidifier for flavour, not a leavener: the dough needs yeast.",
            {_LR: _t(9.0, 9.3, 9.6)},
            {"lactic_acid": 12.0, "acetic_acid": 3.0}, 200.0, 10.0, 37.0, "t80", hours=18.0,
            sources=("Gänzle & Vogel 2003 Int J Food Microbiol 80:31",),
        ),
        LevainStyle(
            "type_iii", "Dried sourdough (Type III)", "Type III sourdough", "III", "dried",
            "Dried sour powder added to a yeasted dough: acidity and flavour, no live culture.",
            {}, {"lactic_acid": 60.0, "acetic_acid": 10.0}, 0.0, 0.0, 26.0, "t65",
            notes=("Powder acid content is a typical value (est.); check the product sheet.",),
            sources=("De Vuyst & Neysens 2005 Trends Food Sci Technol 16:43",),
        ),
        LevainStyle(
            "poolish", "Poolish", "Poolish", "0", "yeast",
            "Yeasted liquid pre-ferment (100 %, ~0.1 % yeast, 12-16 h at room temperature): "
            "extensibility and aroma, little acidity.",
            {}, {}, 100.0, 1000.0, 20.0, "t65",
        ),
        LevainStyle(
            "biga", "Biga", "Biga", "0", "yeast",
            "Stiff yeasted pre-ferment (45-55 %, ~0.3 % yeast, 16-20 h cool): strength and a "
            "mild tang.",
            {}, {}, 50.0, 330.0, 18.0, "t65",
        ),
    ]
}  # fmt: skip


# Yeasts in dough ferment far faster than the same species in sweet tea (the kombucha
# calibration behind the S. cerevisiae prior): ~1-2 g sugar per g dry yeast per hour, as
# commercial yeast in rheofermentometer doughs. Pooled parameters (mu_max, t_opt) are
# never overridden here, so learned priors keep one meaning across ferment types.
DOUGH_KINETICS: dict[str, dict[str, Prior]] = {
    # wide on purpose: starters differ ~15x in rise rate (0.1-1.5 mm/h, Landis et al. 2021)
    _SC: {"maint": _r(0.7, 1.8, 4.0)},
    _KH: {"maint": _r(0.7, 1.8, 4.0)},
}


def dough_kinetics(name: str) -> OrganismKinetics:
    return dataclasses.replace(ORGANISM_KINETICS[name], **DOUGH_KINETICS.get(name, {}))


def style_organisms(style: LevainStyle, uses_yeast: bool) -> list[str]:
    names = list(style.organisms)
    if style.seed == "yeast" or uses_yeast:
        names.append(BAKERS_YEAST)
    return names


# ── plan ────────────────────────────────────────────────────────────────

Blend = tuple[tuple[str, float], ...]


def blend(flour: dict[str, float] | str) -> Blend:
    """{flour key: share} -> normalised, sorted (hashable) blend."""
    d = {flour: 1.0} if isinstance(flour, str) else {k: float(v) for k, v in flour.items() if v > 0}
    unknown = set(d) - set(FLOURS)
    if unknown or not d:
        raise ValueError(f"unknown flour(s): {sorted(unknown) or 'none given'}")
    total = sum(d.values())
    return tuple(sorted((k, v / total) for k, v in d.items()))


@dataclass(frozen=True)
class Build:
    seed_g: float
    flour_g: float
    water_g: float
    flour: Blend
    temperature_c: float
    hours: float | None = None


@dataclass(frozen=True)
class Dough:
    flour_g: float
    water_g: float
    salt_g: float
    flour: Blend
    temperature_c: float
    levain_g: float | None = None
    yeast_g: float = 0.0
    yeast: Literal["instant", "fresh"] = "instant"
    dried_sour_g: float = 0.0
    bulk_hours: float | None = None
    target_rise_pct: float = 75.0


@dataclass(frozen=True)
class Proof:
    temperature_c: float
    hours: float


@dataclass(frozen=True)
class Plan:
    style: str
    levain: Build | None
    dough: Dough | None = None
    proof: Proof | None = None
    starter: Literal["ripe", "refrigerated"] = "ripe"


def plan_from_dict(d: dict[str, Any]) -> Plan:
    """The JSON plan (API, batches.sourdough_plan) -> Plan. Raises ValueError when invalid."""
    style = STYLES.get(d.get("style", ""))
    if style is None:
        raise ValueError(f"unknown style {d.get('style')!r}")
    lv, dg, pf = d.get("levain"), d.get("dough"), d.get("proof")
    levain = (
        Build(
            float(lv["seed_g"]), float(lv["flour_g"]), float(lv["water_g"]),
            blend(lv.get("flour") or style.flour), float(lv["temperature_c"]),
            None if lv.get("hours") is None else float(lv["hours"]),
        )
        if lv
        else None
    )  # fmt: skip
    dough = (
        Dough(
            float(dg["flour_g"]), float(dg["water_g"]), float(dg.get("salt_g") or 0.0),
            blend(dg.get("flour") or style.flour), float(dg["temperature_c"]),
            None if dg.get("levain_g") is None else float(dg["levain_g"]),
            float(dg.get("yeast_g") or 0.0), dg.get("yeast") or "instant",
            float(dg.get("dried_sour_g") or 0.0),
            None if dg.get("bulk_hours") is None else float(dg["bulk_hours"]),
            float(dg.get("target_rise_pct") or 75.0),
        )
        if dg
        else None
    )  # fmt: skip
    proof = Proof(float(pf["temperature_c"]), float(pf["hours"])) if pf else None
    plan = Plan(style.key, levain, dough, proof, d.get("starter") or "ripe")
    validate(plan)
    return plan


def validate(plan: Plan) -> None:
    style = STYLES[plan.style]
    if style.seed == "dried":
        if plan.levain is not None:
            raise ValueError("a dried (Type III) sourdough has no levain build")
        if plan.dough is None or plan.dough.dried_sour_g <= 0 or plan.dough.yeast_g <= 0:
            raise ValueError("a Type III dough needs dried_sour_g and yeast_g")
    elif plan.levain is None:
        raise ValueError("this style needs a levain build")
    if plan.levain is not None:
        b = plan.levain
        if b.seed_g <= 0 or b.flour_g <= 0 or b.water_g < 0:
            raise ValueError("levain seed and flour must be positive")
    if plan.dough is not None:
        dg = plan.dough
        if dg.flour_g <= 0 or dg.water_g < 0 or dg.salt_g < 0 or dg.yeast_g < 0:
            raise ValueError("dough flour must be positive; water, salt, yeast not negative")
        if plan.levain is not None and dg.levain_g is not None:
            total = plan.levain.seed_g + plan.levain.flour_g + plan.levain.water_g
            if not 0 < dg.levain_g <= total * 1.001:
                raise ValueError("levain_g must be between 0 and the levain built")
    if plan.proof is not None and plan.dough is None:
        raise ValueError("a proof needs a dough")
    leavens = style.seed == "yeast" or any(
        ORGANISM_KINETICS[o].kingdom == "yeast" for o in style.organisms
    )
    if plan.dough is not None and not leavens and plan.dough.yeast_g <= 0:
        raise ValueError(f"{style.name} does not leaven: the dough needs yeast (yeast_g)")


def plan_to_dict(plan: Plan) -> dict[str, Any]:
    d = dataclasses.asdict(plan)
    for part in ("levain", "dough"):
        if d[part] is not None:
            d[part]["flour"] = dict(d[part]["flour"])
    return d


# ── phases ──────────────────────────────────────────────────────────────

INSTANT_YEAST_CFU_G = 2e10  # viable cells per g instant dry yeast (est. 1-3e10)
FRESH_YEAST_CFU_G = 1e10  # per g fresh compressed yeast (~30 % dry matter)
REFRIGERATED_LAG = 3.0  # a starter straight from the fridge lags ~3x longer (est.)
RAMP_H = 3.0  # a 1 kg dough takes hours to reach fridge temperature
FLOUR_SOLIDS_KG_L = 1.45


@dataclass
class _Mass:
    """Running composition of a mix, grams."""

    total: float = 0.0
    water: float = 0.0  # incl. flour moisture
    added_water: float = 0.0  # baker's hydration counts this
    flour: float = 0.0  # as-is flour mass
    salt: float = 0.0
    ash: float = 0.0  # g ash (for the blend's ash %)
    gluten: float = 0.0  # flour-weighted
    amylase: float = 0.0
    pools: dict[str, float] = field(default_factory=dict)

    def add_flour(self, grams: float, b: Blend) -> None:
        for key, share in b:
            f, g = FLOURS[key], grams * share
            self.total += g
            self.flour += g
            self.water += g * f.water_pct / 100.0
            self.ash += g * f.ash_pct / 100.0
            self.gluten += g * f.gluten
            self.amylase += g * f.amylase
            # only damaged starch is open to the flour's amylases (profiles: starch_accessible)
            starch = f.starch_pct * PROFILES["sourdough"].starch_accessible
            for pool, pct in (("starch", starch), ("protein", f.protein_pct), *f.sugars.items()):
                self.pools[pool] = self.pools.get(pool, 0.0) + g * pct / 100.0

    def add_water(self, grams: float) -> None:
        self.total += grams
        self.water += grams
        self.added_water += grams

    def add_acids(self, grams_carrier: float, acids: dict[str, float]) -> None:
        for acid, g_per_kg in acids.items():
            self.pools[acid] = self.pools.get(acid, 0.0) + grams_carrier * g_per_kg / 1000.0


@dataclass
class Phase:
    key: str  # levain | bulk | proof
    label: str
    temperature_c: float
    hours: float | None  # fixed duration; None = decided from the forecast (peak, target)
    carry: float  # mass share carried over from the previous phase (0 for the first)
    pools_fresh: dict[str, float]  # g/kg of this phase's mass, fresh ingredients only
    water_frac: float
    flour_frac: float
    ash_pct: float
    gluten: float
    amylase: float
    hydration_pct: float
    salt_wps: float
    x_add: dict[str, float]  # organism -> log10 CFU/g added at the start (baker's yeast)
    continues: bool = False  # same matrix as the previous phase (proof after bulk)


def _phase_from(key: str, label: str, m: _Mass, temp: float, hours: float | None,
                carry: float, x_add: dict[str, float]) -> Phase:  # fmt: skip
    kg = m.total / 1000.0
    return Phase(
        key=key,
        label=label,
        temperature_c=temp,
        hours=hours,
        carry=carry,
        pools_fresh={k: v / kg for k, v in m.pools.items()},
        water_frac=m.water / m.total,
        flour_frac=m.flour / m.total,
        ash_pct=100.0 * m.ash / m.flour if m.flour else 0.6,
        gluten=m.gluten / m.flour if m.flour else 1.0,
        amylase=m.amylase / m.flour if m.flour else 1.0,
        hydration_pct=100.0 * m.added_water / m.flour if m.flour else 100.0,
        salt_wps=100.0 * m.salt / (m.salt + m.water) if m.salt else 0.0,
        x_add=x_add,
    )


def _yeast_log_cfu(grams: float, kind: str, total_g: float) -> float:
    per_g = INSTANT_YEAST_CFU_G if kind == "instant" else FRESH_YEAST_CFU_G
    return math.log10(max(grams * per_g / total_g, 1e-3))


@dataclass
class Compiled:
    style: LevainStyle
    plan: Plan
    organisms: list[str]
    phases: list[Phase]
    inoculum: dict[str, Prior]  # phase-0 inoculum, log10 CFU/g
    summary: dict[str, Any]


def compile_plan(plan: Plan, extra_organisms: tuple[str, ...] = ()) -> Compiled:
    """Plan -> phases with their compositions. `extra_organisms`: custom attachments of a
    tracked batch (modelled at a modest added-culture level, as in the batch forecast)."""
    style = STYLES[plan.style]
    uses_yeast = bool(plan.dough and plan.dough.yeast_g > 0)
    names = style_organisms(style, uses_yeast)
    names += [n for n in extra_organisms if n not in names and n in ORGANISM_KINETICS]
    phases: list[Phase] = []
    inoculum: dict[str, Prior] = {}
    summary: dict[str, Any] = {"style": style.key}
    absent = _t(-2.5, -2.0, -1.5)  # arrives later (baker's yeast at mixing)

    levain_mass: _Mass | None = None
    if plan.levain is not None:
        b = plan.levain
        m = _Mass()
        if style.seed == "starter":
            # ripe seed at the style's hydration: its flour and water, its acids
            seed_flour = b.seed_g / (1.0 + style.hydration_pct / 100.0)
            m.add_flour(seed_flour, b.flour)
            m.add_water(b.seed_g - seed_flour)
            m.add_acids(b.seed_g, style.acids)
        m.add_flour(b.flour_g, b.flour)
        m.add_water(b.water_g)
        if style.seed == "yeast":
            m.total += b.seed_g
        share = b.seed_g / m.total
        for name in names:
            if name in style.organisms:
                inoculum[name] = _shift(style.organisms[name], math.log10(share))
            elif name == BAKERS_YEAST and style.seed == "yeast":
                v = _yeast_log_cfu(b.seed_g, "instant", m.total)
                inoculum[name] = _t(v - 0.3, v, v + 0.2)
            elif name == BAKERS_YEAST:
                inoculum[name] = absent
            else:
                inoculum[name] = _t(3.5, 5.0, 6.5)  # a custom addition to the batch
        label = {"yeast": style.name, "starter": "Levain"}.get(style.seed, "Levain")
        phases.append(_phase_from("levain", label, m, b.temperature_c, b.hours, 0.0, {}))
        levain_mass = m
        summary |= {
            "levain_hydration_pct": round(phases[0].hydration_pct, 1),
            "seed_ratio": _ratio_label(b.seed_g, b.flour_g, b.water_g),
            "levain_g": round(m.total, 1),
        }

    if plan.dough is not None:
        dg = plan.dough
        m = _Mass()
        lev_g = 0.0
        if levain_mass is not None:
            lev_g = levain_mass.total if dg.levain_g is None else dg.levain_g
            k = lev_g / levain_mass.total
            # the levain's matrix (flour, water, salt) comes along; its pools come from
            # the simulated levain state at mixing, not from here
            m.total += lev_g
            m.water += levain_mass.water * k
            m.added_water += levain_mass.added_water * k
            m.flour += levain_mass.flour * k
            m.ash += levain_mass.ash * k
            m.gluten += levain_mass.gluten * k
            m.amylase += levain_mass.amylase * k
        fresh = _Mass()
        fresh.add_flour(dg.flour_g, dg.flour)
        fresh.add_water(dg.water_g)
        fresh.total += dg.salt_g + dg.yeast_g
        if dg.dried_sour_g:
            fresh.add_flour(0.92 * dg.dried_sour_g, dg.flour)  # the powder is mostly flour
            fresh.total += 0.08 * dg.dried_sour_g
            fresh.add_acids(dg.dried_sour_g, style.acids)
        m.total += fresh.total
        m.water += fresh.water
        m.added_water += fresh.added_water
        m.flour += fresh.flour
        m.ash += fresh.ash
        m.gluten += fresh.gluten
        m.amylase += fresh.amylase
        m.salt = dg.salt_g
        m.pools = fresh.pools
        x_add: dict[str, float] = {}
        if dg.yeast_g > 0:
            x_add[BAKERS_YEAST] = _yeast_log_cfu(dg.yeast_g, dg.yeast, m.total)
        carry = lev_g / m.total
        if not phases:  # Type III: the dough is the first phase
            for name in names:
                v = x_add.pop(name, None)
                inoculum[name] = _t(v - 0.3, v, v + 0.2) if v is not None else absent
        phases.append(_phase_from("bulk", "Bulk", m, dg.temperature_c, dg.bulk_hours, carry, x_add))
        flour_total = m.flour
        summary |= {
            "levain_pct_of_flour": round(100.0 * lev_g / flour_total, 1) if lev_g else 0.0,
            "dough_hydration_pct": round(phases[-1].hydration_pct, 1),
            "salt_pct_of_flour": round(100.0 * dg.salt_g / flour_total, 2),
            "total_flour_g": round(flour_total, 1),
            "target_rise_pct": dg.target_rise_pct,
        }
    if plan.proof is not None:
        prev = phases[-1]
        label = "Cold retard" if plan.proof.temperature_c < 10 else "Proof"
        phases.append(
            dataclasses.replace(
                prev, key="proof", label=label, temperature_c=plan.proof.temperature_c,
                hours=plan.proof.hours, carry=1.0, pools_fresh={}, x_add={}, continues=True,
            )
        )  # fmt: skip
    return Compiled(style, plan, names, phases, inoculum, summary)


def _ratio_label(seed: float, flour: float, water: float) -> str:
    def f(x: float) -> str:
        return f"{x / seed:.1f}".removesuffix(".0")

    return f"1:{f(flour)}:{f(water)}"


def _shift(prior: Prior, delta: float) -> Prior:
    return Prior(prior.median + delta, prior.lo + delta, prior.hi + delta, prior.scale)


def _scale(prior: Prior, c: float) -> Prior:
    return Prior(prior.median * c, prior.lo * c, prior.hi * c, prior.scale)


# ── the chained ensemble model ──────────────────────────────────────────

# Sourdough-only parameters, appended after the kinetic spec's columns.
PHI_REF = _r(0.15, 0.3, 0.55)  # acetate share of the C2 branch at 100 % hydration, 25 °C
HYDRATION_EXPONENT = 0.8  # phi ~ hydration^-0.8: FQ 2.4x between DY 160 and 280 (Minervini 2014)
RISE_MAX = _r(120.0, 200.0, 320.0)  # % rise a strong white-wheat dough can hold (est.)
LEAK0 = _r(0.01, 0.03, 0.08)  # 1/h gas loss of a sound dough (~88 % retained, Rheo F4)
LEAK_ACID = _r(0.1, 0.3, 0.8)  # 1/h extra loss once acid has weakened the gluten (est.)
EXTRA_PARAMS: tuple[tuple[str, Prior], ...] = (
    ("phi_ref", PHI_REF), ("rise_max", RISE_MAX), ("leak0", LEAK0), ("leak_acid", LEAK_ACID),
)  # fmt: skip
# Gluten weakening (acid swelling, proteolysis) starts below this pH (est.; calibrated so
# the median levain peaks near baker timings: 1:4:4 at ~25.6 °C in ~12 h, King Arthur 2025).
WEAK_PH = 4.5
WEAK_SPAN = 0.6
# Weakening is a rate process (acid swelling, flour proteases): it builds with the hours of
# acid exposure, half its effect after DAMAGE_HALF_H of full exposure (est.), so a freshly
# fed, already acidic 1:1:1 still holds its gas for hours.
DAMAGE_HALF_H = 3.0
# CO2 solubility in the liquid phase of dough: 1.6e-5 (0 °C) to 5e-6 (50 °C) g/(kPa g)
CO2_SOL_0C = 1.6e-5
CO2_SOL_K = math.log(1.6e-5 / 5e-6) / 50.0
P_ATM_KPA = 101.325
TTA_END_PH = 8.5
GAS_DT = 0.1  # h, internal step of the gas balance (converged: see the grid test)


def co2_saturation(temp_c: FloatArray, water_frac: FloatArray | float) -> FloatArray:
    """g CO2 per kg dough the dough water holds before bubbles grow (1 atm CO2)."""
    return np.asarray(water_frac * 1000.0 * CO2_SOL_0C * np.exp(-CO2_SOL_K * temp_c) * P_ATM_KPA)


def gas_litres_per_g(temp_c: FloatArray) -> FloatArray:
    return np.asarray(22.414 * (temp_c + 273.15) / 273.15 / 44.01)


def dough_litres_per_kg(water_frac: float) -> float:
    return water_frac + (1.0 - water_frac) / FLOUR_SOLIDS_KG_L


@dataclass
class PhaseTrace:
    """One phase run: states and derived series at absolute times t (N members)."""

    k: int
    start: float  # the phase's own t = 0 (absolute h)
    t: FloatArray  # (T,) absolute h
    y: FloatArray  # (N, T, state) raw ODE states
    pools: FloatArray
    biomass: FloatArray
    ph: FloatArray
    rise: FloatArray
    gas: FloatArray
    excess: FloatArray
    damage: FloatArray
    tta: FloatArray
    fq: FloatArray
    seg: dict[str, Any]

    def cut(self, a: int, b: int) -> PhaseTrace:
        """Points a..b-1."""
        sl = slice(a, b)
        return dataclasses.replace(
            self, t=self.t[sl], y=self.y[:, sl], pools=self.pools[:, sl],
            biomass=self.biomass[:, sl], ph=self.ph[:, sl], rise=self.rise[:, sl],
            gas=self.gas[:, sl], excess=self.excess[:, sl], damage=self.damage[:, sl],
            tta=self.tta[:, sl], fq=self.fq[:, sl],
        )  # fmt: skip

    def join(self, more: PhaseTrace) -> PhaseTrace:
        """This trace continued by `more` (which starts at this trace's last point)."""
        cat = np.concatenate
        return dataclasses.replace(
            self, t=cat([self.t, more.t[1:]]), y=cat([self.y, more.y[:, 1:]], axis=1),
            pools=cat([self.pools, more.pools[:, 1:]], axis=1),
            biomass=cat([self.biomass, more.biomass[:, 1:]], axis=1),
            ph=cat([self.ph, more.ph[:, 1:]], axis=1),
            rise=cat([self.rise, more.rise[:, 1:]], axis=1),
            gas=cat([self.gas, more.gas[:, 1:]], axis=1),
            excess=cat([self.excess, more.excess[:, 1:]], axis=1),
            damage=cat([self.damage, more.damage[:, 1:]], axis=1),
            tta=cat([self.tta, more.tta[:, 1:]], axis=1),
            fq=cat([self.fq, more.fq[:, 1:]], axis=1),
        )  # fmt: skip


def assemble(
    pieces: list[tuple[PhaseTrace, FloatArray]], t_eval: FloatArray, n: int, m: int
) -> Trajectories:
    """Trajectories at t_eval from phase traces, each covering t_eval[mask]."""
    pools = np.zeros((n, len(t_eval), N_POOLS))
    biomass = np.zeros((n, len(t_eval), m))
    ph_out = np.zeros((n, len(t_eval)))
    extra = {k: np.zeros((n, len(t_eval))) for k in ("rise", "tta", "fq")}
    last: PhaseTrace | None = None
    for tr, mask in pieces:
        idx = np.clip(np.searchsorted(tr.t, t_eval[mask] - 1e-9), 0, len(tr.t) - 1)
        pools[:, mask] = tr.pools[:, idx]
        biomass[:, mask] = tr.biomass[:, idx]
        ph_out[:, mask] = tr.ph[:, idx]
        extra["rise"][:, mask] = tr.rise[:, idx]
        extra["tta"][:, mask] = tr.tta[:, idx]
        extra["fq"][:, mask] = tr.fq[:, idx]
        last = tr
    return Trajectories(
        t_h=t_eval, pools=pools, biomass_g=biomass, ph=ph_out, extra=extra,
        y_end=None if last is None else last.y[:, -1],
    )  # fmt: skip


class SourdoughModel:
    """Duck-types ModelSpec for inference: `specs`, `dim`, `simulate_z(z, t_eval)`.

    `bounds[k]` is the start (h from the levain feed) of phase k."""

    def __init__(
        self,
        compiled: Compiled,
        bounds: list[float] | None = None,
        population_priors: dict[str, dict[str, Prior]] | None = None,
        measured_temps: dict[int, float] | None = None,
    ) -> None:
        self.compiled = compiled
        self.bounds = bounds or [0.0]
        self.phases = compiled.phases if bounds is None else compiled.phases[: len(bounds)]
        style = compiled.style
        base = PROFILES["sourdough"]
        lag = style.h0_factor * (REFRIGERATED_LAG if compiled.plan.starter == "refrigerated" else 1.0)
        kins: list[OrganismKinetics] = [dough_kinetics(n) for n in compiled.organisms]
        inoc = [compiled.inoculum[n] for n in compiled.organisms]
        self.organisms = kins
        measured = measured_temps or {}
        self.phase_specs: list[ModelSpec] = []
        prev_temp: float | None = None
        for k, ph in enumerate(self.phases):
            temp = measured.get(k, ph.temperature_c)
            profile = dataclasses.replace(
                base,
                buffer_mm=_scale(buffer_per_kg_flour(ph.ash_pct), ph.flour_frac),
                flour_amylase=_scale(base.flour_amylase, ph.amylase) if base.flour_amylase else None,
                h0_factor=lag,
                x_max_override={},
            )
            if prev_temp is not None and abs(temp - prev_temp) > 5.0:
                ramp = RAMP_H if ph.hours is None else min(RAMP_H, ph.hours / 2)
                knots = ([0.0, ramp], [prev_temp, temp])
            else:
                knots = ([0.0], [temp])
            est = 0.0 if k in measured else 1.0
            sched = TemperatureSchedule(knots[0], knots[1], [est] * len(knots[0]))
            self.phase_specs.append(
                ModelSpec(
                    profile=profile,
                    organisms=kins,
                    can_grow=[True] * len(kins),
                    inoculum=inoc,
                    pools0=ph.pools_fresh,
                    salt_water_phase_pct=ph.salt_wps,
                    schedule=sched,
                    population_priors=population_priors or {},
                )
            )
            prev_temp = temp
        s0 = self.phase_specs[0]
        self.base_dim = s0.dim
        self.specs: list[ParamSpec] = [*s0.specs, *(ParamSpec(n, p) for n, p in EXTRA_PARAMS)]
        self.dim = len(self.specs)

    # ModelSpec duck-typing (population pooling reads specs/organisms; run uses dim)
    def params(self, z: FloatArray) -> EnsembleParams:
        return self.phase_specs[0].params(z[:, : self.base_dim])

    def extra_values(self, z: FloatArray) -> dict[str, FloatArray]:
        return {
            name: prior.value(z[:, self.base_dim + i])
            for i, (name, prior) in enumerate(EXTRA_PARAMS)
        }

    def phase_params(self, k: int, z: FloatArray) -> EnsembleParams:
        p = self.phase_specs[k].params(z[:, : self.base_dim])
        hyd = max(self.phases[k].hydration_pct, 20.0)
        p.c2_acetate = self.extra_values(z)["phi_ref"] * (100.0 / hyd) ** HYDRATION_EXPONENT
        return p

    def run_phase(
        self,
        k: int,
        z: FloatArray,
        t_abs: FloatArray,
        prev: PhaseTrace | None = None,
        i: int | None = None,
        extend: bool = False,
    ) -> PhaseTrace:
        """Phase k over the absolute times t_abs (t_abs[0] = where it starts). It starts from
        `prev` at index i: mixed into the phase's fresh ingredients, or (extend=True) the
        same phase simply continued. Raw states are kept so a later boundary can start
        the next phase from any of these times."""
        ph = self.phases[k]
        p = self.phase_params(k, z)
        ex = self.extra_values(z)
        n = z.shape[0]
        t_abs = np.asarray(t_abs, dtype=float)
        if len(t_abs) == 1:  # zero-length phase
            t_abs = np.array([t_abs[0], t_abs[0] + 1e-6])
        # The gas balance steps explicitly between output times: always run it on a fine
        # internal grid, so the rise does not depend on which times were asked for
        # (sparse calibration grids vs the forecast grid).
        t_abs = np.unique(np.r_[t_abs, np.arange(t_abs[0], t_abs[-1], GAS_DT)])
        phase_start = prev.start if extend and prev is not None else float(t_abs[0])
        local = t_abs - phase_start  # the phase's own clock (temperature ramps)
        if prev is None:
            y0 = None
        else:
            assert i is not None
            y0 = prev.y[:, i] if extend else self._mix(prev.y[:, i], p, ph)
        tr = simulate(p, local, y0=y0, keep_states=True)
        assert tr.y is not None
        temps = np.stack([p.temperature(float(t)) for t in local], axis=1)
        co2 = tr.pools[:, :, PI["co2"]]
        if prev is not None and (extend or ph.continues):
            assert i is not None
            seg = prev.seg  # the same dough: its gas keeps building
            gas0, e0, dmg0 = prev.gas[:, i], prev.excess[:, i], prev.damage[:, i]
        else:  # a fresh mix starts a new gas balance
            sat0 = co2_saturation(temps[:, 0], ph.water_frac)
            seg = {
                "co2_0": co2[:, 0],
                # the carried culture was saturated with CO2 already
                "d0": (ph.carry if prev is not None else _seed_share(self.compiled)) * sat0,
                "rmax": ex["rise_max"] * ph.gluten,
                "w": np.full(n, ph.water_frac),
                "v0": np.full(n, dough_litres_per_kg(ph.water_frac)),
            }
            gas0, dmg0 = np.zeros(n), np.zeros(n)  # fresh flour: an intact gluten network
            e0 = np.maximum(seg["d0"] - sat0, 0.0)
        rise, gas, excess, damage = _gas_balance(
            local, temps, co2 - seg["co2_0"][:, None], tr.ph, seg, gas0, e0, dmg0,
            ex["leak0"], ex["leak_acid"],
        )  # fmt: skip
        return PhaseTrace(
            k=k, start=phase_start, t=t_abs, y=tr.y, pools=tr.pools, biomass=tr.biomass_g,
            ph=tr.ph, rise=rise, gas=gas, excess=excess, damage=damage,
            tta=tta(tr.pools, p), fq=fermentation_quotient(tr.pools), seg=seg,
        )  # fmt: skip

    def simulate_z(self, z: FloatArray, t_eval: FloatArray) -> Trajectories:
        """The chain over fixed `bounds`, reported at t_eval (inference, tests)."""
        n = z.shape[0]
        t_eval = np.asarray(t_eval, dtype=float)
        pieces: list[tuple[PhaseTrace, FloatArray]] = []
        prev: PhaseTrace | None = None
        for k in range(len(self.phases)):
            start = self.bounds[k]
            last = k + 1 == len(self.phases)
            end = float(max(t_eval[-1], start)) if last else self.bounds[k + 1]
            mask = (t_eval >= start) & ((t_eval <= end) if last else (t_eval < end))
            t_abs = np.unique(np.r_[start, t_eval[mask], end])
            prev = self.run_phase(k, z, t_abs, prev, None if prev is None else len(prev.t) - 1)
            pieces.append((prev, mask))
        return assemble(pieces, t_eval, n, len(self.organisms))

    def _mix(self, y_prev: FloatArray, p: EnsembleParams, ph: Phase) -> FloatArray:
        """State at the start of a phase: the carried share of the previous state plus the
        fresh ingredients (p.pools0 is their g/kg of the new mix) and any added yeast."""
        y0 = initial_state(p)
        f = ph.carry
        y0[:, :N_POOLS] += f * np.maximum(y_prev[:, :N_POOLS], 0.0)
        for j, o in enumerate(self.organisms):
            ix = N_POOLS + 2 * j
            x = f * np.exp(y_prev[:, ix])
            add = ph.x_add.get(o.name)
            if add is not None and o.cell_mass_g is not None:
                x = x + 10.0**add * o.cell_mass_g * 1000.0
            y0[:, ix] = np.log(np.maximum(x, 1e-30))
            y0[:, ix + 1] = y_prev[:, ix + 1]  # cells stay adapted through mixing
        return y0


def stack_params(ps: list[EnsembleParams]) -> EnsembleParams:
    """Concatenate single-phase ensembles that differ only in their numbers (the feeding
    chart: one solve for every ratio). Same organisms, same temperature schedule, same
    salt, no enzymes."""
    cat = np.concatenate
    p0 = ps[0]
    assert not p0.enzymes and all(np.allclose(p.acid_ka, p0.acid_ka) for p in ps)
    orgs = []
    for j, o in enumerate(p0.organisms):
        fields: dict[str, Any] = {}
        for f in dataclasses.fields(o):
            v = getattr(o, f.name)
            if f.name in ("kin", "can_grow") or v is None:
                fields[f.name] = v
            else:
                fields[f.name] = cat([getattr(p.organisms[j], f.name) for p in ps])
        orgs.append(dataclasses.replace(o, **fields))
    temp = p0.temperature
    assert isinstance(temp, TemperatureFn)
    offsets = [p.temperature.offset for p in ps]  # type: ignore[attr-defined]
    return dataclasses.replace(
        p0,
        n=sum(p.n for p in ps),
        organisms=orgs,
        pools0=cat([p.pools0 for p in ps]),
        buffer=cat([p.buffer for p in ps]),
        z_strong=cat([p.z_strong for p in ps]),
        aw=cat([p.aw for p in ps]),
        oxygen=cat([p.oxygen for p in ps]),
        temperature=TemperatureFn(temp.schedule, cat(offsets)),
        protease_ts_share=cat([p.protease_ts_share for p in ps]),
        protease_late=cat([p.protease_late for p in ps]),
        fish_peptidase_k=cat([p.fish_peptidase_k for p in ps]),
        k_flour_amylase=cat([p.k_flour_amylase for p in ps]),
        c2_acetate=cat([p.c2_acetate for p in ps]) if p0.c2_acetate is not None else None,
    )


def levain_rise(
    model: SourdoughModel, tr: Trajectories, p: EnsembleParams, z: FloatArray
) -> FloatArray:
    """Rise (N, T) of a single-phase levain run of `model` (members in `z` order)."""
    ph = model.phases[0]
    ex = model.extra_values(z)
    n = z.shape[0]
    temps = np.stack([p.temperature(float(t)) for t in tr.t_h], axis=1)
    sat0 = co2_saturation(temps[:, 0], ph.water_frac)
    seg = {
        "co2_0": tr.pools[:, 0, PI["co2"]],
        "d0": _seed_share(model.compiled) * sat0,
        "rmax": ex["rise_max"] * ph.gluten,
        "w": np.full(n, ph.water_frac),
        "v0": np.full(n, dough_litres_per_kg(ph.water_frac)),
    }
    rise, _, _, _ = _gas_balance(
        tr.t_h, temps, tr.pools[:, :, PI["co2"]] - seg["co2_0"][:, None], tr.ph, seg,
        np.zeros(n), np.maximum(seg["d0"] - sat0, 0.0), np.zeros(n), ex["leak0"],
        ex["leak_acid"],
    )  # fmt: skip
    return rise


def _seed_share(c: Compiled) -> float:
    b = c.plan.levain
    if b is None:
        return 0.0
    total = b.seed_g + b.flour_g + b.water_g
    return b.seed_g / total if c.style.seed == "starter" else 0.0


def _gas_balance(
    t: FloatArray,
    temps: FloatArray,
    produced: FloatArray,
    ph: FloatArray,
    seg: dict[str, Any],
    gas0: FloatArray,
    e0: FloatArray,
    damage0: FloatArray,
    leak0: FloatArray,
    leak_acid: FloatArray,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
    """Rise % over t (N, T) from the CO2 produced since the mix. CO2 first saturates the
    dough water; the excess inflates bubbles; bubbles leak (faster as acid exposure
    accumulates and weakens the gluten) and stop being retained as the dough nears its
    expansion limit; a cooling dough re-dissolves gas. Returns rise and the balance's
    state (gas g/kg, excess CO2 g/kg, acid damage h) at every time, so it can resume."""
    n, nt = temps.shape
    sat = co2_saturation(temps, seg["w"][:, None])
    excess = np.maximum(seg["d0"][:, None] + produced - sat, 0.0)
    litres = gas_litres_per_g(temps) / seg["v0"][:, None]
    rise = np.zeros((n, nt))
    gas_t = np.zeros((n, nt))
    damage_t = np.zeros((n, nt))
    gas, e_prev, damage = gas0.copy(), e0, damage0
    for i in range(nt):
        dt = t[i] - t[i - 1] if i else 0.0
        damage = damage + dt * np.clip((WEAK_PH - ph[:, i]) / WEAK_SPAN, 0.0, 1.0)
        k = leak0 + leak_acid * damage / (damage + DAMAGE_HALF_H)
        de = excess[:, i] - e_prev
        r = 100.0 * gas * litres[:, i]
        # a sound dough keeps nearly all its gas until close to its expansion limit
        keep = np.clip(1.0 - (r / seg["rmax"]) ** 3, 0.0, 1.0)
        gas = gas * np.exp(-k * dt) + np.where(de >= 0.0, de * keep, de)
        gas = np.maximum(gas, 0.0)
        e_prev = excess[:, i]
        rise[:, i] = 100.0 * gas * litres[:, i]
        gas_t[:, i] = gas
        damage_t[:, i] = damage
    return rise, gas_t, excess, damage_t


def tta(pools: FloatArray, p: EnsembleParams) -> FloatArray:
    """Total titratable acidity, mL 0.1 N NaOH per 10 g to pH 8.5, (N, T): the base that
    moves the charge balance from the current state to the end point."""
    n, nt, _ = pools.shape
    h_end = np.full(n, 10.0**-TTA_END_PH)
    out = np.zeros((n, nt))
    for i in range(nt):
        f, _ = charge_residual(h_end, acid_moles(pools[:, i]), p.buffer, p.z_strong, p.acid_ka)
        out[:, i] = -100.0 * f
    return out


def fermentation_quotient(pools: FloatArray) -> FloatArray:
    """Molar lactic:acetic ratio (the baker's FQ), capped at 50 while acetate is ~absent."""
    lac = pools[:, :, PI["lactic_acid"]] / 90.08
    ace = pools[:, :, PI["acetic_acid"]] / 60.05
    return np.asarray(np.minimum(lac / np.maximum(ace, 1e-4), 50.0))
