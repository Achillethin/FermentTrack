"""Aroma in the forecast output: series, palette data, routes."""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.prediction import service
from fermenttrack.prediction.service import RecipeIn, member_values, predict
from fermenttrack.schemas import SensoryOut
from tests.test_aroma_lacto import _per_100g
from tests.test_prediction_sensory import _inputs


@pytest.fixture(autouse=True)
def _fresh() -> None:
    service.clear_caches()


def test_lacto_has_palette_series_and_routes() -> None:
    body = predict(_inputs("lacto_ferment", 20.0), horizon_h=21 * 24)
    SensoryOut.model_validate(body["sensory"])
    s = body["sensory"]
    keys = {r["key"] for r in s["aroma_series"]}
    assert {"green", "sulfurous", "pungent"} <= keys
    for r in s["aroma_series"]:
        assert len(r["noticeable"]) == len(s["taste_phases"]["t_h"])
        assert 0.0 <= r["peak_noticeable"] <= 1.0
    comp = {c["key"]: c for c in s["compounds"]}
    smcso = {"kind": "ingredient", "name": "Cabbage", "via": "S-methylcysteine sulfoxide"}
    assert smcso in comp["dmts"]["routes"]
    assert comp["butenyl_itc"]["tier"] == "calibrated"
    assert comp["allyl_cyanide"]["peak_noticeable"] is None  # conc-only: no threshold
    assert any(x["key"].startswith("odor:") for x in body["series"])


def test_types_without_b1_aroma_say_so() -> None:
    body = predict(_inputs("kombucha", 24.0), horizon_h=14 * 24)
    s = body["sensory"]
    assert s["aroma_series"] == [] and s["compounds"] == []
    assert any("later" in n for n in s["not_modelled_aroma"]["notes"])


def test_aroma_follows_what_if() -> None:
    a = predict(_inputs("lacto_ferment", 18.0), horizon_h=21 * 24)
    b = predict(_inputs("lacto_ferment", 18.0), temperature_c=24.0, horizon_h=21 * 24)
    sa = {r["key"]: r["noticeable"] for r in a["sensory"]["aroma_series"]}
    sb = {r["key"]: r["noticeable"] for r in b["sensory"]["aroma_series"]}
    assert sa.keys() == sb.keys() and sa != sb
    service.clear_caches()
    again = predict(_inputs("lacto_ferment", 18.0), temperature_c=24.0, horizon_h=21 * 24)
    assert again["sensory"]["aroma_series"] == b["sensory"]["aroma_series"]


def test_no_brassica_no_sulfur() -> None:
    recipe = (RecipeIn("Chilies", 980.0, "g", _per_100g("Chilies"), "base"),
              RecipeIn("Salt", 20.0, "g", _per_100g("Salt"), "additive"))  # fmt: skip
    s = predict(_inputs("lacto_ferment", 20.0, recipe), horizon_h=21 * 24)["sensory"]
    keys = {c["key"] for c in s["compounds"]}
    assert not keys & {"allyl_itc", "butenyl_itc", "dmds", "dmts", "dms", "methanethiol"}
    assert {"acetoin", "ethyl_butanoate"} <= keys
    assert s["not_modelled_aroma"]["ingredients"] == ["Chilies"]


def test_every_active_compound_counts_in_the_sums() -> None:
    s = predict(_inputs("lacto_ferment", 20.0), horizon_h=21 * 24)["sensory"]
    for c in s["compounds"]:
        assert c["in_series_sum"] == (c["threshold"] is not None), c["key"]


def test_aroma_values_are_finite_and_non_negative() -> None:
    _, values, _ = member_values(_inputs("lacto_ferment", 24.0), 60 * 24.0)
    assert any(k.startswith("conc:") for k in values)
    for k, v in values.items():
        if k.startswith("conc:"):
            assert np.all(np.isfinite(v)) and np.all(v >= 0.0), k


@pytest.mark.parametrize("step", ["_aroma_values", "_aroma_meta", "_aroma_block"])
def test_an_aroma_failure_keeps_the_forecast_taste_and_nutrition(
    step: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fermenttrack.prediction import derived

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("aroma bug")

    monkeypatch.setattr(derived, step, boom)
    body = predict(_inputs("lacto_ferment", 20.0), horizon_h=21 * 24)
    s = body["sensory"]
    assert s["nutrition_label"] and s["taste_phases"]
    assert any(x["key"].startswith("taste:") for x in body["series"])
    assert s["aroma_series"] == [] and s["compounds"] == []
    if step != "_aroma_block":  # the block is built after the bands (harmless leftovers)
        assert not any(x["group"] == "aroma" for x in body["series"])


def test_peak_day_is_the_strongest_when_the_chance_saturates() -> None:
    from fermenttrack.prediction import derived
    from fermenttrack.prediction.aroma import AromaResult

    v = np.log10(np.array([[2.0, 20.0, 200.0, 50.0], [3.0, 30.0, 300.0, 60.0]]))  # all > 1
    ar = AromaResult(
        conc={}, oav={}, series={"fruity": v}, members={"fruity": []}, compounds=[], routes={},
        tiers={}, not_modelled={"notes": [], "organisms": [], "ingredients": []},
    )  # fmt: skip
    t = np.array([0.0, 24.0, 48.0, 72.0])
    block = derived._aroma_block(ar, t, np.array([0.5, 0.5]), np.arange(4))
    row = block["aroma_series"][0]
    assert row["peak_noticeable"] == 1.0 and row["peak_t_h"] == 48.0
