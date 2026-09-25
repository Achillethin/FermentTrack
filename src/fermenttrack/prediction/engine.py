"""Vectorised ensemble kinetic model of a fermentation.

Every ensemble member is one plausible parameter set; all members are integrated at once
as one stacked ODE system (numpy only, one adaptive Runge-Kutta solve), so a 200-member
forecast costs about as much as a few dozen single ones.

State per member: chemical pools in g/kg (POOLS), then for each organism ln(biomass) and
the Baranyi-Roberts lag variable ln(q). Rates:

    mu_j   = mu_max_j * g_T * g_pH * g_HA * g_aw * g_EtOH * g_O2 * f_sub * alpha(q) * (1 - X/Xmax)
    v_j    = mu_j * X / Y_j + m_j * (same environment factors) * f_sub * alpha(q) * X
    dlnX/dt = mu_j - k_death * [(1 - stress) + 0.5 (1 - f_sub)] - k_heat * (T - Tmax)+
                                                        (stress = g_pH * g_HA * g_aw * g_EtOH)
    dlnq/dt = mu_max_j * g_T * stress                  (Baranyi & Roberts 1994)

v_j (substrate flux, Luedeking-Piret-style growth + non-growth terms) is split across the
organism's channels and converted to products at fixed mass yields. Koji mold also makes
amylase, protease and peptidase activity (more protease when grown cool, more amylase
warm); fish and flour bring their own enzymes. Each enzyme class has its own Arrhenius
catalysis, heat/slow inactivation and salt response (prediction/enzymes.py), and protein
breaks down in two steps: protein -> soluble peptides -> free amino acids.

pH is not a state: it is solved from the charge balance of the organic acids against the
matrix buffer (a ladder of weak-acid groups sized to the matrix buffer capacity).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp  # type: ignore[import-untyped]

from fermenttrack.prediction.enzymes import (
    AMYLASE_PRODUCTION_T,
    GLUCOSE_SHARE,
    PROTEASE_PRODUCTION_T,
    R_GAS,
    SOLUBLE_CEILING,
    T_REF_K,
)
from fermenttrack.prediction.organisms import OrganismKinetics
from fermenttrack.prediction.priors import FloatArray

POOLS: tuple[str, ...] = (
    "sucrose",
    "hexoses",
    "lactose",
    "maltose",
    "starch",
    "protein",
    "amino_acids",
    "ethanol",
    "lactic_acid",
    "acetic_acid",
    "gluconic_acid",
    "co2",
    "peptides",  # soluble, not yet free amino acids
    # enzyme activities: 1 = a fully grown koji (fish_enzyme: 1 = fresh whole fish)
    "amylase",
    "protease",
    "protease_ts",  # thermostable share of the koji protease (does not heat-denature)
    "peptidase",
    "fish_enzyme",
)
PI = {k: i for i, k in enumerate(POOLS)}
N_POOLS = len(POOLS)

DISACCHARIDE_TO_HEXOSE = 360.31 / 342.30  # g hexose per g sucrose/maltose/lactose hydrolysed
STARCH_TO_GLUCOSE = 180.16 / 162.14
STARCH_TO_MALTOSE = 342.30 / 324.28
# g hexose equivalent per g of each substrate a channel can consume
HEXOSE_PER_G = {
    "sucrose": DISACCHARIDE_TO_HEXOSE,
    "maltose": DISACCHARIDE_TO_HEXOSE,
    "lactose": DISACCHARIDE_TO_HEXOSE,
    "starch": STARCH_TO_GLUCOSE,
}

# Organic acids: molar mass (g/mol), pKa at ~25 °C.
ACIDS: tuple[tuple[str, float, float], ...] = (
    ("lactic_acid", 90.08, 3.86),
    ("acetic_acid", 60.05, 4.76),
    ("gluconic_acid", 196.16, 3.70),
)
_ACID_IDX = np.array([PI[a] for a, _, _ in ACIDS])
_ACID_MW = np.array([mw for _, mw, _ in ACIDS])
_ACID_KA = np.array([10.0**-pka for _, _, pka in ACIDS])
KW = 1e-14

# Matrix buffer: equal amounts of weak-acid groups at these pKa values. Their summed
# buffer capacity is nearly flat between pH 4 and 7, like food matrices (proteins,
# phosphates, organic acid salts).
BUFFER_PKA = np.array([3.5, 4.5, 5.5, 6.5, 7.5])
_BUFFER_KA = 10.0**-BUFFER_PKA
# beta(pH 5) per mol/kg of each group: 2.303 * sum(alpha * (1 - alpha)).
_A5 = _BUFFER_KA / (_BUFFER_KA + 1e-5)
BUFFER_BETA_PER_MOL = float(2.303 * np.sum(_A5 * (1 - _A5)))

INVERTASE_KM = 10.0  # g/kg sucrose (25-30 mM)
FLOUR_AMYLASE_EA = 45.0e3  # J/mol, cereal amylases (as koji amylase; est.)
# Acid production outlasts growth: cells keep fermenting a little below the pH / acid
# levels that stop division (L. sanfranciscensis: growth stops at pH 4.0, acid production
# at ~3.8, Brandt et al. 2004; Luedeking-Piret beta term, Passos et al. 1994).
PRODUCTION_PH_MARGIN = 0.3
PRODUCTION_MIC_FACTOR = 2.5
# Above an organism's maximum growth temperature cells die: ~0.1 ln-units per hour per °C
# over Tmax (est.; e.g. salt-loving LAB in 60 °C koji garum are gone within hours).
K_HEAT = 0.1


class SimulationError(RuntimeError):
    """The ensemble could not be integrated within budget (failure or runaway stiffness)."""


def ctmi(t: FloatArray, t_min: FloatArray, t_opt: FloatArray, t_max: FloatArray) -> FloatArray:
    """Rosso et al. (1993) cardinal temperature model with inflection, in [0, 1]."""
    num = (t - t_max) * (t - t_min) ** 2
    den = (t_opt - t_min) * (
        (t_opt - t_min) * (t - t_opt) - (t_opt - t_max) * (t_opt + t_min - 2 * t)
    )
    with np.errstate(divide="ignore", invalid="ignore"):
        g = np.where((t > t_min) & (t < t_max), num / den, 0.0)
    return np.asarray(np.clip(np.nan_to_num(g), 0.0, 1.0))


def cpm(x: FloatArray, x_min: FloatArray, x_opt: FloatArray, x_max: FloatArray) -> FloatArray:
    """Rosso et al. (1995) cardinal model (pH, water activity), in [0, 1]."""
    a = (x - x_min) * (x - x_max)
    with np.errstate(divide="ignore", invalid="ignore"):
        g = np.where((x > x_min) & (x < x_max), a / (a - (x - x_opt) ** 2), 0.0)
    return np.asarray(np.clip(np.nan_to_num(g), 0.0, 1.0))


def water_activity(salt_water_phase_pct: FloatArray) -> FloatArray:
    """aw of an NaCl brine from its salt % (w/w): ln aw = -2 m phi M_w, phi(m) ~ NaCl data.

    Matches tabulated values within ~0.01 up to saturation (10 % -> 0.94, 20 % -> 0.85,
    26 % -> 0.76). Sugars and other solutes are ignored.
    """
    w = np.clip(salt_water_phase_pct, 0.0, 26.4) / 100.0
    m = w / (0.05844 * (1.0 - w))  # mol NaCl / kg water
    phi = np.maximum(0.93, 0.87 + 0.067 * m)  # NaCl osmotic coefficient (Robinson & Stokes)
    return np.asarray(np.exp(-2.0 * m * phi * 0.018015))


def buffer_groups(beta_mm: FloatArray) -> FloatArray:
    """mol/kg of each buffer group giving a buffer capacity of beta mmol/kg/pH at pH 5."""
    return np.asarray(beta_mm / 1000.0 / BUFFER_BETA_PER_MOL)


def acid_ka(ionic_strength: float) -> FloatArray:
    """Mixed acidity constants Ka' = a(H+)[A-]/[HA] at this ionic strength, so the solved h is
    the H+ activity a pH meter reads: pKa' = pKa - 0.51 f(I) (Davies for the anion). Capped
    at I = 0.5, past which Davies is unreliable (high-salt ferments keep that shift)."""
    i = min(max(ionic_strength, 0.0), 0.5)
    shift = 0.51 * (math.sqrt(i) / (1.0 + math.sqrt(i)) - 0.3 * i)
    return np.asarray(_ACID_KA * 10.0**shift)


def acid_moles(pools: FloatArray) -> FloatArray:
    """(N, 3) mol/kg of lactic, acetic, gluconic acid."""
    return np.asarray(np.maximum(pools[:, _ACID_IDX], 0.0) / _ACID_MW)


def charge_residual(
    h: FloatArray, acids: FloatArray, buf: FloatArray, z: FloatArray, ka: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Charge balance F(h) = h + Z - Kw/h - sum(acid anions) - sum(buffer anions), dF/dln h."""
    hh = h[:, None]
    a_den = ka + hh
    b_den = _BUFFER_KA + hh
    f = (
        h
        + z
        - KW / h
        - np.sum(acids * ka / a_den, axis=1)
        - buf * np.sum(_BUFFER_KA / b_den, axis=1)
    )
    dfdh = (
        1.0
        + KW / h**2
        + np.sum(acids * ka / a_den**2, axis=1)
        + buf * np.sum(_BUFFER_KA / b_den**2, axis=1)
    )
    return np.asarray(f), np.asarray(dfdh * h)


def strong_ion_offset(
    ph0: FloatArray, acids: FloatArray, buf: FloatArray, ka: FloatArray
) -> FloatArray:
    """Net strong-ion charge Z that makes the charge balance hold at pH ph0."""
    h = 10.0**-ph0
    f, _ = charge_residual(h, acids, buf, np.zeros_like(h), ka)
    return np.asarray(-f)


def solve_h(
    acids: FloatArray, buf: FloatArray, z: FloatArray, ka: FloatArray, h_guess: FloatArray
) -> FloatArray:
    """[H+] from the charge balance: Newton on ln h (F is increasing in h), bisection fallback."""
    x = np.log(np.clip(h_guess, 1e-10, 1e-1))
    for _ in range(8):
        f, dfdx = charge_residual(np.exp(x), acids, buf, z, ka)
        step = np.clip(f / dfdx, -2.3, 2.3)
        x = x - step
        if np.max(np.abs(step)) < 1e-7:
            return np.asarray(np.exp(x))
    f, _ = charge_residual(np.exp(x), acids, buf, z, ka)
    bad = np.abs(f) > 1e-9 * (1.0 + np.abs(z))
    if np.any(bad):
        lo = np.full(int(bad.sum()), math.log(1e-10))
        hi = np.full(int(bad.sum()), math.log(1e-1))
        for _ in range(50):
            mid = 0.5 * (lo + hi)
            fm, _ = charge_residual(np.exp(mid), acids[bad], buf[bad], z[bad], ka)
            hi = np.where(fm > 0, mid, hi)
            lo = np.where(fm > 0, lo, mid)
        x[bad] = 0.5 * (lo + hi)
    return np.asarray(np.exp(x))


def arrhenius(temp_c: FloatArray, ea_j: FloatArray | float) -> FloatArray:
    """Catalysis rate relative to 50 °C."""
    return np.asarray(np.exp(-ea_j / R_GAS * (1.0 / (temp_c + 273.15) - 1.0 / T_REF_K)))


@dataclass
class EnzymeParams:
    """Per-member (N,) parameters of one enzyme class (see prediction/enzymes.py)."""

    k: FloatArray  # 1/h per unit activity at 50 °C, salt and access already applied
    ea: FloatArray  # J/mol, catalysis
    kd_ref: FloatArray  # 1/h heat denaturation at t_ref_k
    t_ref_k: float
    ed: FloatArray  # J/mol, denaturation
    floor: FloatArray  # 1/h slow loss at 25 °C (Q10 2)

    def inactivation(self, temp_c: FloatArray) -> FloatArray:
        tk = temp_c + 273.15
        arg = np.minimum(self.ed / R_GAS * (1.0 / self.t_ref_k - 1.0 / tk), 30.0)
        heat = self.kd_ref * np.exp(arg)
        return np.asarray(heat + self.floor * 2.0 ** ((temp_c - 25.0) / 10.0))


@dataclass
class OrganismParams:
    """Per-member (N,) parameter arrays for one organism."""

    kin: OrganismKinetics
    can_grow: bool  # False: obligate aerobe in a closed ferment (stays at its inoculum)
    mu_max: FloatArray
    ks: FloatArray
    yield_xs: FloatArray
    maint: FloatArray
    t_min: FloatArray
    t_opt: FloatArray
    t_max: FloatArray
    ph_min: FloatArray
    ph_opt: FloatArray
    ph_max: FloatArray
    mic_lactic_mm: FloatArray
    mic_acetic_mm: FloatArray
    aw_min: FloatArray
    ethanol_max: FloatArray
    x_max_g: FloatArray  # g/kg
    k_death: FloatArray
    x0_g: FloatArray  # g/kg at t=0
    ln_q0: FloatArray
    invertase: FloatArray | None  # g sucrose / g biomass / h


@dataclass
class EnsembleParams:
    """Everything one simulation needs, vectorised over N members."""

    n: int
    organisms: list[OrganismParams]
    pools0: FloatArray  # (N, N_POOLS)
    buffer: FloatArray  # (N,) mol/kg of each buffer group
    z_strong: FloatArray  # (N,)
    acid_ka: FloatArray  # (3,) apparent Ka of lactic, acetic, gluconic at the batch's salt
    aw: FloatArray  # (N,)
    oxygen: FloatArray  # (N,) aerobic capacity for obligate aerobes (0 = closed ferment)
    temperature: Callable[[float], FloatArray]  # t_h -> (N,) °C
    # Hydrolysis is first order in substrate: rate = k * E * A(T) * salt * access * S, per
    # enzyme class present (keys: "amylase", "protease", "peptidase", "fish_enzyme").
    enzymes: dict[str, EnzymeParams]
    protease_ts_share: FloatArray  # of koji protease made/present, the thermostable part
    protease_late: FloatArray  # 1/h protease made per unit grown mycelium after growth
    fish_peptidase_k: FloatArray  # 1/h per unit fish enzyme at 50 °C (salt, access applied)
    k_flour_amylase: FloatArray  # 1/h at 50 °C, cereal enzymes (no koji needed)


@dataclass
class Trajectories:
    t_h: FloatArray  # (T,)
    pools: FloatArray  # (N, T, N_POOLS)
    biomass_g: FloatArray  # (N, T, M) g/kg
    ph: FloatArray  # (N, T)


def _state_size(n_org: int) -> int:
    return N_POOLS + 2 * n_org


def initial_state(p: EnsembleParams) -> FloatArray:
    y0 = np.zeros((p.n, _state_size(len(p.organisms))))
    y0[:, :N_POOLS] = p.pools0
    for j, o in enumerate(p.organisms):
        y0[:, N_POOLS + 2 * j] = np.log(o.x0_g)
        y0[:, N_POOLS + 2 * j + 1] = o.ln_q0
    return y0


def make_rhs(
    p: EnsembleParams, max_evals: int | None = None
) -> Callable[[float, FloatArray], FloatArray]:
    n, m = p.n, len(p.organisms)
    evals = [0]
    size = _state_size(m)
    h_cache = [10.0 ** -np.full(n, 6.0)]
    ln_x_cap = [np.log(o.x_max_g) + 0.5 for o in p.organisms]
    protein_floor = (1.0 - SOLUBLE_CEILING) * p.pools0[:, PI["protein"]]
    enz = p.enzymes
    amy_t = [np.full(n, v) for v in AMYLASE_PRODUCTION_T]
    pro_t = [np.full(n, v) for v in PROTEASE_PRODUCTION_T]

    def rhs(t: float, y_flat: FloatArray) -> FloatArray:
        evals[0] += 1
        if max_evals is not None and evals[0] > max_evals:
            raise SimulationError(f"exceeded {max_evals} right-hand-side evaluations")
        y = y_flat.reshape(n, size)
        pools = np.maximum(y[:, :N_POOLS], 0.0)
        dy = np.zeros_like(y)
        dp = dy[:, :N_POOLS]
        temp = p.temperature(t)

        acids = acid_moles(pools)
        h = solve_h(acids, p.buffer, p.z_strong, p.acid_ka, h_cache[0])
        h_cache[0] = h
        ph = -np.log10(h)
        undiss = acids * (h[:, None] / (h[:, None] + p.acid_ka)) * 1000.0  # mmol/kg
        ethanol = pools[:, PI["ethanol"]]

        for j, o in enumerate(p.organisms):
            ln_x = np.minimum(y[:, N_POOLS + 2 * j], ln_x_cap[j])
            x = np.exp(ln_x)
            ln_q = y[:, N_POOLS + 2 * j + 1]
            g_t = ctmi(temp, o.t_min, o.t_opt, o.t_max)
            g_ph = cpm(ph, o.ph_min, o.ph_opt, o.ph_max)
            g_ha = np.clip(1.0 - undiss[:, 0] / o.mic_lactic_mm, 0.0, 1.0) * np.clip(
                1.0 - undiss[:, 1] / o.mic_acetic_mm, 0.0, 1.0
            )
            if o.kin.aw_opt < 0.99:  # halophile: optimum below aw 1, cardinal model
                aw_opt = np.full(n, o.kin.aw_opt)
                g_aw = cpm(p.aw, o.aw_min, aw_opt, 2.0 - aw_opt + 0.05)
            else:  # gamma concept (Zwietering et al. 1992)
                g_aw = np.clip((p.aw - o.aw_min) / (1.0 - o.aw_min), 0.0, 1.0)
            g_e = np.clip(1.0 - ethanol / o.ethanol_max, 0.0, 1.0)
            stress = g_ph * g_ha * g_aw * g_e
            g_o2 = p.oxygen if o.kin.obligate_aerobe else 1.0
            env = g_t * stress * g_o2
            g_ph_prod = cpm(ph, o.ph_min - PRODUCTION_PH_MARGIN, o.ph_opt, o.ph_max)
            g_ha_prod = np.clip(
                1.0 - undiss[:, 0] / (PRODUCTION_MIC_FACTOR * o.mic_lactic_mm), 0.0, 1.0
            ) * np.clip(1.0 - undiss[:, 1] / (PRODUCTION_MIC_FACTOR * o.mic_acetic_mm), 0.0, 1.0)
            env_prod = g_t * g_ph_prod * g_ha_prod * g_aw * g_e * g_o2

            # substrate saturation per channel
            sats = []
            for ch in o.kin.channels:
                s = sum(pools[:, PI[k]] for k in ch.substrates)
                sats.append(ch.weight * s / (o.ks + s))
            sat_sum = np.asarray(sum(sats))
            f_sub = np.minimum(sat_sum, 1.0)
            alpha = 1.0 / (1.0 + np.exp(-np.clip(ln_q, -50.0, 50.0)))

            if o.can_grow:
                mu = np.maximum(o.mu_max * env * f_sub * alpha * (1.0 - x / o.x_max_g), 0.0)
                growth = mu * x
                # g substrate/kg/h: growth-linked + non-growth (Pirt / Luedeking-Piret)
                flux = growth / o.yield_xs + o.maint * env_prod * f_sub * alpha * x
            else:
                mu = growth = flux = np.zeros(n)

            death = o.k_death * ((1.0 - stress) + 0.5 * (1.0 - f_sub)) + K_HEAT * np.maximum(
                temp - o.t_max, 0.0
            )
            dy[:, N_POOLS + 2 * j] = mu - death
            dy[:, N_POOLS + 2 * j + 1] = np.where(ln_q < 30.0, o.mu_max * g_t * stress, 0.0)

            with np.errstate(divide="ignore", invalid="ignore"):
                for ch, s_ch in zip(o.kin.channels, sats, strict=True):
                    share = np.where(sat_sum > 0, s_ch / sat_sum, 0.0)
                    v = flux * share
                    total = sum(pools[:, PI[k]] for k in ch.substrates)
                    for k in ch.substrates:
                        frac = np.where(total > 0, pools[:, PI[k]] / total, 0.0)
                        conv = HEXOSE_PER_G.get(k, 1.0)
                        dp[:, PI[k]] -= v * frac / conv
                    for prod, yld in ch.products.items():
                        dp[:, PI[prod]] += v * yld

            if o.invertase is not None:
                suc = pools[:, PI["sucrose"]]
                inv = o.invertase * x * g_t * suc / (INVERTASE_KM + suc)
                dp[:, PI["sucrose"]] -= inv
                dp[:, PI["hexoses"]] += inv * DISACCHARIDE_TO_HEXOSE

            if o.kin.makes_enzymes and o.can_grow and "amylase" in enz:
                # Luedeking-Piret enzyme production, shifted by bed temperature: amylase
                # favoured warm, protease/peptidase cool (enzymes.py)
                grown = growth / o.x_max_g
                g_pro = ctmi(temp, *pro_t)
                pro = (grown + p.protease_late * x / o.x_max_g) * g_pro
                dp[:, PI["amylase"]] += grown * ctmi(temp, *amy_t)
                dp[:, PI["protease"]] += pro * (1.0 - p.protease_ts_share)
                dp[:, PI["protease_ts"]] += pro * p.protease_ts_share
                dp[:, PI["peptidase"]] += grown * g_pro

        # enzymatic hydrolysis: starch -> sugars; protein -> peptides -> free amino acids
        starch = pools[:, PI["starch"]]
        peptides = pools[:, PI["peptides"]]
        hydrolysable = np.maximum(pools[:, PI["protein"]] - protein_floor, 0.0)
        r_flour_st = p.k_flour_amylase * arrhenius(temp, FLOUR_AMYLASE_EA) * starch
        r_koji_st = np.zeros(n)
        r_pro = np.zeros(n)
        r_pep = np.zeros(n)
        if "amylase" in enz:
            e, a = enz["amylase"], pools[:, PI["amylase"]]
            r_koji_st = e.k * a * arrhenius(temp, e.ea) * starch
            dp[:, PI["amylase"]] -= e.inactivation(temp) * a
        if "protease" in enz:
            e, a, a_ts = enz["protease"], pools[:, PI["protease"]], pools[:, PI["protease_ts"]]
            r_pro += e.k * (a + a_ts) * arrhenius(temp, e.ea) * hydrolysable
            dp[:, PI["protease"]] -= e.inactivation(temp) * a
            dp[:, PI["protease_ts"]] -= e.floor * 2.0 ** ((temp - 25.0) / 10.0) * a_ts
        if "peptidase" in enz:
            e, a = enz["peptidase"], pools[:, PI["peptidase"]]
            r_pep += e.k * a * arrhenius(temp, e.ea) * peptides
            dp[:, PI["peptidase"]] -= e.inactivation(temp) * a
        if "fish_enzyme" in enz:
            e, a = enz["fish_enzyme"], pools[:, PI["fish_enzyme"]]
            act = a * arrhenius(temp, e.ea)
            r_pro += e.k * act * hydrolysable
            r_pep += p.fish_peptidase_k * act * peptides
            dp[:, PI["fish_enzyme"]] -= e.inactivation(temp) * a
        dp[:, PI["starch"]] -= r_koji_st + r_flour_st
        dp[:, PI["hexoses"]] += r_koji_st * GLUCOSE_SHARE * STARCH_TO_GLUCOSE
        dp[:, PI["maltose"]] += (
            r_koji_st * (1 - GLUCOSE_SHARE) + r_flour_st
        ) * STARCH_TO_MALTOSE
        dp[:, PI["protein"]] -= r_pro
        dp[:, PI["peptides"]] += r_pro - r_pep
        dp[:, PI["amino_acids"]] += r_pep

        # never drain a pool below zero (fluxes use clipped pools, but solver stages can
        # overshoot slightly on the way to exhaustion)
        drain = (y[:, :N_POOLS] <= 0.0) & (dp < 0.0)
        dp[drain] = 0.0
        return np.asarray(dy.reshape(-1))

    return rhs


# The step size follows the stiffest member; a budget bounds a request's CPU time (typical
# forecasts need 100-1500 evaluations).
MAX_EVALS = 4000


def simulate(
    p: EnsembleParams, t_eval: FloatArray, max_evals: int | None = MAX_EVALS
) -> Trajectories:
    """Integrate all members over t_eval (hours, increasing, starting at 0)."""
    y0 = initial_state(p)
    rhs = make_rhs(p, max_evals)
    # Pools to 1e-3 g/kg, log-states (ln X, ln q) to 1 %: finer than any reported digit.
    atol = np.tile(
        np.r_[np.full(N_POOLS, 1e-3), np.full(2 * len(p.organisms), 1e-2)], p.n
    )
    sol = solve_ivp(
        rhs,
        (0.0, float(t_eval[-1])),
        y0.reshape(-1),
        method="RK23",
        t_eval=t_eval,
        rtol=5e-3,
        atol=atol,
    )
    if not sol.success:
        raise SimulationError(f"kinetic model integration failed: {sol.message}")
    m = len(p.organisms)
    ys = sol.y.reshape(p.n, _state_size(m), -1).transpose(0, 2, 1)  # (N, T, S)
    pools = np.maximum(ys[:, :, :N_POOLS], 0.0)
    biomass = np.exp(np.stack([ys[:, :, N_POOLS + 2 * j] for j in range(m)], axis=2)) if m else (
        np.zeros((p.n, len(t_eval), 0))
    )
    ph = np.empty((p.n, len(t_eval)))
    h = 10.0 ** -np.full(p.n, 6.0)
    for i in range(len(t_eval)):
        h = solve_h(acid_moles(pools[:, i, :]), p.buffer, p.z_strong, p.acid_ka, h)
        ph[:, i] = -np.log10(h)
    return Trajectories(t_h=np.asarray(t_eval, dtype=float), pools=pools, biomass_g=biomass, ph=ph)
