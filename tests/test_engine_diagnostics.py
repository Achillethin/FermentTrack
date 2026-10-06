"""The engine reports per-organism growth, substrate and CO2 flux without changing the solve."""

from __future__ import annotations

import numpy as np

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction import engine, service
from fermenttrack.prediction.engine import HEXOSE_PER_G, PI, EnsembleParams
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES


def _setup(
    ferment: str, n: int = 8, organisms: list[str] | None = None, temp: float | None = None
) -> tuple[EnsembleParams, FloatArray]:
    """Prior ensemble parameters for a type's typical recipe, and its 161-point grid."""
    profile = PROFILES[ferment]
    names = organisms if organisms is not None else FERMENTATION_TYPE_ORGANISMS[ferment]
    inputs = service.PredictionInputs(
        fermentation_type=ferment, now_h=0.0, expected_temperature_c=temp,
        organisms=tuple(service.OrganismIn(o, ORGANISMS.get(o, "bacteria"), ()) for o in names),
        organism_source="default" if organisms is None else "custom", recipe=(), measurements=(),
    )  # fmt: skip
    init = service._initial_state(profile, inputs.recipe)
    plans = service._plan_organisms(inputs, profile)
    sched, *_ = service._schedule(inputs, profile, None, profile.horizon_h)
    spec, _ = service._spec(profile, plans, init, sched, {})
    z = np.random.default_rng(0).standard_normal((n, spec.dim))
    return spec.params(z), np.linspace(0.0, profile.horizon_h, 161)


def test_solve_is_unchanged_by_keeping_states() -> None:
    p, t = _setup("kombucha")
    a = engine.simulate(p, t)
    b = engine.simulate(p, t, keep_states=True)
    assert np.array_equal(a.pools, b.pools) and np.array_equal(a.ph, b.ph)


def test_flux_integrates_to_the_sugar_the_pools_lost() -> None:
    p, t = _setup("lacto_ferment")
    tr = engine.simulate(p, t, keep_states=True)
    assert tr.y is not None
    d = engine.diagnose(p, t, tr.y)
    flux = sum(d[f"flux:{j}"] for j in range(len(p.organisms)))
    used = np.trapezoid(flux, t, axis=1)
    lost = sum(
        HEXOSE_PER_G.get(k, 1.0) * (tr.pools[:, 0, PI[k]] - tr.pools[:, -1, PI[k]])
        for k in ("sucrose", "hexoses", "lactose", "maltose")
    )
    assert np.allclose(used, lost, rtol=0.05, atol=0.05)


def test_co2_flux_integrates_to_the_co2_pool() -> None:
    p, t = _setup("kombucha")
    tr = engine.simulate(p, t, keep_states=True)
    assert tr.y is not None
    d = engine.diagnose(p, t, tr.y)
    made = np.trapezoid(d["co2"], t, axis=1)
    gained = tr.pools[:, -1, PI["co2"]] - tr.pools[:, 0, PI["co2"]]
    assert np.allclose(made, gained, rtol=0.05, atol=0.05)


def test_growth_is_reported_per_organism() -> None:
    p, t = _setup("lacto_ferment")
    tr = engine.simulate(p, t, keep_states=True)
    assert tr.y is not None
    d = engine.diagnose(p, t, tr.y)
    for j in range(len(p.organisms)):
        assert d[f"growth:{j}"].shape == (p.n, len(t)) and np.all(d[f"growth:{j}"] >= 0.0)
    assert np.any(d["growth:0"] > 0.0)


def test_strided_diagnostics_match_the_full_grid() -> None:
    """Every 2nd time evaluated, the rest interpolated: the aroma layer's cost saving. Monod
    kinks (a substrate running out within one grid step) cost a few members up to ~25 % of
    an integrated rate; the ensemble median stays within 3 %, far inside the aroma priors."""
    p, t = _setup("lacto_ferment", 16)
    tr = engine.simulate(p, t, keep_states=True)
    assert tr.y is not None
    full = engine.diagnose(p, t, tr.y)
    half = engine.diagnose(p, t, tr.y, stride=2)
    assert np.allclose(half["co2"][:, ::2], full["co2"][:, ::2], rtol=1e-4, atol=1e-9)
    for key in full:
        a = np.trapezoid(full[key], t, axis=1)
        rel = np.abs(np.trapezoid(half[key], t, axis=1) / np.maximum(a, 1e-9) - 1.0)
        assert np.median(rel) < 0.03 and np.max(rel) < 0.25, key
