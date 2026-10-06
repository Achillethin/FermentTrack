"""B1 templates on real prior ensembles: right signs, mass balance, ingredients and routes."""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.prediction import aroma, engine
from fermenttrack.prediction.aroma import Context, Draws, Route
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from tests.test_engine_diagnostics import _setup

LACTO = PROFILES["lacto_ferment"]
Run = tuple[Context, dict[str, FloatArray], dict[str, list[Route]], Draws]


def _run(
    shares: dict[str, float] | None = None, organisms: list[str] | None = None, n: int = 16
) -> Run:
    p, t = _setup("lacto_ferment", n, organisms)
    tr = engine.simulate(p, t, keep_states=True)
    ctx = aroma.build_context(p, tr, LACTO, shares or {"Cabbage": 0.98}, LACTO.co2_escapes)
    d = aroma.draws(n, 7)
    conc, routes = aroma.concentrations(ctx, d)
    return ctx, conc, routes, d


def test_ingredient_shares() -> None:
    items = [("Cabbage", 490.0, "base"), ("Water", 490.0, "base"), ("Salt", 20.0, "additive")]
    shares, no_data = aroma.ingredient_shares(items, "lacto_ferment")
    assert shares["Cabbage"] == pytest.approx(0.49) and no_data == []
    assert aroma.ingredient_shares([], "lacto_ferment") == ({"Cabbage": 0.98}, [])
    _, no_data = aroma.ingredient_shares([("Chilies", 500.0, "base")], "lacto_ferment")
    assert no_data == ["Chilies"]


def test_cabbage_brings_pungent_sulfurous_and_green() -> None:
    _, c, routes, _ = _run()
    for k in ("allyl_itc", "butenyl_itc", "dmds", "dmts", "z3_hexenol", "hexanal"):
        assert np.median(c[k].max(axis=1)) > 0.0, k
    assert ("ingredient", "Cabbage", "sinigrin (a glucosinolate)") in routes["allyl_itc"]
    assert any(
        r[0] == "organism" and r[1] == "Leuconostoc mesenteroides"
        for r in routes["ethyl_butanoate"]
    )


def test_pools_scale_with_the_ingredient_share() -> None:
    _, full, _, _ = _run({"Cabbage": 0.98})
    _, half, _, _ = _run({"Cabbage": 0.49})
    assert np.allclose(half["z3_hexenol"][:, 0], full["z3_hexenol"][:, 0] / 2.0)


def test_glucosinolate_released_never_exceeds_the_pool() -> None:
    _, c, _, d = _run()
    p0 = 0.98 * d["ing:Cabbage:@sinigrin"][:, 0] * 1000.0  # µmol/kg
    assert np.all(c["_released:@sinigrin"][:, -1] <= p0 * 1.0001)
    assert np.all(np.diff(c["_released:@sinigrin"], axis=1) >= -1e-9)


def test_unknown_class_contributes_nothing() -> None:
    ctx, _, _, d = _run()
    ctx.classes = ["unknown"] * len(ctx.classes)
    c, _ = aroma.concentrations(ctx, d)
    assert np.allclose(c.get("ethyl_butanoate", 0.0), 0.0)
    assert np.allclose(c.get("acetoin", 0.0), 0.0)
    assert np.all(c["dmts"][:, 0] > 0.0)  # the cabbage's burst pool needs no microbe


def test_a_custom_yeast_adds_fusel_alcohols() -> None:
    _, plain, _, _ = _run()
    lab = ["Leuconostoc mesenteroides", "Lactobacillus plantarum"]
    _, yeast, routes, _ = _run(organisms=[*lab, "Saccharomyces cerevisiae"])
    before = np.median(plain["methylbutanol_3"][:, -1])
    assert np.median(yeast["methylbutanol_3"][:, -1]) > 10 * before + 1.0
    assert any(r[1] == "Saccharomyces cerevisiae" for r in routes["methylbutanol_3"])


def test_all_tracers_finite_and_non_negative() -> None:
    _, c, _, _ = _run()
    for k, v in c.items():
        assert np.all(np.isfinite(v)) and np.all(v >= 0.0), k
