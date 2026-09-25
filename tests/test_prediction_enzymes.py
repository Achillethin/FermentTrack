"""Koji, miso and garum enzyme kinetics against the literature checkpoints of the scientific
review (docs/superpowers/specs/2026-09-25-koji-miso-garum-enzymes-review.md § 5).

Checkpoints 1-6 and 9-10 run the engine on the median parameter set (every prior at its
median) for the published set-up: koji or fish in water or brine at a fixed temperature.
Checkpoints 7-8 and the garum temperature ordering run the full prior forecast. Ranges are
loose: the priors are calibrated to these studies, not fitted to them.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest
from test_prediction_trajectories import _at, _forecast, _milestone

from fermenttrack.prediction import enzymes
from fermenttrack.prediction.engine import PI, EnzymeParams, Trajectories, arrhenius, simulate
from fermenttrack.prediction.model import ModelSpec, TemperatureSchedule
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from fermenttrack.prediction.priors import Prior
from fermenttrack.prediction.profiles import PROFILES


def _fixed(v: float) -> Prior:
    return Prior(v, v, v)


def _run(
    pools: dict[str, float],
    salt_pct: float,
    schedule: TemperatureSchedule,
    days: list[float],
    *,
    koji: float = 0.0,
    fish: float = 0.0,
    access: float = 1.0,
) -> Trajectories:
    """Median-parameter run of koji (its enzymes, not the mold) and/or fish in a mash."""
    profile = dataclasses.replace(
        PROFILES["garum"],
        koji_enzyme0=_fixed(koji) if koji else None,
        fish_enzyme0=_fixed(fish) if fish else None,
        enzyme_access=access,
    )
    orgs = [ORGANISM_KINETICS["Aspergillus oryzae"]] if koji else []
    spec = ModelSpec(
        profile=profile,
        organisms=orgs,
        can_grow=[False] * len(orgs),
        inoculum=[_fixed(0.01)] * len(orgs),
        pools0=pools,
        salt_water_phase_pct=salt_pct,
        schedule=schedule,
    )
    t = np.r_[0.0, np.asarray(days, dtype=float) * 24.0]
    return simulate(spec.params(np.zeros((1, spec.dim))), t)


def _const(temp_c: float) -> TemperatureSchedule:
    return TemperatureSchedule([0.0], [temp_c], [0.0])


def _share(tr: Trajectories, key: str, of: str, i: int = -1) -> float:
    return float(tr.pools[0, i, PI[key]] / tr.pools[0, 0, PI[of]])


def _soluble(tr: Trajectories, i: int = -1) -> float:
    return _share(tr, "peptides", "protein", i) + _share(tr, "amino_acids", "protein", i)


def _left(tr: Trajectories, *keys: str) -> float:
    now, start = (sum(tr.pools[0, i, PI[k]] for k in keys) for i in (-1, 0))
    return float(now / start)


def _saccharified(temp_c: float, hours: float) -> float:
    # koji:water 1:2 (koji ~60 % starch)
    tr = _run({"starch": 200.0}, 0.0, _const(temp_c), [hours / 24.0], koji=1 / 3)
    return 1.0 - _share(tr, "starch", "starch")


def test_1_saccharification_akamatsu_2024() -> None:
    # ~60 % of the rice degraded in 24 h at 50 °C, ~10 % at 15 °C
    assert 0.45 <= _saccharified(50.0, 24.0) <= 0.75
    assert 0.05 <= _saccharified(15.0, 24.0) <= 0.2


def test_2_temperature_optimum_emerges_oguro_2019() -> None:
    # 8 h glucose yields 66 / 100 / 92 / 77 % at 40 / 50 / 60 / 70 °C: catalysis speeds up
    # while inactivation catches up; neither is an input curve any more
    y = {t: _saccharified(t, 8.0) for t in (40.0, 50.0, 60.0, 70.0)}
    rel = {t: v / y[50.0] for t, v in y.items()}
    assert 0.5 <= rel[40.0] <= 0.8
    assert 0.8 <= rel[60.0] <= 1.1
    assert rel[70.0] < rel[60.0] and rel[70.0] < 1.0  # 44 % (low against 77 %: see spec)


def test_3_heat_kills_amylase_before_protease_hasegawa_2016() -> None:
    # shio-koji, 13 % salt, 96 h: amylase ~gone at 55 °C, protease loses less; 45 °C < 55 °C
    left = {}
    for t in (45.0, 55.0):
        tr = _run({"starch": 150.0, "protein": 30.0}, 13.0, _const(t), [4.0], koji=0.5)
        left[t] = (_left(tr, "amylase"), _left(tr, "protease", "protease_ts"))
    assert left[55.0][0] < 0.1
    assert left[55.0][1] > left[55.0][0]
    assert left[45.0][0] > left[55.0][0] and left[45.0][1] > left[55.0][1]


def test_4_koji_hydrolysate_su_2005() -> None:
    # koji + 1.5 vol water, 5 % NaCl, 48 h at 45 °C: amino N / soluble N 0.43, and 45 °C
    # solubilises more than 55 °C over 48 h (the protease's "critical temperature")
    sol = {}
    for t in (45.0, 55.0):
        tr = _run({"starch": 120.0, "protein": 60.0}, 5.0, _const(t), [2.0], koji=0.4)
        sol[t] = _soluble(tr)
        if t == 45.0:
            assert 0.3 <= _share(tr, "amino_acids", "protein") / sol[t] <= 0.55
    assert sol[45.0] > sol[55.0]


def _ohnishi_miso(days: list[float]) -> Trajectories:
    # shinshu rice miso: 21.7 % water-phase salt, koji ratio 60 % (~0.3 of the mash), a
    # paste; 32 °C for 25 days, then 20 °C
    sched = TemperatureSchedule([0.0, 600.0, 612.0], [32.0, 32.0, 20.0], [0.0] * 3)
    rec = {"starch": 190.0, "protein": 120.0, "hexoses": 5.0}
    return _run(rec, 21.7, sched, days, koji=0.3, access=0.5)


def test_5_miso_two_step_proteolysis_ohnishi_1982() -> None:
    # at ~90 d: soluble N / total N 55-60 %, formol (free amino) N / total N ~20 %
    tr = _ohnishi_miso([90.0])
    assert 0.45 <= _soluble(tr) <= 0.7
    assert 0.12 <= _share(tr, "amino_acids", "protein") <= 0.3
    assert _share(tr, "starch", "starch") < 0.2  # saccharified in weeks


def _days_to_soluble(temp_c: float, target: float) -> float:
    rec = {"starch": 190.0, "protein": 120.0, "hexoses": 5.0}
    days = list(np.arange(5.0, 725.0, 5.0))
    tr = _run(rec, 20.0, _const(temp_c), days, koji=0.4, access=0.5)
    sol = np.array([_soluble(tr, i) for i in range(1, len(days) + 1)])
    return float(np.interp(target, sol, days))


def test_6_warm_brewing_matures_miso_3_to_5_times_faster_kusumoto_2021() -> None:
    # ~3 months at 30 °C against ~1 year unheated (ratio 3-5). The model gives ~2.6 against
    # a constant 15 °C; real unheated miso sits through a cold winter and a warm summer.
    ratio = _days_to_soluble(15.0, 0.6) / _days_to_soluble(30.0, 0.6)
    assert 2.2 <= ratio <= 6.0


@pytest.mark.parametrize("temp_c", [30.0, 35.0])
def test_9_traditional_fish_sauce_udomsil(temp_c: float) -> None:
    # anchovy, 25 % salt, 30-35 °C, 180 d: amino N / total N ~0.5-0.6, most N soluble
    tr = _run({"protein": 150.0}, 26.0, _const(temp_c), [180.0], fish=1.0)
    assert 0.4 <= _share(tr, "amino_acids", "protein") <= 0.75
    assert _soluble(tr) >= 0.7


def test_10_fish_sauce_faster_at_50_than_35_lopetcharat_2002() -> None:
    sol = {
        t: _soluble(_run({"protein": 150.0}, 26.0, _const(t), [15.0], fish=1.0))
        for t in (35.0, 50.0)
    }
    assert sol[50.0] > 1.4 * sol[35.0]


def test_inactivation_combines_slow_loss_and_heat_denaturation() -> None:
    # protease half-lives at the medians: months at 25 °C, hours at 60 °C
    e = enzymes.PROTEASE
    ep = EnzymeParams(
        k=np.ones(1),
        ea=np.full(1, e.ea_kj.median * 1e3),
        kd_ref=np.full(1, np.log(2) / e.t_half_h.median),
        t_ref_k=e.t_ref_c + 273.15,
        ed=np.full(1, e.ed_kj.median * 1e3),
        floor=np.full(1, e.floor_25.median),
    )
    t_half = {t: float(np.log(2) / ep.inactivation(np.array([t]))[0]) for t in (25.0, 55.0, 60.0)}
    assert t_half[25.0] > 60 * 24
    assert t_half[55.0] == pytest.approx(e.t_half_h.median, rel=0.05)  # + slow loss
    assert t_half[60.0] < 6.0
    assert arrhenius(np.array([50.0]), 50e3)[0] == pytest.approx(1.0)


def test_salt_hits_protease_hardest_fish_enzymes_least() -> None:
    f = {
        c.key: float(enzymes.salt_factor(20.0, np.array([c.salt_s50.median]), c.salt_floor)[0])
        for c in enzymes.CLASSES
    }
    assert f["protease"] < f["peptidase"] < f["amylase"]
    assert f["protease"] < f["fish_enzyme"]
    assert 0.4 <= float(enzymes.salt_factor(25.0, np.array([25.0]), 0.0)[0]) <= 0.6  # Siringan


# ── full forecasts ──────────────────────────────────────────────────────


def test_7_8_koji_temperature_shifts_the_enzyme_mix() -> None:
    # Narahara 1982 / Kitano 2002 / Kusumoto 2021: A. oryzae grows best near 38 °C, yet
    # protease is made more at 30 °C; amylase is not suppressed warm. Chancharoonpong 2012:
    # protease keeps rising after growth stops (72 h > 48 h at 30 °C).
    cool, warm = _forecast("koji", 30.0), _forecast("koji", 38.0)
    assert _at(cool, "protease", 48) > 1.3 * _at(warm, "protease", 48)
    assert _at(warm, "amylase", 48) > _at(cool, "amylase", 48)
    assert _at(warm, "mycelium", 30) > _at(cool, "mycelium", 30)
    assert _at(cool, "protease", 72) > _at(cool, "protease", 48)
    t = _milestone(_forecast("koji", 40.0), "mycelium_90pct")["t_h"]
    assert t["p50"] is not None  # sake-koji temperatures still grow koji


def _final(b: Any, key: str) -> float:
    return _at(b, key, 84 * 24) / _at(b, "protein", 0)


def test_koji_garum_hot_front_loads_but_45_ends_richer() -> None:
    # Review § 3: at 60 °C most koji enzymes denature within days, so breakdown front-loads;
    # 45-50 °C ends higher in free amino acids after 12 weeks.
    hot, mid = _forecast("garum", 60.0), _forecast("garum", 45.0)
    assert _final(mid, "amino_acids") > 1.5 * _final(hot, "amino_acids")
    early = _at(hot, "soluble_protein", 7 * 24) / _at(hot, "soluble_protein", 84 * 24)
    assert early > 0.6
    assert _at(hot, "amylase", 48) < 5.0  # % of a koji: gone within two days


def test_miso_forecast_series_and_milestones() -> None:
    b = _forecast("miso", 25.0)
    keys = {s["key"] for s in b["series"]}
    assert {"soluble_protein", "amino_acids", "amylase", "protease", "peptidase"} <= keys
    assert "fish_enzyme" not in keys
    soluble = _milestone(b, "protein_50pct_soluble")["t_h"]["p50"]
    free = _milestone(b, "free_amino_15pct")["t_h"]["p50"]
    assert soluble is not None and 20 * 24 <= soluble <= 120 * 24
    assert free is not None
    warm = _milestone(_forecast("miso", 30.0), "protein_50pct_soluble")["t_h"]["p50"]
    assert warm is not None and warm < soluble
