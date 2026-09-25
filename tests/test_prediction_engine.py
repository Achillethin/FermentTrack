"""Kinetic engine building blocks: priors, cardinal models, water activity, pH, mass balance."""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.prediction import engine
from fermenttrack.prediction.model import ModelSpec, TemperatureSchedule
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from fermenttrack.prediction.priors import Z90, Prior
from fermenttrack.prediction.profiles import PROFILES


def test_prior_maps_quantiles_to_its_range() -> None:
    p = Prior(0.4, 0.2, 1.0)
    v = p.value(np.array([-Z90, 0.0, Z90]))
    assert v == pytest.approx([0.2, 0.4, 1.0])
    lin = Prior(30.0, 27.0, 36.0, "lin")
    assert lin.value(np.array([-Z90, 0.0, Z90])) == pytest.approx([27.0, 30.0, 36.0])


def test_prior_rejects_disordered_range() -> None:
    with pytest.raises(ValueError):
        Prior(1.0, 2.0, 3.0)
    with pytest.raises(ValueError):
        Prior(1.0, 0.0, 3.0)  # log scale needs lo > 0


def test_ctmi_is_one_at_optimum_and_zero_outside() -> None:
    t = np.array([4.0, 5.0, 20.0, 35.0, 41.0, 45.0])
    g = engine.ctmi(t, np.full(6, 5.0), np.full(6, 35.0), np.full(6, 41.0))
    assert g[0] == 0.0 and g[1] == 0.0 and g[4] == 0.0 and g[5] == 0.0
    assert g[3] == pytest.approx(1.0)
    assert 0.0 < g[2] < 1.0


def test_cpm_is_one_at_optimum_and_zero_outside() -> None:
    ph = np.array([3.0, 3.3, 4.5, 6.0, 8.5])
    g = engine.cpm(ph, np.full(5, 3.3), np.full(5, 6.0), np.full(5, 8.5))
    assert list(g[[0, 1, 4]]) == [0.0, 0.0, 0.0]
    assert g[3] == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("salt_pct", "aw"), [(0.0, 1.0), (3.0, 0.982), (10.0, 0.935), (20.0, 0.84), (26.4, 0.76)]
)
def test_water_activity_matches_nacl_tables(salt_pct: float, aw: float) -> None:
    assert engine.water_activity(np.array([salt_pct]))[0] == pytest.approx(aw, abs=0.01)


def _ph(acids_g_per_kg: dict[str, float], ph0: float, beta_mm: float, ionic: float = 0.0) -> float:
    pools = np.zeros((1, engine.N_POOLS))
    for k, v in acids_g_per_kg.items():
        pools[0, engine.PI[k]] = v
    buf = engine.buffer_groups(np.array([beta_mm]))
    ka = engine.acid_ka(ionic)
    z = engine.strong_ion_offset(np.array([ph0]), np.zeros((1, 3)), buf, ka)
    h = engine.solve_h(engine.acid_moles(pools), buf, z, ka, np.array([1e-6]))
    return float(-np.log10(h[0]))


def test_charge_balance_reproduces_the_matrix_ph_without_acid() -> None:
    assert _ph({}, 6.2, 35.0) == pytest.approx(6.2, abs=1e-6)


def test_unbuffered_acetic_acid_ph() -> None:
    # 4 g/L acetic acid in plain water is pH ~2.97 (textbook weak-acid equilibrium)
    assert _ph({"acetic_acid": 4.0}, 7.0, 1e-6) == pytest.approx(2.97, abs=0.03)


def test_buffer_capacity_slows_acidification() -> None:
    weak = _ph({"lactic_acid": 10.0}, 6.2, 10.0)
    strong = _ph({"lactic_acid": 10.0}, 6.2, 60.0)
    assert weak < strong
    # sauerkraut: ~1.5 % lactic acid in cabbage buffer ends near pH 3.5
    assert _ph({"lactic_acid": 15.0}, 6.2, 35.0, ionic=0.38) == pytest.approx(3.55, abs=0.25)


def test_salt_lowers_apparent_pka() -> None:
    assert engine.acid_ka(0.4)[0] > engine.acid_ka(0.0)[0]
    assert engine.acid_ka(5.0)[0] == engine.acid_ka(0.5)[0]  # Davies capped at I = 0.5


def _homolactic_spec(temp: float = 30.0) -> ModelSpec:
    profile = PROFILES["lacto_ferment"]
    lp = ORGANISM_KINETICS["Lactobacillus plantarum"]
    return ModelSpec(
        profile=profile,
        organisms=[lp],
        can_grow=[True],
        inoculum=[profile.inoculum[lp.name]],
        pools0={"hexoses": 30.0},
        salt_water_phase_pct=2.0,
        schedule=TemperatureSchedule([0.0], [temp], [0.0]),
    )


def test_homolactic_mass_balance_and_monotone_acidification() -> None:
    spec = _homolactic_spec()
    z = np.random.default_rng(1).standard_normal((32, spec.dim))
    tr = engine.simulate(spec.params(z), np.linspace(0.0, 400.0, 41))
    sugar = tr.pools[:, :, engine.PI["hexoses"]]
    lactic = tr.pools[:, :, engine.PI["lactic_acid"]]
    consumed = sugar[:, 0] - sugar[:, -1]
    # every gram of sugar consumed yields 0.9 g lactate (homolactic stoichiometry)
    assert lactic[:, -1] == pytest.approx(0.9 * consumed, rel=0.01)
    assert np.all(consumed > 1.0)
    assert np.all(np.diff(sugar, axis=1) <= 1e-6)
    assert np.all(np.diff(tr.ph, axis=1) <= 1e-6)
    assert np.all(tr.pools >= 0.0)


def test_warmer_ferments_faster_below_the_optimum() -> None:
    z = np.random.default_rng(2).standard_normal((32, _homolactic_spec().dim))
    t = np.linspace(0.0, 96.0, 25)
    cool = engine.simulate(_homolactic_spec(15.0).params(z), t)
    warm = engine.simulate(_homolactic_spec(28.0).params(z), t)
    assert np.median(warm.ph[:, -1]) < np.median(cool.ph[:, -1]) - 0.3


def test_obligate_aerobe_cannot_grow_in_a_closed_ferment() -> None:
    profile = PROFILES["lacto_ferment"]
    aab = ORGANISM_KINETICS["Acetobacter aceti"]
    spec = ModelSpec(
        profile=profile,
        organisms=[aab],
        can_grow=[False],
        inoculum=[Prior(5.0, 4.0, 6.0, "lin")],
        pools0={"ethanol": 20.0},
        salt_water_phase_pct=0.0,
        schedule=TemperatureSchedule([0.0], [28.0], [0.0]),
    )
    z = np.zeros((1, spec.dim))
    tr = engine.simulate(spec.params(z), np.linspace(0.0, 200.0, 11))
    assert tr.pools[0, -1, engine.PI["acetic_acid"]] == pytest.approx(0.0)
    assert tr.pools[0, -1, engine.PI["ethanol"]] == pytest.approx(20.0)
