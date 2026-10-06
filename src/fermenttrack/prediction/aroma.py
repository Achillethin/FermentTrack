"""Aroma tracers on a forecast ensemble (increment B).

Each odorant obeys dC/dt = S(t) - K(t)·C on every member, with S and K built from the
engine's per-organism growth and flux, its pools, pH and temperature, and from the
batch's ingredients. Templates run in dependency order (precursor -> product), so each
tracer is linear with known coefficients and is integrated exactly per interval. Data:
aroma_data.py; design: docs/superpowers/specs/2026-10-05-aroma-curation.md.
"""

from __future__ import annotations

import numpy as np

from fermenttrack.prediction import aroma_data as A
from fermenttrack.prediction.priors import FloatArray

Draws = dict[str, FloatArray]


def _phi(x: FloatArray) -> tuple[FloatArray, FloatArray]:
    """phi1 = (1 - e^-x)/x and phi2 = (x - 1 + e^-x)/x^2, stable near 0."""
    small = x < 1e-4
    xs = np.where(small, 1.0, x)
    em = -np.expm1(-xs)
    p1 = np.where(small, 1.0 - x / 2.0 + x * x / 6.0, em / xs)
    p2 = np.where(small, 0.5 - x / 6.0 + x * x / 24.0, (xs - em) / (xs * xs))
    return p1, p2


def integrate(t: FloatArray, source: FloatArray, k: FloatArray, c0: FloatArray) -> FloatArray:
    """C' = S - K·C with S linear and K at its interval mean: exact per interval.
    source (N, T) µg/kg/h, k (N, T) 1/h, c0 (N,) µg/kg -> (N, T) µg/kg."""
    n, nt = source.shape
    c = np.empty((n, nt))
    c[:, 0] = c0
    for i in range(nt - 1):
        h = float(t[i + 1] - t[i])
        if h <= 0.0:
            c[:, i + 1] = c[:, i]
            continue
        x = 0.5 * (k[:, i] + k[:, i + 1]) * h
        p1, p2 = _phi(x)
        s0 = source[:, i]
        s1 = (source[:, i + 1] - s0) / h
        c[:, i + 1] = np.maximum(c[:, i] * np.exp(-x) + s0 * h * p1 + s1 * h * h * p2, 0.0)
    return c


def neutral_fraction(ph: FloatArray, kind: str, pka: float | None) -> FloatArray:
    """Share of an acid or amine in its volatile, uncharged form (curation spec D5)."""
    ph = np.asarray(ph, dtype=float)
    if kind == "acid" and pka is not None:
        return np.asarray(1.0 / (1.0 + 10.0 ** (ph - pka)))
    if kind == "base" and pka is not None:
        return np.asarray(1.0 / (1.0 + 10.0 ** (pka - ph)))
    return np.ones_like(ph)


def draws(n: int, seed: int) -> Draws:
    """Template parameters, thresholds, ingredient pools and the shared matrix factor per
    member: nothing observes them yet, so prior draws are their posterior (spec 2026-10-02
    § 1). Each value is (N, 1)."""
    priors = dict(A.PARAMS)
    priors.update({f"thr:{k}": c.threshold for k, c in A.COMPOUNDS.items() if c.threshold})
    priors.update({f"ing:{i}:{k}": p for i, e in A.AROMA_INGREDIENTS.items() for k, p in e.items()})
    z = np.random.default_rng(seed).standard_normal((n, len(priors)))
    out = {}
    for j, (k, p) in enumerate(priors.items()):
        v = np.asarray(p.value(z[:, j]))
        # Split-normal tails can cross 0 (lin rates) or 1 (shares, either scale). Shares
        # stop at 0.95 so that s / (1 - s) stays finite in the templates.
        if k.startswith(("share_", "excr_")):
            v = np.clip(v, 0.0, 0.95)
        elif p.scale == "lin":
            v = np.maximum(v, 0.0)
        out[k] = v[:, None]
    return out


def kaw25(key: str, d: Draws) -> FloatArray | float:
    """K_aw at 25 °C: measured (§ 5.12), else the class stand-in x the member's factor."""
    if key in A.KAW:
        return A.KAW[key]
    return A.KAW[A.KAW_CLASS[key]] * d["kaw_standin"]


def volatility(
    key: str, temp: FloatArray, f_neutral: FloatArray, co2_rate: FloatArray, d: Draws,
    co2_escapes: bool, k_surf_d: FloatArray | float = 0.0,
) -> FloatArray:  # fmt: skip
    """Loss rate (1/h): CO2 stripping of the neutral form plus open-surface loss (§ 5.12).
    co2_rate in g/kg/h; k_surf_d in 1/d (0 for a closed jar)."""
    kaw = kaw25(key, d) * d["kaw_tfactor"] ** ((temp - 25.0) / 10.0) * f_neutral
    strip = (np.maximum(co2_rate, 0.0) / 44.01 * 24.5) * kaw * d["kaw_eta"] if co2_escapes else 0.0
    return np.asarray(strip + k_surf_d * kaw / 24.0)


def odour_activity(conc: FloatArray, key: str, f_neutral: FloatArray, d: Draws) -> FloatArray:
    """Concentration of the volatile form over the member's threshold x shared matrix factor."""
    return np.asarray(conc * f_neutral / (d[f"thr:{key}"] * d["matrix"]))
