"""Condition the prior ensemble on a batch's own measurements.

Adaptive multiple importance sampling (AMIS; Cornuet et al. 2012) in the standard-normal
z-space of the priors: draw from the prior, weight each member by how well it explains
the logged pH / gravity / Brix readings, fit a Gaussian to the weighted members, draw a
new batch from it, and re-weight ALL members against the mixture of every proposal used
so far (deterministic-mixture weights keep the estimate unbiased). A few rounds of this
concentrate the ensemble on parameter sets consistent with the batch, while the prior
keeps unconstrained parameters at their literature spread.

Observation errors are Student-t (heavy tails: one mis-typed reading must not collapse
the ensemble). If even the best members explain the data poorly, the likelihood is
tempered until at least MIN_ESS members carry weight, and the result says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from fermenttrack.prediction.engine import PI, Trajectories, simulate
from fermenttrack.prediction.model import ModelSpec
from fermenttrack.prediction.priors import FloatArray

NU = 4.0  # Student-t degrees of freedom
# key -> (measurement sd, model discrepancy sd); combined in quadrature.
OBS_SIGMA: dict[str, tuple[float, float]] = {
    "ph": (0.15, 0.15),
    "gravity": (0.002, 0.003),
    "brix": (0.3, 0.8),
}
MIN_ESS = 15.0
TARGET_ESS_FRACTION = 0.3
MAX_ROUNDS = 3


@dataclass(frozen=True)
class Observation:
    key: str  # "ph" | "gravity" | "brix"
    t_h: float
    value: float


def plato_to_sg(plato: float) -> float:
    """ASBC approximation: SG from degrees Plato (for iSpindels configured in °P)."""
    return 1.0 + plato / (258.6 - (plato / 258.2) * 227.1)


# Density increments at 20 °C, g/L of solution per g/L of solute (CRC density tables:
# sucrose 0.384, glucose 0.380, fructose 0.387; ethanol -0.18 at 1-5 % w/w; the acid
# values are less certain).
_SG_K = {
    "sucrose": 0.384, "hexoses": 0.383, "lactose": 0.385, "maltose": 0.39,
    "lactic_acid": 0.22, "acetic_acid": 0.14, "gluconic_acid": 0.40, "ethanol": -0.18,
}  # fmt: skip
# Refractometer response relative to sucrose (refractive-index increments): ethanol reads
# ~0.44 °Bx per 1 % w/w, which is why a dry ferment never reads 0 °Bx.
_BRIX_K = {
    "sucrose": 1.0, "hexoses": 1.0, "lactose": 1.0, "maltose": 1.0,
    "lactic_acid": 0.5, "acetic_acid": 0.5, "gluconic_acid": 0.9, "ethanol": 0.44,
}  # fmt: skip


def density_series(pools: FloatArray, solids_offset: FloatArray) -> tuple[FloatArray, FloatArray]:
    """(specific gravity, apparent refractometer Brix) from pools (N, T, P) in g/kg.

    `solids_offset` (N,) stands for dissolved solids the model does not track (tea, fruit,
    protein, device bias), in g/kg sucrose equivalents; readings calibrate it.
    """
    off = solids_offset[:, None]
    sg = 1.0 + (sum(k * pools[:, :, PI[p]] for p, k in _SG_K.items()) + 0.384 * off) / 998.2
    brix = (sum(k * pools[:, :, PI[p]] for p, k in _BRIX_K.items()) + off) / 10.0
    return np.asarray(sg), np.asarray(brix)


@dataclass
class Posterior:
    z: FloatArray  # (K, D) all members from all rounds
    weights: FloatArray  # (K,) normalised
    traj: Trajectories  # stacked over all members
    ess: float
    rounds: int
    tempered: float  # likelihood exponent actually used (1.0 = untempered)
    solids_offset: FloatArray  # (K,)


def solids_offset(z: FloatArray) -> FloatArray:
    """Untracked dissolved solids plus device bias, g/kg sucrose-equivalent, from the last z
    column: 3 g/kg median, 90 % range -7 to +13 (about -0.003 to +0.005 SG): tea and fruit
    solids, and hydrometer/iSpindel calibration offsets, which are commonly 0.002-0.003 SG."""
    return np.asarray(3.0 + 6.0 * z[:, -1])


def _stack(trs: list[Trajectories]) -> Trajectories:
    return Trajectories(
        t_h=trs[0].t_h,
        pools=np.concatenate([t.pools for t in trs]),
        biomass_g=np.concatenate([t.biomass_g for t in trs]),
        ph=np.concatenate([t.ph for t in trs]),
    )


def log_likelihood(
    tr: Trajectories, obs: list[Observation], t_index: dict[float, int], solids: FloatArray
) -> FloatArray:
    n = tr.ph.shape[0]
    ll = np.zeros(n)
    if not obs:
        return ll
    sg = brix = None
    if any(o.key in ("gravity", "brix") for o in obs):
        sg, brix = density_series(tr.pools, solids)
    for o in obs:
        i = t_index[o.t_h]
        if o.key == "ph":
            pred = tr.ph[:, i]
        elif o.key == "gravity":
            assert sg is not None
            pred = sg[:, i]
        else:
            assert brix is not None
            pred = brix[:, i]
        s_meas, s_model = OBS_SIGMA[o.key]
        sigma2 = s_meas**2 + s_model**2
        r2 = (pred - o.value) ** 2
        ll += -0.5 * (NU + 1.0) * np.log1p(r2 / (NU * sigma2))
    return ll


def _log_norm(z: FloatArray, mean: FloatArray, var: FloatArray) -> FloatArray:
    return np.asarray(
        -0.5 * np.sum((z - mean) ** 2 / var + np.log(2 * math.pi * var), axis=1)
    )


def _normalise(logw: FloatArray) -> tuple[FloatArray, float]:
    w = np.exp(logw - np.max(logw))
    w /= w.sum()
    return w, float(1.0 / np.sum(w**2))


def run(
    spec: ModelSpec,
    obs: list[Observation],
    t_eval: FloatArray,
    *,
    n: int = 200,
    seed: int = 0,
) -> Posterior:
    """Prior ensemble, then (if there is data) AMIS rounds towards the posterior."""
    rng = np.random.default_rng(seed)
    t_index = {float(t): i for i, t in enumerate(t_eval)}
    d = spec.dim

    def solids(z: FloatArray) -> FloatArray:
        # Unmodelled dissolved solids, g/kg sucrose equivalents: an observation-only
        # parameter carried as the last z column (not part of the kinetic spec).
        return solids_offset(z)

    def draw_extra(k: int) -> FloatArray:
        return rng.standard_normal((k, 1))

    z0 = np.hstack([rng.standard_normal((n, d)), draw_extra(n)])
    trs = [simulate(spec.params(z0[:, :d]), t_eval)]
    zs = [z0]
    lls = [log_likelihood(trs[0], obs, t_index, solids(z0))]
    proposals = [(np.zeros(d + 1), np.ones(d + 1))]

    def weights(beta: float) -> tuple[FloatArray, float]:
        z = np.vstack(zs)
        ll = np.concatenate(lls)
        log_prior = _log_norm(z, np.zeros(d + 1), np.ones(d + 1))
        log_q = np.logaddexp.reduce(
            np.stack([_log_norm(z, m, v) for m, v in proposals]), axis=0
        ) - math.log(len(proposals))
        return _normalise(beta * ll + log_prior - log_q)

    w, ess = weights(1.0)
    rounds = 0
    while obs and rounds < MAX_ROUNDS and ess < TARGET_ESS_FRACTION * n:
        z_all = np.vstack(zs)
        mean = w @ z_all
        var = w @ (z_all - mean) ** 2
        var = np.clip(var * 1.5, 0.05, 1.0)  # inflate: proposals should over-cover
        z_new = mean + np.sqrt(var) * rng.standard_normal((n, d + 1))
        tr_new = simulate(spec.params(z_new[:, :d]), t_eval)
        zs.append(z_new)
        trs.append(tr_new)
        lls.append(log_likelihood(tr_new, obs, t_index, solids(z_new)))
        proposals.append((mean, var))
        rounds += 1
        w, ess = weights(1.0)

    beta = 1.0
    if obs and ess < MIN_ESS:
        lo, hi = 0.0, 1.0  # largest beta keeping ESS >= MIN_ESS
        for _ in range(20):
            mid = 0.5 * (lo + hi)
            _, e = weights(mid)
            lo, hi = (mid, hi) if e >= MIN_ESS else (lo, mid)
        beta = lo
        w, ess = weights(beta)

    z_all = np.vstack(zs)
    return Posterior(
        z=z_all,
        weights=w,
        traj=_stack(trs),
        ess=ess,
        rounds=rounds,
        tempered=beta,
        solids_offset=solids(z_all),
    )


def weighted_quantiles(
    values: FloatArray, weights: FloatArray, qs: tuple[float, ...]
) -> FloatArray:
    """Quantiles over axis 0 of values (K, ...) under weights (K,). Returns (len(qs), ...)."""
    order = np.argsort(values, axis=0)
    v = np.take_along_axis(values, order, axis=0)
    w = weights[order] if values.ndim == 1 else weights[order.reshape(order.shape[0], -1)].reshape(
        order.shape
    )
    cw = np.cumsum(w, axis=0)
    cw /= cw[-1]
    out = []
    for q in qs:
        idx = np.argmax(cw >= q, axis=0)
        out.append(np.take_along_axis(v, np.expand_dims(idx, 0), axis=0)[0])
    return np.asarray(out)
