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
    ferment: str = "lacto_ferment", temp: float | None = None,
) -> Run:  # fmt: skip
    p, t = _setup(ferment, n, organisms, temp)
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


def test_koji_volatiles_follow_mycelium_growth() -> None:
    _, c, routes, _ = _run({"White rice": 1.0}, ["Aspergillus oryzae"], ferment="koji")
    for k in ("octen3ol", "octanone_3", "octanol_3", "heptanone_2", "nonanone_2"):
        assert np.all(c[k][:, -1] > c[k][:, 0]), k
        assert any(r[1] == "Aspergillus oryzae" for r in routes[k]), k
    assert ("ingredient", "White rice", "carried in") in routes["hexanal"]


def test_no_growth_no_mould_volatiles() -> None:
    ctx, _, _, d = _run({"White rice": 1.0}, ["Aspergillus oryzae"], ferment="koji")
    ctx.growth = [np.zeros_like(g) for g in ctx.growth]
    c, _ = aroma.concentrations(ctx, d)
    for k in ("octen3ol", "heptanone_2", "ethyl_acetate"):
        assert np.allclose(c.get(k, 0.0), 0.0), k


MISO = ["Aspergillus oryzae", "Tetragenococcus halophilus", "Zygosaccharomyces rouxii"]
SOY_RICE = {"Soybeans": 0.45, "White rice": 0.44}


def test_miso_makes_hemf_through_the_yeast() -> None:
    _, c, routes, _ = _run(SOY_RICE, MISO, ferment="miso", temp=30.0)
    assert np.median(c["hemf"].max(axis=1)) > 0.0
    assert any(r[1] == "Zygosaccharomyces rouxii" for r in routes["hemf"])
    assert any(r[0] == "ingredient" and r[1] == "Soybeans" for r in routes["hemf"])


def test_no_soybean_no_hemf() -> None:
    _, c, _, _ = _run({"White rice": 0.89}, MISO, ferment="miso", temp=30.0)
    assert np.allclose(c.get("hemf", 0.0), 0.0)


def test_no_koji_no_hemf() -> None:
    _, c, _, _ = _run(SOY_RICE, MISO[1:], ferment="miso", temp=30.0)
    assert np.allclose(c.get("hemf", 0.0), 0.0)


def test_hemf_conversion_waits_for_ph_5_6() -> None:
    ctx, c, _, _ = _run(SOY_RICE, MISO, ferment="miso", temp=30.0)
    first = np.argmax(ctx.ph < A.HEMF_PH, axis=1)  # first time below the gate
    for i, j in enumerate(first):
        if ctx.ph[i, j] < A.HEMF_PH:
            assert np.allclose(c["hemf"][i, :j], 0.0)  # the gate opens at j
        else:  # never below: none at all
            assert np.allclose(c["hemf"][i], 0.0)


def test_strecker_needs_free_amino_acids() -> None:
    strecker = ("chemistry", "free amino acids", "Strecker degradation")
    _, _, routes, _ = _run(SOY_RICE, MISO, ferment="miso", temp=30.0)
    assert strecker in routes["methylbutanal_3"]
    _, _, routes2, _ = _run()  # cabbage: no free amino acids
    assert strecker not in routes2.get("methylbutanal_3", [])


def test_garum_fish_lipids_rise() -> None:
    _, c, routes, _ = _run({"Anchovies": 0.75}, ["Tetragenococcus halophilus"], ferment="garum")
    for k in A.FISH_LIPID:
        assert np.all(c[k][:, -1] > 0.0), k
        assert ("ingredient", "Anchovies", "fish lipid oxidation") in routes[k], k


def test_fish_lipids_need_fish() -> None:
    _, c, _, _ = _run({"Soybeans": 0.5}, ["Tetragenococcus halophilus"], ferment="garum")
    assert np.allclose(c.get("z4_heptenal", 0.0), 0.0)


def test_conserved_tracer_concentrates_as_co2_escapes() -> None:
    ctx, _, _, d = _run({"Cucumber": 0.98}, ["Leuconostoc mesenteroides"])
    zero = np.zeros_like(d["loss_linalool"])
    c, _ = aroma.concentrations(ctx, {**d, "loss_linalool": zero, "kaw_eta": zero})
    assert np.any(ctx.left[:, -1] < 0.999)  # heterofermentative: CO2 leaves the jar
    assert np.allclose(c["linalool"], c["linalool"][:, :1] / ctx.left)


CHEESE = ["Lactococcus lactis"]


def _cheese(share: float) -> tuple[dict[str, FloatArray], Draws]:
    ctx, _, _, d = _run({"Milk": 1.0}, CHEESE, ferment="cheese", temp=30.0)
    d = {**d, "share_cit_lc": np.full_like(d["share_cit_lc"], share)}
    c, _ = aroma.concentrations(ctx, d)
    return c, d


def test_citrate_feeds_acetolactate_within_its_mass_balance() -> None:
    c, d = _cheese(1.0)
    p0 = d["ing:Milk:@citrate"][:, 0] * 1000.0  # µmol/kg
    assert np.all(np.diff(c["_citrate"], axis=1) <= 1e-9)
    assert np.all(c["_citrate"][:, -1] < p0)
    c4 = (c["diacetyl"] / A.MW["diacetyl"] + c["acetoin"] / A.MW["acetoin"]
          + c.get("butanediol_23", 0.0) / A.MW["butanediol_23"] + c["_acetolactate"])  # fmt: skip
    assert np.all(c4[:, -1] > 0.0)


def test_no_citrate_active_cells_no_citrate_c4() -> None:  # curation test 36
    c, d = _cheese(0.0)
    p0 = d["ing:Milk:@citrate"][:, 0] * 1000.0
    assert np.allclose(c["_citrate"], p0[:, None])


def test_leuconostoc_waits_for_sugar_to_fall() -> None:
    ctx, c, _, _ = _run({"Milk": 1.0}, ["Leuconostoc mesenteroides"], ferment="kefir")
    sweet = ctx.pools[:, :, engine.PI["hexoses"]] > A.LEUC_SUGAR_GATE
    used = np.diff(c["_citrate"], axis=1) < -1e-9
    assert not np.any(used & sweet[:, 1:] & sweet[:, :-1])


def test_milk_lactones_grow_from_their_fat_bound_precursor() -> None:
    _, c, routes, _ = _run({"Milk": 0.97}, None, ferment="kefir")
    assert np.all(c["decalactone_delta"][:, -1] > c["decalactone_delta"][:, 0])
    assert ("ingredient", "Milk", "milk fat (lactone precursors)") in routes["decalactone_delta"]


TEA = {"Black tea leaves": 0.005}
KOMBUCHA = ["Saccharomyces cerevisiae", "Acetobacter aceti", "Gluconacetobacter xylinus"]


def test_tea_bound_terpenes_release_within_the_pool() -> None:
    _, c, routes, d = _run(TEA, KOMBUCHA, ferment="kombucha", temp=30.0)
    b0 = 0.005 * d["ing:Black tea leaves:@tea_bound"][:, 0]
    assert np.all(np.diff(c["_tea_bound"], axis=1) <= 1e-9)
    assert np.all(c["_tea_bound"][:, -1] < b0) and np.all(c["_tea_bound"] >= 0.0)
    assert ("ingredient", "Black tea leaves", "bound terpenes (glycosides)") in routes["linalool"]


def test_kombucha_surface_strips_volatiles() -> None:
    assert "kombucha" in A.K_SURF
    _, c, _, _ = _run(TEA, KOMBUCHA, ferment="kombucha", temp=30.0)
    assert np.all(c["hexanal"][:, -1] < c["hexanal"][:, 0])


def test_spices_bring_their_terpenes() -> None:
    _, c, routes, _ = _run({"Cabbage": 0.97, "Caraway seeds": 0.005})
    assert np.all(c["carvone"][:, 0] > 0.0)
    assert ("ingredient", "Caraway seeds", "carried in") in routes["carvone"]


def test_vegetable_amino_acids_only_feed_strecker() -> None:
    ctx, veg, routes, d = _run({"Napa cabbage": 0.975})
    key = "ing:Napa cabbage:@free_aa"
    plain, _ = aroma.concentrations(ctx, {**d, key: np.zeros_like(d[key])})
    for k in ("methylbutanol_3", "phenylethanol_2"):
        # the slow Strecker chemistry adds tens of µg/kg at most; through the microbial
        # routes the same 2 g/kg pool would add ~59 mg/kg 3-methylbutanol (B6 probe)
        assert np.all(np.abs(veg[k] - plain[k]) <= 50.0), k
    assert ("ingredient", "Napa cabbage", "free amino acids (Strecker)") in routes["methional"]


def test_coumaric_acid_gives_vinylphenol() -> None:
    ctx, _, _, d = _run({"Cabbage": 0.98}, ["Lactobacillus plantarum", "Saccharomyces cerevisiae"])
    d = {**d, "pad_lp": np.ones_like(d["pad_lp"]), "pof_yeast": np.ones_like(d["pof_yeast"])}
    c, routes = aroma.concentrations(ctx, d)
    assert np.all(c["vinylphenol_4"][:, -1] > 0.0)
    assert ("ingredient", "Cabbage", "p-coumaric acid") in routes["vinylphenol_4"]
