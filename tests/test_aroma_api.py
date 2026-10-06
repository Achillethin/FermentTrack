"""Aroma in the forecast output: series, palette data, routes."""

from __future__ import annotations

import pytest

from fermenttrack.prediction import service
from fermenttrack.prediction.service import predict
from fermenttrack.schemas import SensoryOut
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
