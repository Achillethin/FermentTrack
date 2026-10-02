"""Derived layer: nutrition per 100 g, taste activities and phases (prediction/derived.py)."""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction import derived, engine, service
from fermenttrack.prediction.engine import N_POOLS, PI
from fermenttrack.prediction.profiles import PROFILES


def _pools(t: int = 1, n: int = 1) -> np.ndarray:
    return np.zeros((n, t, N_POOLS))


def test_energy_abv_and_co2_mass_loss() -> None:
    pools = _pools(2)
    pools[0, 0, PI["sucrose"]] = 100.0
    pools[0, 1, PI["ethanol"]] = 47.0
    pools[0, 1, PI["co2"]] = 45.0
    rows, lower = derived.nutrition(pools, derived.UNKNOWN, co2_escapes=True)
    left = 1.0 - 0.045
    assert rows["sugars"][0, 0] == pytest.approx(10.0)
    assert rows["energy_kcal"][0, 0] == pytest.approx(40.0)
    assert rows["alcohol"][0, 1] == pytest.approx(47.0 / (10 * left) * 10 / 7.89)
    assert rows["energy_kcal"][0, 1] == pytest.approx(7.0 * 47.0 / (10 * left))
    assert "fat" not in rows and {"energy_kcal", "energy_kj", "carbohydrate"} <= lower


def test_a_dough_keeps_its_mass() -> None:
    pools = _pools()
    pools[0, 0, PI["co2"]] = 30.0
    pools[0, 0, PI["maltose"]] = 20.0
    rows, _ = derived.nutrition(pools, derived.UNKNOWN, co2_escapes=False)
    assert rows["sugars"][0, 0] == pytest.approx(2.0)


def test_carried_rows_and_lower_bounds() -> None:
    carried = derived.Carried(
        fat=32.5, fibre=None, sodium=0.43, other_carbohydrate=0.0, lower=frozenset({"fat"})
    )
    rows, lower = derived.nutrition(_pools(), carried, co2_escapes=True)
    assert rows["fat"][0, 0] == pytest.approx(3.25)
    assert rows["salt"][0, 0] == pytest.approx(0.43 * 2.5 / 10)
    assert "fibre" not in rows
    assert {"fat", "energy_kcal", "energy_kj"} <= lower and "salt" not in lower


def _prior_run(ferment: str, n: int = 16) -> np.ndarray:
    profile = PROFILES[ferment]
    inputs = service.PredictionInputs(
        fermentation_type=ferment, now_h=0.0, expected_temperature_c=None,
        organisms=tuple(
            service.OrganismIn(o, ORGANISMS.get(o, "bacteria"), ())
            for o in FERMENTATION_TYPE_ORGANISMS[ferment]
        ),
        organism_source="default", recipe=(), measurements=(),
    )  # fmt: skip
    init = service._initial_state(profile, inputs.recipe)
    plans = service._plan_organisms(inputs, profile)
    sched, *_ = service._schedule(inputs, profile, None, profile.horizon_h)
    spec, _ = service._spec(profile, plans, init, sched, {})
    z = np.random.default_rng(0).standard_normal((n, spec.dim))
    tr = engine.simulate(
        spec.params(z), np.linspace(0.0, profile.horizon_h, 41), keep_states=True
    )
    assert tr.y is not None
    # Raw states, not the zero-clipped pools: when a substrate runs out the adaptive step
    # can overshoot below zero (Monod's kink hides from the error estimate); clipping the
    # display then hides that negative mass (vinegar: ~1 % of the acetic acid).
    return np.asarray(tr.y[:, :, :N_POOLS])


@pytest.mark.parametrize("ferment", sorted(PROFILES))
def test_batch_energy_never_rises(ferment: str) -> None:
    """Fermentation only loses energy. Measured with carbohydrate in monosaccharide
    equivalents (3.75 kcal/g): on the EU label basis (4 kcal/g as weighed) hydrolysis
    alone would add energy (starch -> glucose gains 11 % in mass from water)."""
    p = _prior_run(ferment)

    def g(k: str) -> np.ndarray:
        return p[:, :, PI[k]]

    mono = g("hexoses") + 1.0526 * (g("sucrose") + g("lactose") + g("maltose")) + 1.111 * g(
        "starch"
    )
    kcal = (
        3.75 * mono + 4.0 * (g("protein") + g("peptides") + g("amino_acids")) + 7.0 * g("ethanol")
        + 3.0 * (g("lactic_acid") + g("acetic_acid") + g("gluconic_acid"))
    )  # fmt: skip
    assert np.all(np.diff(kcal, axis=1) <= 1e-3 * kcal[:, :1])
