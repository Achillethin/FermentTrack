"""Sourdough aroma: chained phases (bake plans) and curation § 7 tests 14-15."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from fermenttrack.prediction import aroma, bake
from fermenttrack.prediction.bake import BakeInputs, forecast
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.sourdough import Compiled, SourdoughModel, compile_plan, plan_from_dict
from fermenttrack.schemas import SensoryOut

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
