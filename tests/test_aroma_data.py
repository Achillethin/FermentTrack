"""Aroma data: catalogue loaded, parameters well-formed, ingredients and evidence consistent."""

from __future__ import annotations

from fermenttrack.prediction import aroma_data as A


def test_catalogue_loads_all_85() -> None:
    assert len(A.COMPOUNDS) == 85
    assert A.COMPOUNDS["ethyl_acetate"].templates == ("T2", "T5")
    assert A.COMPOUNDS["acetic"].ph_kind == "acid" and A.COMPOUNDS["acetic"].pka == 4.76
    bdo = A.COMPOUNDS["butanediol_23"]
    assert bdo.threshold is None and bdo.conc_only


def test_every_evidence_cell_is_a_known_compound() -> None:
    for t in A.AROMA_TYPES:
        for key, (tier, _anchor, sources) in A.EVIDENCE[t].items():
            assert key in A.COMPOUNDS, key
            assert tier in ("calibrated", "reported", "plausible", "engine"), key
            assert tier in ("plausible", "engine") or sources, key


def test_ingredient_entries_are_compounds_or_labelled_precursors() -> None:
    for name, entries in A.AROMA_INGREDIENTS.items():
        for key in entries:
            assert key in A.COMPOUNDS or key in A.PRECURSOR_LABEL, (name, key)
    for shares in A.DEFAULT_INGREDIENTS.values():
        assert set(shares) <= set(A.AROMA_INGREDIENTS) and sum(shares.values()) <= 1.0


def test_parameters_and_molar_masses_cover_the_templates() -> None:
    assert {"b_mb_yeast", "gsl_release", "b_dmds_lab", "kaw_eta", "matrix"} <= A.PARAMS.keys()
    for k in ("methylbutanol_3", "allyl_itc", "butenyl_itc", "dmds", "dmts", "acetoin"):
        assert k in A.MW, k


def test_every_compound_has_an_air_water_partition() -> None:
    for key, c in A.COMPOUNDS.items():
        if c.status == "active":
            assert key in A.KAW or A.KAW_CLASS.get(key) in A.KAW, key


def test_flour_pools_follow_the_new_threshold_medians() -> None:
    # § 6.2 re-derived (B2): OAV > 100 in rye flour (02:S2) x the 2026-10-06 medians
    flour = A.AROMA_INGREDIENTS["Rye flour"]
    for key in ("hexanal", "e2_nonenal", "methional"):
        thr = A.COMPOUNDS[key].threshold
        assert thr is not None and flour[key].hi >= 100 * thr.median, key


def test_new_types_have_aroma_data() -> None:
    for t, default in (("sourdough", "White wheat flour"), ("vinegar", "White wine"),
                       ("koji", "White rice")):
        assert t in A.AROMA_TYPES and t in A.EVIDENCE, t
        assert set(A.DEFAULT_INGREDIENTS[t]) == {default}, t
    for t, cells in A.PENDING.items():
        assert set(cells) <= set(A.COMPOUNDS), t


def test_ingredient_pass_entries() -> None:
    from fermenttrack.seed_data import INGREDIENT_SEED_DATA_V4

    # their own odorants are not curated: they stay "no aroma data yet"
    no_data = {"Garlic", "Onion", "Radish", "Carrot", "Chilies"}
    assert not no_data & set(A.AROMA_INGREDIENTS)
    v4 = {n for n, _r, _s in INGREDIENT_SEED_DATA_V4} - no_data
    assert v4 <= set(A.AROMA_INGREDIENTS)
    for spice, key in (("Caraway seeds", "carvone"), ("Lemongrass", "geranial"),
                       ("Fresh ginger", "neral"), ("White rice", "acetylpyrroline_2"),
                       ("Rye flour", "sotolon")):  # fmt: skip
        assert key in A.AROMA_INGREDIENTS[spice], spice
