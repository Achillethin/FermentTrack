"""What the app learns across batches: a crossed Gaussian hierarchy over the kinetic
parameters, per organism and pooled parameter, in the literature prior's z-units u (the
literature prior is exactly N(0, 1) there):

    theta_batch = g + d_style + a_baker + e_starter + eps
    variances     0.30  0.20    0.10     0.30      0.10   (sum 1)

"Achille's classic levain" inherits the classic-levain class and Achille; "Aymard's rye
levain" the rye class and Aymard. With no data anywhere a batch's prior is exactly the
literature prior (the general default inherits the global class), and each finished,
calibrated batch adds one piece of evidence per organism and parameter: its **likelihood
summary** (its AMIS posterior with the prior it ran under divided out, so pooled
information is never counted twice). The prior for a new batch is exact Gaussian
conditioning on all evidence rows. Design: docs/superpowers/specs/
2026-09-28-sourdough-engine-design.md § 6 (supersedes the plug-in pooling of
2026-09-28-population-pooling-design.md; its table is left unused).
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from fermenttrack.models import BatchEvidence
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from fermenttrack.prediction.priors import Z90, FloatArray, Prior

# The parameters most identifiable from pH / rise / gravity curves. ponytail: the other
# kinetic parameters stay on literature priors; add more once evidence shows them moving.
POOLED_PARAMS = ("mu_max", "t_opt")

# Variance components in literature z-units, summing to 1 (est.; the literature spread
# across strains is split into class, style, baker, starter and batch parts). ponytail:
# fixed; scripts/estimate_variance_components.py re-estimates them by REML once enough
# starters have several batches each.
VARIANCES = {"global": 0.30, "style": 0.20, "baker": 0.10, "starter": 0.30, "batch": 0.10}
MIN_NARROWING = 0.10  # a batch must shrink the prior variance by 10 % to count as evidence
MAX_ROWS = 2000  # ponytail: O(n^3) conditioning; switch to group sufficient statistics beyond


# ── u-space: the literature prior's own z-units ─────────────────────────


def to_u(lit: Prior, x: FloatArray | float) -> FloatArray:
    """Inverse of Prior.value: the literature z-score of a parameter value (split normal)."""
    x = np.asarray(x, dtype=float)
    if lit.scale == "log":
        y = np.log(np.maximum(x, 1e-300) / lit.median)
        s_lo, s_hi = math.log(lit.median / lit.lo) / Z90, math.log(lit.hi / lit.median) / Z90
    else:
        y = x - lit.median
        s_lo, s_hi = (lit.median - lit.lo) / Z90, (lit.hi - lit.median) / Z90
    s_lo, s_hi = max(s_lo, 1e-12), max(s_hi, 1e-12)
    return np.asarray(np.where(y < 0, y / s_lo, y / s_hi))


def from_u(lit: Prior, mean: float, var: float) -> Prior:
    """N(mean, var) in u-space -> a Prior in the parameter's own units."""
    sd = math.sqrt(max(var, 1e-9))
    lo, med, hi = lit.value(np.array([mean - Z90 * sd, mean, mean + Z90 * sd]))
    return Prior(float(med), float(min(lo, med)), float(max(hi, med)), lit.scale)


def prior_moments_u(lit: Prior, prior: Prior) -> tuple[float, float]:
    """(mean, variance) in u-space of the prior a batch actually ran with."""
    lo, med, hi = to_u(lit, np.array([prior.lo, prior.median, prior.hi]))
    sd = max((hi - lo) / (2 * Z90), 1e-6)
    return float(med), float(sd**2)


# ── evidence from one batch ─────────────────────────────────────────────


@dataclass(frozen=True)
class Evidence:
    organism: str
    param: str
    ell: float  # likelihood mean, u-space
    lam: float  # likelihood precision, u-space


def likelihood_summaries(
    specs: Sequence[Any], organisms: Sequence[Any], z: FloatArray, weights: FloatArray
) -> list[Evidence]:
    """Per organism x pooled param: what this batch's readings said, with the prior it ran
    under divided out (Gaussian division of the weighted posterior by that prior).
    `specs`: ModelSpec.specs (or SourdoughModel.specs); `organisms`: their kinetics."""
    w = weights / weights.sum()
    out = []
    for col, s in enumerate(specs):
        if s.organism is None or s.name not in POOLED_PARAMS:
            continue
        name = organisms[s.organism].name
        lit_kin = ORGANISM_KINETICS.get(name)
        if lit_kin is None:
            continue
        lit: Prior = getattr(lit_kin, s.name)
        u = to_u(lit, s.prior.value(z[:, col]))
        m_post = float(np.sum(w * u))
        v_post = float(np.sum(w * (u - m_post) ** 2))
        m_pr, v_pr = prior_moments_u(lit, s.prior)
        if not (0.0 < v_post < (1.0 - MIN_NARROWING) * v_pr):
            continue  # the readings said nothing about this parameter
        lam = 1.0 / v_post - 1.0 / v_pr
        ell = (m_post / v_post - m_pr / v_pr) / lam
        out.append(Evidence(name, s.name, ell, lam))
    return out


# ── conditioning ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Row:
    style: str | None
    baker: str | None
    starter: str | None
    ell: float
    lam: float


def _same(a: str | None, b: str | None) -> float:
    return 1.0 if a is not None and a == b else 0.0


def predictive(rows: Sequence[Row], style: str | None, baker: str | None,
               starter: str | None, v: dict[str, float] = VARIANCES) -> tuple[float, float]:  # fmt: skip
    """Mean and variance (u-space) of a new batch's parameter for this starter, style and
    baker, given every evidence row: exact Gaussian conditioning."""
    total = sum(v.values())
    if not rows:
        return 0.0, total
    rows = list(rows)[-MAX_ROWS:]
    n = len(rows)
    sig = np.full((n, n), v["global"])
    c = np.full(n, v["global"])
    for i, a in enumerate(rows):
        c[i] += (
            v["style"] * _same(style, a.style)
            + v["baker"] * _same(baker, a.baker)
            + v["starter"] * _same(starter, a.starter)
        )
        for j in range(i, n):
            b = rows[j]
            k = (
                v["style"] * _same(a.style, b.style)
                + v["baker"] * _same(a.baker, b.baker)
                + v["starter"] * _same(a.starter, b.starter)
            )
            sig[i, j] += k
            sig[j, i] = sig[i, j]
        sig[i, i] += v["batch"] + 1.0 / max(a.lam, 1e-9)
    y = np.array([r.ell for r in rows])
    sol = np.linalg.solve(sig, np.column_stack([y, c]))
    return float(c @ sol[:, 0]), float(max(total - c @ sol[:, 1], 1e-6))


def learned_prior(lit: Prior, rows: Sequence[Row], style: str | None, baker: str | None,
                  starter: str | None) -> Prior:  # fmt: skip
    if not rows:
        return lit
    m, var = predictive(rows, style, baker, starter)
    return from_u(lit, m, var)


# ── database ────────────────────────────────────────────────────────────


async def learned_priors(
    db: AsyncSession,
    organisms: Sequence[str],
    *,
    style: str | None,
    baker: str | None,
    starter: uuid.UUID | None,
) -> dict[str, dict[str, Prior]]:
    """organism -> {param -> Prior} for a new batch; only entries that differ from the
    literature (organisms with no evidence anywhere are left out: literature prior)."""
    names = [o for o in organisms if o in ORGANISM_KINETICS]
    if not names:
        return {}
    res = await db.execute(
        select(BatchEvidence)
        .where(BatchEvidence.organism.in_(names))
        .order_by(BatchEvidence.created_at)  # MAX_ROWS keeps the most recent
    )
    by: dict[tuple[str, str], list[Row]] = {}
    for e in res.scalars():
        by.setdefault((e.organism, e.param), []).append(
            Row(e.style, e.owner_id, str(e.culture_id), e.ell, e.lam)
        )
    # the dense solve is CPU: off the event loop, like the forecasts themselves
    return await run_in_threadpool(_condition_all, by, style, baker, str(starter) if starter else None)


def _condition_all(
    by: dict[tuple[str, str], list[Row]], style: str | None, baker: str | None, starter: str | None
) -> dict[str, dict[str, Prior]]:
    out: dict[str, dict[str, Prior]] = {}
    for (org, param), rows in by.items():
        lit = getattr(ORGANISM_KINETICS[org], param)
        out.setdefault(org, {})[param] = learned_prior(lit, rows, style, baker, starter)
    return out


async def record_evidence(
    db: AsyncSession,
    *,
    batch_id: uuid.UUID,
    culture_id: uuid.UUID,
    owner_id: str | None,
    style: str | None,
    evidence: Sequence[Evidence],
) -> int:
    """Store a finished batch's evidence once (unique per batch x organism x param)."""
    existing = {
        (e.organism, e.param)
        for e in (
            await db.execute(select(BatchEvidence).where(BatchEvidence.batch_id == batch_id))
        ).scalars()
    }
    added = 0
    for ev in evidence:
        if (ev.organism, ev.param) in existing or not (math.isfinite(ev.ell) and ev.lam > 0):
            continue
        db.add(
            BatchEvidence(
                batch_id=batch_id, culture_id=culture_id, owner_id=owner_id, style=style,
                organism=ev.organism, param=ev.param, ell=ev.ell, lam=ev.lam,
            )
        )  # fmt: skip
        added += 1
    await db.flush()
    return added
