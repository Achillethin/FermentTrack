"""Compile one batch's context into a sampled kinetic ensemble.

ModelSpec is the static description (which organisms, starting composition, temperature
schedule, which priors apply). `spec.params(z)` maps an (N, D) matrix of standard-normal
draws to engine parameters, so inference can move members around in z-space while the
prior stays N(0, I).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from fermenttrack.prediction.engine import (
    N_POOLS,
    PI,
    EnsembleParams,
    OrganismParams,
    acid_ka,
    acid_moles,
    buffer_groups,
    strong_ion_offset,
    water_activity,
)
from fermenttrack.prediction.organisms import OrganismKinetics
from fermenttrack.prediction.priors import FloatArray, Prior
from fermenttrack.prediction.profiles import FermentProfile

# Enzyme priors, first order in substrate (1/h per unit of koji enzyme, at 50 °C). Koji
# enzyme activity is on a 0-1 "fully grown koji" scale. Calibrated to: amazake (koji +
# rice, 55-60 °C) breaks down up to ~60 % of the rice in 6-10 h (Oguro et al. 2019;
# Akamatsu et al. 2024); miso koji enzymes do most of their work in ~5 months at 25-30 °C
# (Allwood et al. 2021); koji garum runs 10-12 weeks at 60 °C. All est.
KOJI_AMYLASE = Prior(0.12, 0.05, 0.3)
KOJI_PROTEASE = Prior(4e-3, 1.5e-3, 1.2e-2)
ENZYME_DECAY_25C = Prior(3e-4, 1e-4, 1e-3)  # 1/h (half-life ~3 months at 25 °C)
TEMP_OFFSET = Prior(0.0, -1.5, 1.5, "lin")  # °C, error of an estimated temperature
SUGAR_SCALE = Prior(1.0, 0.85, 1.15)  # real produce vs its USDA reference sugars


@dataclass(frozen=True)
class ParamSpec:
    name: str
    prior: Prior
    organism: int | None = None  # index into ModelSpec.organisms


@dataclass
class TemperatureSchedule:
    """Piecewise-linear °C over batch hours; `estimated` marks spans not backed by readings."""

    t_h: list[float]
    temp_c: list[float]
    estimated: list[float]  # 1.0 = user/type estimate (gets the offset), 0.0 = measured

    def __post_init__(self) -> None:
        if not (len(self.t_h) == len(self.temp_c) == len(self.estimated) >= 1):
            raise ValueError("temperature schedule needs matching, non-empty knots")


@dataclass
class ModelSpec:
    profile: FermentProfile
    organisms: list[OrganismKinetics]
    can_grow: list[bool]
    inoculum: list[Prior]  # log10 CFU/g (cells) or g/kg (mold) per organism
    pools0: dict[str, float]  # g/kg at t=0, before the sugar-scale draw
    salt_water_phase_pct: float
    schedule: TemperatureSchedule
    specs: list[ParamSpec] = field(init=False)

    def __post_init__(self) -> None:
        p = self.profile
        specs = [
            ParamSpec("ph0", p.ph0),
            ParamSpec("buffer_mm", p.buffer_mm),
            ParamSpec("temp_offset", TEMP_OFFSET),
            ParamSpec("sugar_scale", SUGAR_SCALE),
        ]
        if any(o.obligate_aerobe for o, g in zip(self.organisms, self.can_grow, strict=True) if g):
            specs.append(ParamSpec("oxygen", p.oxygen_factor))
        has_koji = any(o.makes_enzymes for o in self.organisms)
        if has_koji:
            specs += [
                ParamSpec("k_koji_amylase", KOJI_AMYLASE),
                ParamSpec("k_koji_protease", KOJI_PROTEASE),
            ]
            if p.koji_enzyme0 is not None:
                specs.append(ParamSpec("koji_enzyme0", p.koji_enzyme0))
        if has_koji or p.fish_protease is not None:
            specs.append(ParamSpec("enzyme_decay", ENZYME_DECAY_25C))
        if p.flour_amylase is not None:
            specs.append(ParamSpec("k_flour_amylase", p.flour_amylase))
        if p.fish_protease is not None:
            specs.append(ParamSpec("k_fish_protease", p.fish_protease))
        for j, o in enumerate(self.organisms):
            overrides = {"x_max": p.x_max_override.get(o.name, o.x_max)}
            for name in (
                "mu_max", "ks", "yield_xs", "maint", "t_min", "t_opt", "t_max", "ph_min",
                "ph_opt", "ph_max", "mic_lactic_mm", "mic_acetic_mm", "aw_min", "ethanol_max",
                "x_max", "h0", "k_death",
            ):  # fmt: skip
                specs.append(ParamSpec(name, overrides.get(name, getattr(o, name)), j))
            specs.append(ParamSpec("x0", self.inoculum[j], j))
            if o.inverts_sucrose is not None:
                specs.append(ParamSpec("invertase", o.inverts_sucrose, j))
        self.specs = specs

    @property
    def dim(self) -> int:
        return len(self.specs)

    def _values(self, z: FloatArray) -> tuple[dict[str, FloatArray], list[dict[str, FloatArray]]]:
        glob: dict[str, FloatArray] = {}
        orgs: list[dict[str, FloatArray]] = [{} for _ in self.organisms]
        for col, s in enumerate(self.specs):
            v = s.prior.value(z[:, col])
            if s.organism is None:
                glob[s.name] = v
            else:
                orgs[s.organism][s.name] = v
        return glob, orgs

    def temperature(self, offset: FloatArray) -> TemperatureFn:
        return TemperatureFn(self.schedule, offset)

    def params(self, z: FloatArray) -> EnsembleParams:
        n = z.shape[0]
        glob, orgs = self._values(z)
        wps = self.salt_water_phase_pct

        pools0 = np.zeros((n, N_POOLS))
        for k, conc in self.pools0.items():
            pools0[:, PI[k]] = conc
        for k in ("sucrose", "hexoses", "lactose", "maltose"):
            pools0[:, PI[k]] *= glob["sugar_scale"]
        pools0[:, PI["koji_enzyme"]] = glob.get("koji_enzyme0", np.zeros(n))

        buf = buffer_groups(glob["buffer_mm"])
        ka = acid_ka(ionic_strength(wps))
        # Z is set by the matrix alone; acids present at t=0 (starter carry-over) then
        # lower the starting pH below the matrix's own.
        z_strong = strong_ion_offset(glob["ph0"], np.zeros_like(acid_moles(pools0)), buf, ka)

        org_params = []
        for j, o in enumerate(self.organisms):
            v: dict[str, FloatArray] = orgs[j]
            t_min = v["t_min"]
            t_opt = np.maximum(v["t_opt"], t_min + 3.0)
            t_max = np.maximum(v["t_max"], t_opt + 2.0)
            ph_min = v["ph_min"]
            ph_opt = np.maximum(v["ph_opt"], ph_min + 0.5)
            ph_max = np.maximum(v["ph_max"], ph_opt + 0.5)
            if o.is_mold:
                x_max = v["x_max"]  # g/kg
                x0 = v["x0"]
            else:
                assert o.cell_mass_g is not None
                x_max = 10.0 ** v["x_max"] * o.cell_mass_g * 1000.0
                x0 = 10.0 ** v["x0"] * o.cell_mass_g * 1000.0
            x0 = np.minimum(x0, 0.5 * x_max)
            h0 = v["h0"] * self.profile.h0_factor
            ln_q0 = -np.log(np.expm1(np.maximum(h0, 1e-6)))
            org_params.append(
                OrganismParams(
                    kin=o,
                    can_grow=self.can_grow[j],
                    mu_max=v["mu_max"],
                    ks=v["ks"],
                    yield_xs=v["yield_xs"],
                    maint=v["maint"],
                    t_min=t_min,
                    t_opt=t_opt,
                    t_max=t_max,
                    ph_min=ph_min,
                    ph_opt=ph_opt,
                    ph_max=ph_max,
                    mic_lactic_mm=v["mic_lactic_mm"],
                    mic_acetic_mm=v["mic_acetic_mm"],
                    aw_min=v["aw_min"],
                    ethanol_max=v["ethanol_max"],
                    x_max_g=x_max,
                    k_death=v["k_death"],
                    x0_g=x0,
                    ln_q0=ln_q0,
                    invertase=v.get("invertase"),
                )
            )

        zeros = np.zeros(n)
        aw = np.full(n, float(water_activity(np.array([wps]))[0]))
        return EnsembleParams(
            n=n,
            organisms=org_params,
            pools0=pools0,
            buffer=buf,
            z_strong=z_strong,
            acid_ka=ka,
            aw=aw,
            oxygen=glob.get("oxygen", zeros),
            temperature=self.temperature(glob["temp_offset"]),
            k_koji_amylase=glob.get("k_koji_amylase", zeros),
            k_koji_protease=glob.get("k_koji_protease", zeros),
            k_flour_amylase=glob.get("k_flour_amylase", zeros),
            k_fish_protease=glob.get("k_fish_protease", zeros),
            k_enzyme_decay25=glob.get("enzyme_decay", zeros),
            # ponytail: one coarse linear salt factor for all enzymes; A. oryzae proteases
            # keep ~30-60 % of their activity at 12-18 % NaCl (Ito & Matsuyama 2021, est.).
            enzyme_salt=np.full(n, max(0.2, 1.0 - wps / 30.0)),
            enzyme_access=self.profile.enzyme_access,
        )


@dataclass
class TemperatureFn:
    schedule: TemperatureSchedule
    offset: FloatArray

    def __call__(self, t: float) -> FloatArray:
        s = self.schedule
        base = float(np.interp(t, s.t_h, s.temp_c))
        est = float(np.interp(t, s.t_h, s.estimated))
        return np.asarray(base + self.offset * est)


def ionic_strength(salt_water_phase_pct: float) -> float:
    """mol/kg water: NaCl dominates the ionic strength of salted ferments (I = molality)."""
    w = min(max(salt_water_phase_pct, 0.0), 26.4) / 100.0
    return w / (0.05844 * (1.0 - w))


def log_q0(h0: float) -> float:
    """Baranyi-Roberts ln q0 from h0 = mu_max * lag (exposed for tests/docs)."""
    return -math.log(math.expm1(h0))
