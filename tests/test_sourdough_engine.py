"""Sourdough engine: catalogue integrity and the published behaviours the priors are pinned
to (docs/superpowers/specs/2026-09-28-sourdough-engine-design.md § 5)."""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from fermenttrack.prediction.bake import BakeInputs, feeding_chart, forecast
from fermenttrack.prediction.organisms import ORGANISM_KINETICS
from fermenttrack.prediction.sourdough import (
    FLOURS,
    STYLES,
    SourdoughModel,
    blend,
    compile_plan,
    plan_from_dict,
)


def _levain(style: str, ratio: float, temp: float, hydration: float = 100.0,
            flour: str = "t65", **extra: object) -> dict:  # fmt: skip
    return {
        "style": style,
        "levain": {
            "seed_g": 20, "flour_g": 20 * ratio, "water_g": 20 * ratio * hydration / 100,
            "flour": {flour: 1}, "temperature_c": temp,
        },
        **extra,
    }  # fmt: skip


def _run(d: dict, **kw: object) -> dict:
    return forecast(plan_from_dict(d), BakeInputs(plan=d, **kw))  # type: ignore[arg-type]


def _ms(out: dict, key: str) -> dict:
    return next(m for m in out["milestones"] if m["key"] == key)["t_h"]


def _series(out: dict, key: str) -> dict:
    return next(s for s in out["series"] if s["key"] == key)


def _median_member(d: dict, horizon: float = 40.0):
    c = compile_plan(plan_from_dict(d))
    m = SourdoughModel(c, [0.0])
    t = np.linspace(0.0, horizon, 401)
    return m, t, m.simulate_z(np.zeros((1, m.dim)), t)


def test_catalogue_is_consistent() -> None:
    for s in STYLES.values():
        assert set(s.organisms) <= set(ORGANISM_KINETICS), s.key
        assert s.flour in FLOURS
    for f in FLOURS.values():
        assert 0.3 < f.ash_pct < 2.0 and 0 < f.gluten <= 1.0
    assert blend({"t65": 3, "t150": 1}) == (("t150", 0.25), ("t65", 0.75))
    with pytest.raises(ValueError):
        blend({"t999": 1})
    with pytest.raises(ValueError):
        plan_from_dict({"style": "nope", "levain": None})
    with pytest.raises(ValueError):  # Type III has no levain and needs yeast
        plan_from_dict({"style": "type_iii", "levain": None, "dough": {
            "flour_g": 500, "water_g": 350, "salt_g": 10, "temperature_c": 25}})


def test_home_starter_peaks_near_baker_timings() -> None:
    # King Arthur 2025 (25.6 °C, 100 %): 1:1:1 peaks in 4-8 h, 1:4:4 in ~12 h
    fast = _run(_levain("home_starter", 1, 25.6))
    slow = _run(_levain("home_starter", 4, 25.6))
    p1, p4 = _ms(fast, "levain_peak"), _ms(slow, "levain_peak")
    # Known gap (spec § 5): the prior median is ~1.5-2x slower than vigorous home starters;
    # the 90 % band reaches them, and a baker's own jar readings recalibrate it.
    assert p1["p05"] <= 7.0 and p1["p50"] <= 14.0
    assert p4["p05"] <= 12.0 <= p4["p95"]
    assert p1["p50"] < p4["p50"]
    assert _ms(fast, "levain_doubled")["p05"] <= 5.0
    # ripe white levain: pH ~3.8-4.3 and a peak rise between doubled and ~tripled
    i = int(np.argmax(_series(fast, "rise")["p50"]))
    assert 3.7 <= _series(fast, "ph")["p50"][i] <= 4.5
    assert 90.0 <= _series(fast, "rise")["p50"][i] <= 250.0


def test_feeding_chart_is_monotone_in_ratio_and_temperature() -> None:
    fl = blend("t65")
    warm = feeding_chart("home_starter", fl, 100.0, 27.0, "ripe", (1.0, 5.0, 10.0), {})
    cool = feeding_chart("home_starter", fl, 100.0, 21.0, "ripe", (1.0, 5.0, 10.0), {})
    w = [r["peak_h"]["p50"] for r in warm["rows"]]
    c = [r["peak_h"]["p50"] for r in cool["rows"]]
    assert w == sorted(w) and c == sorted(c)
    assert all(a < b for a, b in zip(w, c, strict=True))
    assert warm["rows"][1]["label"] == "1:5:5"


def test_stiff_and_cool_are_more_acetic() -> None:
    def fq(d: dict) -> float:
        m, t, tr = _median_member(d, 24.0)
        return float(tr.extra["fq"][0, -1])

    liquid = fq(_levain("levain_liquide", 3, 26, hydration=125))
    stiff = fq(_levain("levain_liquide", 3, 26, hydration=55))
    assert stiff < liquid / 1.5  # Minervini 2014: FQ 6.5 (DY 160) vs 15.5 (DY 280)
    warm = fq(_levain("levain_liquide", 3, 30))
    cool = fq(_levain("levain_liquide", 3, 20))
    assert cool < warm


def test_kazachstania_lives_on_glucose_released_by_l_sanfranciscensis() -> None:
    d = _levain("san_francisco", 2.5, 27, hydration=55)
    c = compile_plan(plan_from_dict(d))
    k = c.organisms.index("Kazachstania humilis")
    t = np.linspace(0.0, 12.0, 121)
    m = SourdoughModel(c, [0.0])
    with_lab = m.simulate_z(np.zeros((1, m.dim)), t)
    alone = dataclasses.replace(c, organisms=["Kazachstania humilis"])
    m_alone = SourdoughModel(alone, [0.0])
    tr_alone = m_alone.simulate_z(np.zeros((1, m_alone.dim)), t)
    grown = math.log10(with_lab.biomass_g[0, -1, k] / with_lab.biomass_g[0, 0, k])
    grown_alone = math.log10(tr_alone.biomass_g[0, -1, 0] / tr_alone.biomass_g[0, 0, 0])
    assert grown > grown_alone + 0.2  # maltose-negative: needs the LAB's glucose


def test_whole_grain_buffers_more_than_white() -> None:
    def tta_ph(flour: str) -> tuple[float, float]:
        _, _, tr = _median_member(_levain("levain_liquide", 3, 26, flour=flour), 16.0)
        return float(tr.extra["tta"][0, -1]), float(tr.ph[0, -1])

    tta_white, ph_white = tta_ph("t65")
    tta_whole, ph_whole = tta_ph("t150")
    assert tta_whole > tta_white * 1.2
    assert ph_whole > ph_white - 0.05  # more acid for about the same pH
    assert 7.0 <= tta_white <= 15.0  # ripe white levain, TTA ~8-12


def _dough(salt_g: float, proof_temp: float | None) -> dict:
    d = _levain("levain_liquide", 5, 24)
    d["dough"] = {"flour_g": 900, "water_g": 630, "salt_g": salt_g, "flour": {"t65": 1},
                  "temperature_c": 25, "target_rise_pct": 50}  # fmt: skip
    if proof_temp is not None:
        d["proof"] = {"temperature_c": proof_temp, "hours": 12}
    return d


def test_dough_phases_salt_and_retard() -> None:
    out = _run(_dough(20, 4))
    keys = [p["key"] for p in out["phases"]]
    assert keys == ["levain", "bulk", "proof"]
    assert out["phases"][2]["label"] == "Cold retard"
    lv, bulk, proof = out["phases"]
    assert lv["end_h"] == bulk["start_h"] and bulk["end_h"] == proof["start_h"]
    assert out["summary"]["salt_pct_of_flour"] == pytest.approx(2.0, abs=0.1)
    # 4 % salt on flour slows the bulk (L. sanfranciscensis stops at ~4 %, Gänzle 1998)
    salty = _run(_dough(40, None))
    plain = _run(_dough(0, None))
    assert _ms(salty, "bulk_target")["p50"] > _ms(plain, "bulk_target")["p50"]
    # in the fridge the jar nearly stops rising (after the ~3 h cool-down)
    rise = _series(out, "rise")
    t = np.asarray(rise["t_h"])
    r = np.asarray(rise["p50"])
    a, b = proof["start_h"] + 4.0, proof["end_h"] - 0.5
    ia, ib = int(np.searchsorted(t, a)), int(np.searchsorted(t, b))
    warm = _run(_dough(20, 24))
    rw = np.asarray(_series(warm, "rise")["p50"])
    assert abs(r[ib] - r[ia]) < 15.0
    assert abs(r[ib] - r[ia]) < abs(rw[ib] - rw[ia]) or rw[ib] < rw[ia]  # warm proof moves (or collapses)


def test_type_iii_and_preferments_run() -> None:
    t3 = {"style": "type_iii", "levain": None, "dough": {
        "flour_g": 500, "water_g": 330, "salt_g": 10, "flour": {"t65": 1}, "temperature_c": 26,
        "yeast_g": 5, "yeast": "fresh", "dried_sour_g": 20, "target_rise_pct": 100}}  # fmt: skip
    out = _run(t3)
    assert [p["key"] for p in out["phases"]] == ["bulk"]
    assert _ms(out, "bulk_target")["p50"] is not None and _ms(out, "bulk_target")["p50"] < 6
    assert _series(out, "ph")["p50"][0] < 5.6  # the powder's acids
    poolish = _run({"style": "poolish", "levain": {"seed_g": 0.5, "flour_g": 500, "water_g": 500,
                    "flour": {"t65": 1}, "temperature_c": 20}})  # fmt: skip
    assert _ms(poolish, "levain_peak")["p50"] is not None
    assert _series(poolish, "ph")["p50"][-1] > 4.6  # yeasted: little acidity


def test_rise_readings_calibrate_the_forecast() -> None:
    d = _levain("home_starter", 5, 24)
    prior = _run(d)
    # a vigorous starter: +100 % at 5 h, well ahead of the prior's median
    calib = _run(d, now_h=5.0, measurements=(("rise", 2.0, 15.0), ("rise", 4.0, 60.0), ("rise", 5.0, 100.0)))
    assert calib["status"] == "calibrated"
    assert _ms(calib, "levain_peak")["p50"] < _ms(prior, "levain_peak")["p50"]
    assert all(o["used"] for o in calib["observations"])
