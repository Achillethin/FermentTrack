"""Derived layer: nutrition per 100 g, taste activities and phases (prediction/derived.py)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction import compounds, derived, engine, service
from fermenttrack.prediction.engine import N_POOLS, PI
from fermenttrack.prediction.priors import Z90
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


def _uniform(n: int) -> np.ndarray:
    return np.full(n, 1.0 / n)


def test_sweet_noticeable_share_is_the_threshold_distribution() -> None:
    n = 20000
    pools = _pools(1, n)
    pools[:, 0, PI["sucrose"]] = 3.0
    der = derived.evaluate(pools, np.full((n, 1), 6.0), PROFILES["kombucha"], derived.UNKNOWN, 1)
    share = float(np.mean(der.activity["sweet"][:, 0] > 1.0))
    prior = compounds.SWEET_THRESHOLD
    z = math.log(3.0 / prior.median) / (math.log(prior.hi / prior.median) / Z90)
    assert share == pytest.approx(0.5 * (1 + math.erf(z / math.sqrt(2))), abs=0.01)


def test_sour_counts_protonated_acid_not_total_acid() -> None:
    pools = _pools(2)
    pools[0, :, PI["lactic_acid"]] = 9.0  # 0.1 mol/kg
    der = derived.evaluate(
        pools, np.array([[3.0, 6.0]]), PROFILES["lacto_ferment"], derived.UNKNOWN, 1
    )
    sour = der.activity["sour"][0]
    assert sour[0] > 50 * sour[1]  # 88 % protonated at pH 3, 0.7 % at pH 6


def test_kombucha_ladder_climbs_with_the_sugar_acid_balance() -> None:
    n = 4000
    pools = _pools(3, n)
    pools[:, :, PI["sucrose"]] = [70.0, 20.0, 5.0]
    pools[:, :, PI["acetic_acid"]] = [0.7, 1.5, 12.0]
    der = derived.evaluate(pools, np.full((n, 3), 3.5), PROFILES["kombucha"], derived.UNKNOWN, 2)
    t = np.array([0.0, 1.0, 2.0])
    block = derived.sensory_block(der, t, _uniform(n), np.arange(3), 1.0, 2)
    tp = block["taste_phases"]
    prob = np.array([tp["prob"][name] for name in tp["vocabulary"]])
    assert np.allclose(prob.sum(axis=0), 1.0)
    assert list(prob.argmax(axis=0)) == [0, 1, 3]  # sweet, balanced, vinegary


def test_now_past_the_window_clamps_to_the_end() -> None:
    pools = _pools(3)
    der = derived.evaluate(pools, np.full((1, 3), 6.0), PROFILES["kefir"], derived.UNKNOWN, 3)
    t = np.array([0.0, 5.0, 10.0])
    block = derived.sensory_block(der, t, _uniform(1), np.arange(3), 99.0, 2)
    assert block["now_h"] == block["end_h"] == 10.0


def test_label_rows_and_series() -> None:
    pools = _pools(2, 8)
    pools[:, :, PI["lactose"]] = [48.0, 30.0]
    pools[:, :, PI["lactic_acid"]] = [0.0, 8.0]
    der = derived.evaluate(pools, np.full((8, 2), 4.5), PROFILES["kefir"], derived.UNKNOWN, 4)
    t = np.array([0.0, 24.0])
    block = derived.sensory_block(der, t, _uniform(8), np.arange(2), 24.0, 1)
    rows = {r["key"]: r for r in block["nutrition_label"]}
    assert rows["lactose"]["start"]["p50"] == pytest.approx(4.8)
    assert rows["fat"]["start"] is None and rows["energy_kcal"]["now"]["lower_bound"]
    assert "alcohol" not in rows  # optional rows with nothing in them are left out
    keys = {s["key"] for s in derived.series_out(der, np.arange(2), t, _uniform(8))}
    assert {"taste:sour", "nut:lactose", "nut:energy_kcal"} <= keys
    assert "taste:umami" not in keys  # no free amino acids: below a tenth of the threshold
    ms = derived.taste_milestones(PROFILES["kefir"])
    assert [m.key for m in ms] == ["taste_tangy", "taste_sour"] and ms[0].lens == "taste"
