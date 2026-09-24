"""Prediction service: inference behaviour, recipe/reading handling, output shape, caching."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction import inference
from fermenttrack.prediction.service import (
    MeasurementIn,
    OrganismIn,
    PredictionInputs,
    RecipeIn,
    predict,
)

CABBAGE = {
    "water": 92.2, "protein": 1.28, "carbohydrate": 5.8, "fiber": 2.5, "sugars_total": 3.2,
    "sucrose": 0.08, "glucose": 1.67, "fructose": 1.45, "sodium": 0.018,
}  # fmt: skip
SALT = {"water": 0.2, "sodium": 38.8}
RICE = {"water": 12.9, "protein": 6.5, "carbohydrate": 79.3, "fiber": 2.8, "sodium": 0.001}


def _inputs(
    ferment: str = "lacto_ferment",
    recipe: tuple[RecipeIn, ...] = (),
    measurements: tuple[MeasurementIn, ...] = (),
    now_h: float = 0.0,
    temp: float | None = 20.0,
    organisms: list[str] | None = None,
) -> PredictionInputs:
    names = organisms if organisms is not None else FERMENTATION_TYPE_ORGANISMS[ferment]
    return PredictionInputs(
        fermentation_type=ferment,
        now_h=now_h,
        expected_temperature_c=temp,
        organisms=tuple(OrganismIn(n, ORGANISMS.get(n, "bacteria"), ()) for n in names),
        organism_source="default" if organisms is None else "custom",
        recipe=recipe,
        measurements=measurements,
    )


def _kraut(n_ph: int = 0) -> PredictionInputs:
    readings = [(1.0, 6.1), (24.0, 5.2), (48.0, 4.3)][:n_ph]
    return _inputs(
        recipe=(
            RecipeIn("Cabbage", 1000, "g", CABBAGE, "base"),
            RecipeIn("Salt", 20, "g", SALT, "additive"),
        ),
        measurements=tuple(MeasurementIn("pH", t, v) for t, v in readings),
        now_h=50.0 if n_ph else 0.0,
    )


def _series(body: Any, key: str) -> Any:
    return next(s for s in body["series"] if s["key"] == key)


def _at(body: Any, key: str, t_h: float, q: str = "p50") -> float:
    s = _series(body, key)
    return float(np.interp(t_h, s["t_h"], s[q]))


def test_weighted_quantiles() -> None:
    v = np.array([1.0, 2.0, 3.0, 4.0])
    q = inference.weighted_quantiles(v, np.full(4, 0.25), (0.25, 0.5, 1.0))
    assert list(q) == [1.0, 2.0, 4.0]
    heavy = inference.weighted_quantiles(v, np.array([0.0, 0.0, 0.0, 1.0]), (0.05,))
    assert heavy[0] == 4.0


def test_prior_only_output_shape() -> None:
    body = predict(_kraut())
    assert body["status"] == "prior_only"
    assert body["model"]["effective_members"] == pytest.approx(body["model"]["members"])
    assert body["model"]["validated"] is False
    for s in body["series"]:
        assert len(s["t_h"]) == len(s["p05"]) == len(s["p50"]) == len(s["p95"])
        bands = zip(s["p05"], s["p50"], s["p95"], strict=True)
        assert all(a <= b + 1e-9 <= c + 2e-9 for a, b, c in bands)
    assert body["reference_lines"] == [
        {"series": "ph", "value": 4.6, "label": "4.6 food-safety reference"}
    ]
    assert body["initial"]["source"] == "recipe"
    assert body["initial"]["values"]["salt_water_phase_pct"] == pytest.approx(2.1, abs=0.1)
    assert body["initial"]["values"]["sugars_total"] == pytest.approx(31.4, abs=0.5)
    m = body["milestones"][0]
    assert m["title"] == "pH below 4.6" and m["threshold"] == {
        "series": "ph", "value": 4.6, "kind": "below"
    }  # fmt: skip
    assert "safe by" not in m["label"].lower() and " is safe" not in m["label"].lower()


def test_readings_pull_the_forecast_and_narrow_it() -> None:
    prior = predict(_kraut(0))
    post = predict(_kraut(3))
    assert post["status"] == "calibrated"
    assert post["model"]["effective_members"] >= inference.MIN_ESS
    # the posterior passes near the readings...
    assert abs(_at(post, "ph", 48.0) - 4.3) < abs(_at(prior, "ph", 48.0) - 4.3)
    assert _at(post, "ph", 48.0) == pytest.approx(4.3, abs=0.35)
    # ...and the band at the last reading is narrower than the prior's
    width = lambda b: _at(b, "ph", 48.0, "p95") - _at(b, "ph", 48.0, "p05")  # noqa: E731
    assert width(post) < width(prior)
    assert [o["used"] for o in post["observations"]] == [True, True, True]


def test_what_if_temperature_moves_milestones() -> None:
    base = _kraut(2)
    cold = predict(base, temperature_c=15.0)
    warm = predict(base, temperature_c=26.0)
    assert cold["temperature"]["source"] == warm["temperature"]["source"] == "override"
    t = lambda b: b["milestones"][1]["t_h"]["p50"] or 1e9  # noqa: E731  pH below 4.0
    assert t(warm) < t(cold)


def test_cache_returns_identical_results() -> None:
    a = predict(_kraut(2))
    b = predict(_kraut(2))
    assert a == b


def test_missing_recipe_falls_back_to_typical_with_warning() -> None:
    body = predict(_inputs("kombucha", temp=24.0))
    assert body["initial"]["source"] == "typical_recipe"
    assert any("typical kombucha recipe" in w for w in body["warnings"])
    assert any("starter" in a.lower() for a in body["assumptions"])


def test_starch_is_estimated_and_dry_weights_get_water() -> None:
    rice = (RecipeIn("White rice", 1, "kg", RICE, "base"),)
    body = predict(_inputs("koji", recipe=rice, temp=30))
    assert body["initial"]["source"] == "recipe"
    assert body["initial"]["values"]["starch"] > 400.0
    assert any("Starch estimated" in a for a in body["assumptions"])
    assert any("dry weights" in w for w in body["warnings"])


def test_temperature_readings_drive_the_past_and_fahrenheit_is_ignored() -> None:
    body = predict(
        _inputs(
            measurements=(
                MeasurementIn("temperature", 5.0, 18.0),
                MeasurementIn("temperature", 9.0, 68.0),  # °F by mistake
            ),
            now_h=10.0,
            temp=None,
        )
    )
    assert body["temperature"]["source"] == "measured"
    assert body["temperature"]["forecast_c"] == 18.0
    assert body["temperature"]["readings"] == 1
    assert any("°F" in w for w in body["warnings"])


def test_ispindel_plato_and_dense_streams_are_thinned() -> None:
    # an iSpindel in °Plato, ending below 1.5 °P (which alone would pass for SG)
    stream = tuple(MeasurementIn("gravity", h / 4, 7.5 - 0.0165 * h) for h in range(400))
    body = predict(_inputs("kombucha", measurements=stream, now_h=100.0, temp=24.0))
    used = [o for o in body["observations"] if o["used"]]
    assert 0 < len(used) <= 30
    assert all(1.0 < o["value"] < 1.05 for o in used)  # converted to SG
    assert body["status"] == "calibrated"


def test_density_readings_are_not_used_for_milk() -> None:
    body = predict(_inputs("kefir", measurements=(MeasurementIn("brix", 2.0, 12.0),), now_h=3.0))
    assert [o["used"] for o in body["observations"]] == [False]
    assert body["status"] == "prior_only"


def test_unknown_and_airless_organisms_are_reported() -> None:
    body = predict(
        _inputs(organisms=["Lactobacillus plantarum", "Acetobacter aceti", "Mystery bug"])
    )
    by_name = {o["name"]: o for o in body["organisms"]}
    assert by_name["Mystery bug"]["modelled"] is False
    assert by_name["Acetobacter aceti"]["growing"] is False
    assert "air" in by_name["Acetobacter aceti"]["note"]
    assert by_name["Lactobacillus plantarum"]["series_key"] == "pop:Lactobacillus plantarum"
    assert any("Mystery bug" in w for w in body["warnings"])


def test_pathways_report_kegg_backing() -> None:
    base = _inputs(organisms=["Lactobacillus plantarum"])
    lp = OrganismIn("Lactobacillus plantarum", "bacteria", ("1.1.1.27",))
    inputs = PredictionInputs(**{**base.__dict__, "organisms": (lp,)})
    body = predict(inputs)
    (path,) = body["organisms"][0]["pathways"]
    assert path["in_reference_graph"] is True
    assert "1.1.1.27" in path["ec_numbers"]


def test_exploratory_types_say_so() -> None:
    body = predict(_inputs("miso", temp=25.0))
    assert body["model"]["confidence"] == "exploratory"
    assert any(w.startswith("Exploratory") for w in body["warnings"])
    assert body["reference_lines"] == []


def test_horizon_is_respected_and_old_batches_stay_in_window() -> None:
    body = predict(_kraut(), horizon_h=100.0)
    assert body["horizon_h"] == 100.0 and _series(body, "ph")["t_h"][-1] == 100.0
    old = predict(_inputs(now_h=40 * 24))
    assert old["horizon_h"] > 40 * 24
    assert old["horizon_h"] in old["horizon_options_h"]
