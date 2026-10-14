"""Engine hooks for the recommender (recommender design § 9): a planned temperature schedule
and the ensemble size.

The PINNED_* values were recorded on the engine before these hooks existed: with no plan and
no `members`, fingerprints, seeds, schedules and forecasts must not move. Forecast numbers
are compared to their last printed digit (ODE results may differ in the last bit across
platforms); any real change to a seed or a schedule moves them far more.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.service import (
    MeasurementIn,
    OrganismIn,
    PredictionInputs,
    RecipeIn,
    _schedule,
    clear_caches,
    member_values,
    population_samples,
    predict,
)

CABBAGE = {
    "water": 92.2, "protein": 1.28, "carbohydrate": 5.8, "fiber": 2.5, "sugars_total": 3.2,
    "sucrose": 0.08, "glucose": 1.67, "fructose": 1.45, "sodium": 0.018,
}  # fmt: skip
SALT = {"water": 0.2, "sodium": 38.8}
LACTO = PROFILES["lacto_ferment"]
STAGED = ((0.0, 20.0), (48.0, 4.0))  # a recipe's "0:20;48:4": a day or two warm, then cold
H = 240.0  # forecast window for the behaviour tests (keeps them quick)


def _kraut(
    measurements: tuple[MeasurementIn, ...] = (),
    now_h: float = 0.0,
    temp: float | None = 20.0,
    plan: tuple[tuple[float, float], ...] = (),
) -> PredictionInputs:
    names = FERMENTATION_TYPE_ORGANISMS["lacto_ferment"]
    return PredictionInputs(
        fermentation_type="lacto_ferment",
        now_h=now_h,
        expected_temperature_c=temp,
        organisms=tuple(OrganismIn(n, ORGANISMS.get(n, "bacteria"), ()) for n in names),
        organism_source="default",
        recipe=(
            RecipeIn("Cabbage", 1000, "g", CABBAGE, "base"),
            RecipeIn("Salt", 20, "g", SALT, "additive"),
        ),
        measurements=measurements,
        planned_temperature=plan,
    )


READINGS = (
    MeasurementIn("temperature", 2.0, 22.0),
    MeasurementIn("temperature", 30.0, 18.0),
    MeasurementIn("pH", 1.0, 6.1),
    MeasurementIn("pH", 24.0, 5.2),
    MeasurementIn("pH", 48.0, 4.3),
)
PRIOR = _kraut()
CALIBRATED = _kraut(READINGS, now_h=50.0, temp=None)

PINNED_FINGERPRINTS = {
    "prior": "d4aeb25a7020c94da1215bf77c5dab527cb1705e69241c64c66ac8914e05640a",
    "calibrated": "25ca852f8a4e9584ecb9d4acf4acb1f9112955fb3f13ca5b3fef1c73155d8aa0",
}
# _schedule(CALIBRATED, lacto, None, 672.0): t_h, temp_c, estimated, forecast, source, n, ignored
PINNED_SCHEDULE = (
    [0.0, 2.0, 14.0, 18.0, 30.0, 50.0, 50.01, 672.0],
    [22.0, 22.0, 20.0, 20.0, 18.0, 18.0, 18.0, 18.0],
    [0.5, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0],
    18.0, "measured", 2, 0,
)  # fmt: skip
# pH p50 at grid points 20, 40, 80, 160; pH p05 at 160; lactic acid p50 at 40, 80, 160
PINNED_FORECASTS: dict[str, dict[str, Any]] = {
    "prior": {
        "members": 160, "ess": 160.0,
        "ph_p50": [5.063, 4.169, 3.848, 3.727], "ph_p05_end": 3.46,
        "lactic_p50": [8.276, 12.597, 15.242],
        "milestones": {"ph_below_4_6": 109.81, "ph_below_4_0": 225.1, "sugars_90pct_used": None,
                       "taste_tangy": 73.5, "taste_sour": 186.9},
        "temperature": {"forecast_c": 20.0, "source": "expected", "type_default_c": 20.0,
                        "range_c": [16.0, 24.0], "readings": 0},
        "assumption": "Temperature: your estimate of 20 °C from now on.",
    },
    "what_if_25": {
        "members": 128, "ess": 128.0,
        "ph_p50": [4.363, 3.895, 3.72, 3.641], "ph_p05_end": 3.394,
        "lactic_p50": [11.651, 15.421, 17.173],
        "milestones": {"ph_below_4_6": 70.8, "ph_below_4_0": 135.43, "sugars_90pct_used": None,
                       "taste_tangy": 52.5, "taste_sour": 111.3},
        "temperature": {"forecast_c": 25.0, "source": "override", "type_default_c": 20.0,
                        "range_c": [16.0, 24.0], "readings": 0},
        "assumption": "Temperature: what-if: 25 °C from now on (not saved).",
    },
    "calibrated": {
        "members": 400, "ess": 15.0,
        "ph_p50": [4.414, 4.062, 3.824, 3.675], "ph_p05_end": 3.451,
        "lactic_p50": [8.423, 12.358, 14.259],
        "milestones": {"ph_below_4_6": 68.29, "ph_below_4_0": 185.01, "sugars_90pct_used": None,
                       "taste_tangy": 56.7, "taste_sour": 186.9},
        "temperature": {"forecast_c": 18.0, "source": "measured", "type_default_c": 20.0,
                        "range_c": [16.0, 24.0], "readings": 2},
        "assumption": "Temperature: 18 °C from now on (your last reading; no estimate set); "
                      "your 2 logged temperature reading(s) for the past.",
    },
}  # fmt: skip
PINNED_MEMBER_VALUES = {"members": 160, "times": 161, "ph_mean_at_120h": 4.552903}


@pytest.fixture(autouse=True)
def _cold_caches() -> None:
    clear_caches()  # pins and cache tests need a known cache state


def _series(body: dict[str, Any], key: str) -> dict[str, Any]:
    return next(s for s in body["series"] if s["key"] == key)


def _at(body: dict[str, Any], key: str, t_h: float) -> float:
    s = _series(body, key)
    return float(np.interp(t_h, s["t_h"], s["p50"]))


def _temp_at(sched: Any, t_h: float) -> tuple[float, float]:
    """(°C, estimated) of a TemperatureSchedule at an hour."""
    return (
        float(np.interp(t_h, sched.t_h, sched.temp_c)),
        float(np.interp(t_h, sched.t_h, sched.estimated)),
    )


def _assert_pinned(body: dict[str, Any], pin: dict[str, Any]) -> None:
    ph, lactic = _series(body, "ph"), _series(body, "lactic_acid")
    assert body["model"]["members"] == pin["members"]
    assert body["model"]["effective_members"] == pytest.approx(pin["ess"], abs=0.1)
    assert [ph["p50"][i] for i in (20, 40, 80, 160)] == pytest.approx(pin["ph_p50"], abs=2e-3)
    assert ph["p05"][160] == pytest.approx(pin["ph_p05_end"], abs=2e-3)
    assert [lactic["p50"][i] for i in (40, 80, 160)] == pytest.approx(
        pin["lactic_p50"], abs=2e-3
    )
    milestones = {m["key"]: m["t_h"]["p50"] for m in body["milestones"]}
    assert milestones.keys() == pin["milestones"].keys()
    for key, want in pin["milestones"].items():
        assert milestones[key] == (None if want is None else pytest.approx(want, abs=0.02))
    assert body["temperature"] == pin["temperature"]
    assert pin["assumption"] in body["assumptions"]


# ── an empty plan and no `members` change nothing ───────────────────────


def test_an_empty_plan_keeps_the_pinned_fingerprints() -> None:
    assert PRIOR.fingerprint() == PINNED_FINGERPRINTS["prior"]
    assert CALIBRATED.fingerprint() == PINNED_FINGERPRINTS["calibrated"]
    assert replace(PRIOR, planned_temperature=()).fingerprint() == PINNED_FINGERPRINTS["prior"]
    planned = _kraut(plan=STAGED).fingerprint()
    assert planned != PINNED_FINGERPRINTS["prior"]
    # one plan, one fingerprint (and seed), however its steps are typed or ordered
    assert _kraut(plan=((48, 4), (0, 20))).fingerprint() == planned


def test_an_empty_plan_keeps_the_pinned_schedule() -> None:
    sched, *rest = _schedule(CALIBRATED, LACTO, None, 672.0)
    assert (sched.t_h, sched.temp_c, sched.estimated, *rest) == PINNED_SCHEDULE


def test_an_empty_plan_keeps_the_pinned_forecast() -> None:
    _assert_pinned(predict(PRIOR), PINNED_FORECASTS["prior"])


def test_an_empty_plan_keeps_the_pinned_what_if() -> None:
    _assert_pinned(predict(PRIOR, temperature_c=25.0), PINNED_FORECASTS["what_if_25"])


def test_an_empty_plan_keeps_the_pinned_calibrated_forecast() -> None:
    _assert_pinned(predict(CALIBRATED), PINNED_FORECASTS["calibrated"])


def test_an_empty_plan_keeps_the_pinned_member_values() -> None:
    t, values, w = member_values(PRIOR, H)
    assert values["ph"].shape == (PINNED_MEMBER_VALUES["members"], PINNED_MEMBER_VALUES["times"])
    i = int(np.searchsorted(t, 120.0))
    assert float(np.sum(w * values["ph"][:, i])) == pytest.approx(
        PINNED_MEMBER_VALUES["ph_mean_at_120h"], abs=1e-4
    )


# ── the planned schedule ────────────────────────────────────────────────


def test_without_readings_the_plan_replaces_the_constant_estimate() -> None:
    # the plan wins over expected_temperature_c, which is only its constant form
    sched, forecast, source, n, _ = _schedule(_kraut(temp=15.0, plan=STAGED), LACTO, None, H)
    for t_h in (0.0, 24.0, 47.98):
        assert _temp_at(sched, t_h) == pytest.approx((20.0, 1.0))
    for t_h in (48.0, 100.0, H):
        assert _temp_at(sched, t_h) == pytest.approx((4.0, 1.0))
    assert (forecast, source, n) == (20.0, "expected", 0)
    # a plan whose first step starts late still covers the hours before it
    late, *_ = _schedule(_kraut(plan=((12.0, 18.0), (48.0, 4.0))), LACTO, None, H)
    assert _temp_at(late, 6.0) == pytest.approx((18.0, 1.0))


def test_a_one_stage_plan_is_the_constant_estimate() -> None:
    # planned knots are estimated exactly like the constant estimate (same temperature offset)
    planned, *p_rest = _schedule(_kraut(temp=None, plan=((0.0, 20.0),)), LACTO, None, H)
    constant, *c_rest = _schedule(_kraut(temp=20.0), LACTO, None, H)
    assert (planned.t_h, planned.temp_c, planned.estimated) == (
        constant.t_h, constant.temp_c, constant.estimated,
    )  # fmt: skip
    assert p_rest == c_rest


def test_the_what_if_replaces_only_the_first_stage() -> None:
    sched, forecast, source, _, _ = _schedule(_kraut(plan=STAGED), LACTO, 25.0, H)
    # the what-if stage is exact (no offset), like a constant what-if
    assert _temp_at(sched, 24.0) == pytest.approx((25.0, 0.0))
    assert _temp_at(sched, 47.98) == pytest.approx((25.0, 0.0))
    for t_h in (48.0, 100.0, H):  # the later stage is kept, still an estimate
        assert _temp_at(sched, t_h) == pytest.approx((4.0, 1.0))
    assert (forecast, source) == (25.0, "override")


def test_readings_set_the_past_and_the_plan_the_future() -> None:
    plan = ((0.0, 20.0), (48.0, 4.0), (100.0, 10.0))
    temps = tuple(m for m in READINGS if m.type == "temperature")  # 22 °C at 2 h, 18 °C at 30 h
    inputs = _kraut(temps, now_h=50.0, temp=None, plan=plan)
    sched, forecast, source, n, _ = _schedule(inputs, LACTO, None, H)
    assert _temp_at(sched, 2.0) == pytest.approx((22.0, 0.0))
    assert _temp_at(sched, 30.0) == pytest.approx((18.0, 0.0))
    assert _temp_at(sched, 16.0) == pytest.approx((20.0, 1.0))  # a gap: the plan, not the mean
    assert _temp_at(sched, 60.0) == pytest.approx((4.0, 1.0))
    assert _temp_at(sched, 120.0) == pytest.approx((10.0, 1.0))
    assert (forecast, source, n) == (4.0, "expected", 2)
    # mid-plan, a what-if replaces the stage in effect now (the first one still ahead)
    what_if, forecast, source, _, _ = _schedule(inputs, LACTO, 25.0, H)
    assert _temp_at(what_if, 60.0) == pytest.approx((25.0, 0.0))
    assert _temp_at(what_if, 120.0) == pytest.approx((10.0, 1.0))
    assert _temp_at(what_if, 30.0) == pytest.approx((18.0, 0.0))  # the past is not changed
    assert (forecast, source) == (25.0, "override")


def test_a_staged_plan_slows_acidification_after_48_h() -> None:
    constant = predict(_kraut(temp=20.0), horizon_h=H, members=64)
    staged = predict(_kraut(temp=None, plan=STAGED), horizon_h=H, members=64)

    def rise(body: dict[str, Any]) -> float:
        return _at(body, "lactic_acid", H) - _at(body, "lactic_acid", 48.0)

    assert rise(staged) < 0.25 * rise(constant)
    assert _at(staged, "ph", H) > _at(constant, "ph", H) + 0.5
    assert staged["temperature"] == {**constant["temperature"], "source": "expected"}
    assert (
        "Temperature: your plan: 20 °C from the start, then 4 °C from hour 48."
        in staged["assumptions"]
    )


def test_a_what_if_on_a_plan_shifts_the_first_stage_only() -> None:
    planned = _kraut(temp=None, plan=STAGED)
    base = predict(planned, horizon_h=H, members=64)
    warm = predict(planned, temperature_c=25.0, horizon_h=H, members=64)
    constant_warm = predict(_kraut(temp=20.0), temperature_c=25.0, horizon_h=H, members=64)
    # warmer first stage: more acid by 48 h than the plan (the same 64 members, re-simulated)
    assert _at(warm, "lactic_acid", 48.0) > _at(base, "lactic_acid", 48.0) + 0.5
    # the 4 °C stage is kept: after 48 h it barely acidifies, unlike a constant 25 °C what-if

    def rise(body: dict[str, Any]) -> float:
        return _at(body, "lactic_acid", H) - _at(body, "lactic_acid", 48.0)

    assert rise(warm) < 0.25 * rise(constant_warm)
    assert warm["temperature"]["source"] == "override"
    assert (
        "Temperature: what-if: 25 °C from now until hour 48, then your plan (not saved)."
        in warm["assumptions"]
    )


# ── the ensemble size ───────────────────────────────────────────────────


def test_members_sets_the_ensemble_size() -> None:
    t, values, w = member_values(PRIOR, H, members=64)
    assert values["ph"].shape == (64, len(t)) and w.shape == (64,)
    assert all(v.shape[0] == 64 for v in values.values())
    assert predict(PRIOR, horizon_h=H, members=64)["model"]["members"] == 64
    # with its posterior cached, the resampled paths keep the size too
    assert predict(PRIOR, temperature_c=25.0, horizon_h=H, members=64)["model"]["members"] == 64
    _, warm, warm_w = member_values(PRIOR, H, members=64)
    assert warm["ph"].shape[0] == 64 and warm_w.shape == (64,)


def test_members_are_isolated_in_the_caches() -> None:
    small_first = predict(PRIOR, horizon_h=H, members=64)
    default = predict(PRIOR, horizon_h=H)
    assert (small_first["model"]["members"], default["model"]["members"]) == (64, 160)
    clear_caches()
    assert predict(PRIOR, horizon_h=H) == default
    # a 160-member posterior in the cache is not served (nor resampled) for 64 members, so
    # the result does not depend on which size ran first; and the reverse
    small_after = predict(PRIOR, horizon_h=H, members=64)
    assert small_after == small_first
    assert predict(PRIOR, horizon_h=H) == default


def test_only_the_default_ensemble_feeds_population_learning() -> None:
    finished = replace(PRIOR, finished=True)
    predict(finished, horizon_h=H, members=64)
    assert population_samples(finished) is None
    predict(finished, horizon_h=H)
    assert population_samples(finished) is not None
