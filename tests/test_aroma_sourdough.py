"""Sourdough aroma: chained phases (bake plans) and curation § 7 tests 14-15."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from fermenttrack.prediction import aroma, bake, service
from fermenttrack.prediction.bake import BakeInputs, forecast
from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.service import RecipeIn
from fermenttrack.prediction.sourdough import Compiled, SourdoughModel, compile_plan, plan_from_dict
from fermenttrack.schemas import SensoryOut
from tests.test_aroma_lacto import At, _per_100g
from tests.test_prediction_sensory import _inputs

SD = PROFILES["sourdough"]


def _plan(flour: str = "t65", proof: float | None = 4.0) -> dict[str, Any]:
    d: dict[str, Any] = {
        "style": "levain_liquide",
        "levain": {"seed_g": 20, "flour_g": 100, "water_g": 100, "flour": {flour: 1},
                   "temperature_c": 24},
        "dough": {"flour_g": 900, "water_g": 630, "salt_g": 20, "flour": {flour: 1},
                  "temperature_c": 25, "target_rise_pct": 50},
    }  # fmt: skip
    if proof is not None:
        d["proof"] = {"temperature_c": proof, "hours": 12}
    return d


Chain = tuple[Compiled, list[aroma.Segment], dict[str, FloatArray], dict[str, list[aroma.Route]],
              aroma.Draws]  # fmt: skip


def _chain(d: dict[str, Any], n: int = 8) -> Chain:
    compiled = compile_plan(plan_from_dict(d))
    model = SourdoughModel(compiled, None)
    z = np.random.default_rng(0).standard_normal((n, model.dim))
    ch = bake._run_chain(model, compiled, [0.0], z, np.full(n, 1 / n), 0.0, [], [])
    segs = bake._aroma_segments(model, ch.traces, z)
    dr = aroma.draws(n, 5)
    conc, routes, _, _ = aroma.chain(segs, SD, dr, False)
    return compiled, segs, conc, routes, dr


def test_mixing_dilutes_the_levain_and_adds_fresh_flour() -> None:
    compiled, segs, c, _, dr = _chain(_plan())
    b1 = len(segs[0].tr.t_h)
    b2 = b1 + len(segs[1].tr.t_h)
    bulk = compiled.phases[1]
    fresh = bulk.flour_fresh["t65"] * dr["ing:White wheat flour:hexanal"][:, 0]
    assert np.allclose(c["hexanal"][:, b1], bulk.carry * c["hexanal"][:, b1 - 1] + fresh)
    # the retard continues the same dough: no dilution, no new flour
    assert np.allclose(c["hexanal"][:, b2], c["hexanal"][:, b2 - 1], rtol=0.05)
    assert segs[2].carry == 1.0 and segs[2].shares == {}


@pytest.mark.parametrize("flour,name", [("rye_t130", "Rye flour"), ("t150", "Whole wheat flour")])
def test_flour_names_follow_the_blend(flour: str, name: str) -> None:
    _, _, _, routes, _ = _chain(_plan(flour, None))
    assert ("ingredient", name, "carried in") in routes["hexanal"]


def test_a_plan_gets_aroma() -> None:
    d = _plan()
    out = forecast(plan_from_dict(d), BakeInputs(plan=d))
    s = out["sensory"]
    SensoryOut.model_validate(s)
    comp = {c["key"]: c for c in s["compounds"]}
    assert {"hexanal", "methylbutanol_3", "diacetyl", "acetic"} <= comp.keys()
    assert s["aroma_series"] and any(x["group"] == "aroma" for x in out["series"])


def test_a_bake_survives_an_aroma_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("aroma bug")

    monkeypatch.setattr(aroma, "evaluate", boom)
    d = _plan(proof=None)
    s = forecast(plan_from_dict(d), BakeInputs(plan=d, now_h=1.0))["sensory"]
    assert s["nutrition_label"] and s["aroma_series"] == [] and s["compounds"] == []


# ── curation § 7, tests 14-15 (prior-only forecasts, weighted medians) ──


def _medians(
    temp: float, hours: float, recipe: tuple[RecipeIn, ...] = (),
    organisms: list[str] | None = None,
) -> At:  # fmt: skip
    service.clear_caches()
    t, values, w = service.member_values(_inputs("sourdough", temp, recipe, organisms), hours)

    def at(key: str, h: float) -> float:
        rows = values.get(f"conc:{key}")
        if rows is None:
            return 0.0
        col = np.array([np.interp(h, t, row) for row in rows])
        return float(weighted_quantiles(col, w, (0.5,))[0])

    return at


def test_14_flour_to_levain_directions() -> None:
    # levain at 26 °C for 24 h, profile organisms and typical recipe (02:S1, 02:S2)
    c = _medians(26.0, 24.0)
    for key in ("methylbutanal_3", "methylbutanol_3", "diacetyl"):
        assert c(key, 24.0) > c(key, 0.0), key
    for key in ("hexanal", "e2_nonenal"):
        assert c(key, 24.0) < c(key, 0.0), key


def _dough() -> tuple[RecipeIn, ...]:
    # wheat sourdough at 1:1 flour:water (DY 200): est. (B2), 02:S3's dough yield not opened
    return (RecipeIn("White wheat flour", 500.0, "g", _per_100g("White wheat flour"), "base"),
            RecipeIn("Water", 500.0, "g", _per_100g("Water"), "base"))  # fmt: skip


@pytest.fixture(scope="module", params=["Lactobacillus brevis", "Lactobacillus plantarum"])
def cool(request: pytest.FixtureRequest) -> At:
    # 15 °C, 120 h, S. cerevisiae x L. brevis or L. plantarum (02:S3)
    return _medians(15.0, 120.0, _dough(), ["Saccharomyces cerevisiae", request.param])


def test_15_calibrated_end_points(cool: At) -> None:
    assert 274.0 <= cool("methylbutanol_3", 120.0) <= 38_500.0
    assert 33.0 <= cool("hexanal", 120.0) <= 1_100.0


@pytest.mark.parametrize("key,lo,hi", [
    ("methylbutanol_2", 42.0, 6_100.0), ("methylpropanol_2", 56.0, 10_700.0),
    ("ethyl_acetate", 450.0, 171_000.0), ("ethyl_hexanoate", 1.4, 1_800.0),
    ("ethyl_octanoate", 0.23, 182.0),
])  # fmt: skip
def test_15_reported_end_points(cool: At, key: str, lo: float, hi: float) -> None:
    assert lo <= cool(key, 120.0) <= hi


@pytest.mark.parametrize("key,hi", [
    pytest.param("isoamyl_acetate", 20.0, marks=pytest.mark.xfail(strict=True, reason=(
        "§ 5.2 isoamyl acetate : isoamyl alcohol 0.0062-0.015 mol/mol (05:Godillot23, wine) "
        "gives ~65 µg/kg; 02:S3's dough has nd-6.73 against 823-12 838 µg/kg alcohol "
        "(mass ratio <= 0.008), and the model has no dough esterase or ester loss"))),
    ("ethyl_butanoate", 21.0), ("ethyl_decanoate", 11.0),
    ("ethyl_2methylbutanoate", 1.8), ("ethyl_2methylpropanoate", 5.2),
    ("phenylethanol_2", 209_000.0),
])  # fmt: skip
def test_15_upper_bounds(cool: At, key: str, hi: float) -> None:
    assert cool(key, 120.0) <= hi


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.1: the sourdough engine has no free amino-acid pool (flour proteases are not "
    "modelled), so yeast forms no methional from methionine, and aldehyde reduction "
    "(kmax_ald_reduction >= 0.5/d) removes the flour's methional within days"))
def test_15_methional_lower_bound(cool: At) -> None:
    assert cool("methional", 120.0) >= 10.0
