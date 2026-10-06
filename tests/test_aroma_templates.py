"""B1 templates on real prior ensembles: right signs, mass balance, ingredients and routes."""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.prediction import aroma, engine
from fermenttrack.prediction import aroma_data as A
from fermenttrack.prediction.aroma import Context, Draws, Route
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from tests.test_engine_diagnostics import _setup

LACTO = PROFILES["lacto_ferment"]
Run = tuple[Context, dict[str, FloatArray], dict[str, list[Route]], Draws]


def _run(
    shares: dict[str, float] | None = None, organisms: list[str] | None = None, n: int = 16,
    ferment: str = "lacto_ferment",
) -> Run:  # fmt: skip
    p, t = _setup(ferment, n, organisms)
    tr = engine.simulate(p, t, keep_states=True)
    prof = PROFILES[ferment]
    seg = aroma.Segment(p, tr, shares or {"Cabbage": 0.98})
    ctx = aroma.build_context(seg, prof, prof.co2_escapes)
    d = aroma.draws(n, 7)
    conc, routes = aroma.concentrations(ctx, d)
    return ctx, conc, routes, d


def test_ingredient_shares() -> None:
    items = [("Cabbage", 490.0, "base"), ("Water", 490.0, "base"), ("Salt", 20.0, "additive")]
    shares, no_data, notes = aroma.ingredient_shares(items, "lacto_ferment")
    assert shares["Cabbage"] == pytest.approx(0.49) and no_data == [] and notes == []
    assert aroma.ingredient_shares([], "lacto_ferment") == ({"Cabbage": 0.98}, [], [])
    _, no_data, _ = aroma.ingredient_shares([("Chilies", 500.0, "base")], "lacto_ferment")
    assert no_data == ["Chilies"]


def test_unweighed_recipe_never_falls_back_to_the_default_cabbage() -> None:
    shares, no_data, notes = aroma.ingredient_shares(
        [("Chilies", None, "base"), ("Salt", None, "additive")], "lacto_ferment"
    )
    assert "Cabbage" not in shares and shares == {"Chilies": pytest.approx(0.98)}
    assert no_data == ["Chilies"] and notes


def test_an_unweighed_ingredient_is_named_not_dropped_silently() -> None:
    items = [("Cabbage", None, "base"), ("Carrot", 200.0, "base"), ("Salt", 20.0, "additive")]
    shares, no_data, notes = aroma.ingredient_shares(items, "lacto_ferment")
    assert "Cabbage" not in shares and no_data == ["Carrot"]
    assert any("Cabbage" in n for n in notes)


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


@pytest.mark.parametrize("veg", ["Cabbage", "Napa cabbage (salted)"])
def test_every_compound_made_says_where_it_comes_from(veg: str) -> None:
    _, c, routes, _ = _run({veg: 0.975})
    for k, v in c.items():
        if not k.startswith("_") and np.max(v) > 0.0:
            assert routes.get(k), k


def test_a_reduced_aldehyde_is_not_called_carried_in() -> None:
    _, c, routes, _ = _run({"Napa cabbage (salted)": 0.975})
    pe = routes["phenylethanol_2"]
    assert ("ingredient", "Napa cabbage (salted)", "carried in") not in pe
    assert any("phenylacetaldehyde" in r[2] for r in pe if r[0] == "ingredient")


SOUR = ["Saccharomyces cerevisiae", "Lactobacillus sanfranciscensis"]


def test_flour_brings_aldehydes_and_ferulic_acid() -> None:
    _, c, routes, _ = _run({"White wheat flour": 0.54}, SOUR, ferment="sourdough")
    for k in ("hexanal", "e2_nonenal", "methional"):
        assert c[k][:, -1].mean() < c[k][:, 0].mean(), k  # microbes reduce them
    assert ("ingredient", "White wheat flour", "carried in") in routes["hexanal"]
    assert ("ingredient", "White wheat flour", "ferulic acid") in routes["vinylguaiacol_4"]


def test_ferulic_acid_mass_balance() -> None:
    _, c, _, d = _run({"White wheat flour": 0.54}, SOUR, ferment="sourdough")
    total = 0.54 * d["ing:White wheat flour:@ferulic"][:, 0] * 1000.0  # µmol/kg
    left = c["_ferulic_bound"] + c["_ferulic_free"]
    made = c.get("vinylguaiacol_4", 0.0) / A.MW["vinylguaiacol_4"]
    assert np.all(left + made <= total[:, None] * 1.0001)
    assert np.all(np.diff(c["_ferulic_bound"], axis=1) <= 1e-9)


def test_no_pof_no_vinylguaiacol() -> None:
    ctx, _, _, d = _run({"White wheat flour": 0.54}, SOUR, ferment="sourdough")
    d = {**d, "pof_yeast": np.zeros_like(d["pof_yeast"]), "pad_lp": np.zeros_like(d["pad_lp"])}
    c, _ = aroma.concentrations(ctx, d)
    assert np.allclose(c.get("vinylguaiacol_4", 0.0), 0.0)


def test_sugar_route_goes_through_acetolactate() -> None:
    _, c, routes, _ = _run()  # cabbage, LAB
    assert np.all(c["diacetyl"][:, -1] > 0.0) and np.all(c["pentanedione_23"][:, -1] > 0.0)
    assert np.all(c["_acetolactate"] >= 0.0) and np.any(c["_acetolactate"] > 0.0)
    assert any(r[0] == "organism" for r in routes["diacetyl"])


VIN = ["Acetobacter aceti", "Acetobacter pasteurianus"]


def test_aab_sink_and_products() -> None:
    _, c, routes, _ = _run({"White wine": 0.53}, VIN, ferment="vinegar")
    for k in ("methylbutanol_3", "methylpropanol_2", "acetaldehyde", "butanediol_23"):
        assert np.all(c[k][:, -1] < c[k][:, 0]), k
    for k in ("methylbutanoic_3", "methylpropanoic_2", "acetoin"):
        assert np.all(c[k][:, -1] > c[k][:, 0]), k
    assert any(r[1] == "Acetobacter aceti" for r in routes["methylbutanoic_3"])
    assert any(r[0] == "ingredient" and r[1] == "White wine" for r in routes["acetoin"])


def test_aab_oxidation_mass_balance() -> None:
    _, c, _, _ = _run({"White wine": 0.53}, VIN, ferment="vinegar")
    lost = (c["methylpropanol_2"][:, 0] - c["methylpropanol_2"][:, -1]) / A.MW["methylpropanol_2"]
    made = c["methylpropanoic_2"][:, -1] / A.MW["methylpropanoic_2"]
    assert np.all(made <= lost * 1.0001)


@pytest.mark.parametrize("base", ["White wine", "Hard cider"])
def test_wine_base_scales_with_starting_ethanol(base: str) -> None:
    ctx, c, _, d = _run({base: 0.5}, VIN, ferment="vinegar")
    etoh0 = ctx.pools[:, 0, engine.PI["ethanol"]]
    pool = d[f"ing:{base}:ethyl_acetate"][:, 0]
    assert np.allclose(c["ethyl_acetate"][:, 0], pool * etoh0 / A.BASE_ETHANOL)


def test_surface_loss_only_in_open_vessels() -> None:
    d = aroma.draws(4, 0)
    for ferment, open_ in (("vinegar", True), ("koji", True), ("lacto_ferment", False),
                           ("sourdough", False)):  # fmt: skip
        assert (ferment in A.K_SURF) == open_, ferment
    assert np.all(d["k_surf_vinegar"] > 0.0) and np.all(d["k_surf_koji"] > 0.0)
