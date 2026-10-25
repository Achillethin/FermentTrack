"""The lacto composer (recommender v2 § 3.3, release 2): rules, masses and the safety gate."""

from __future__ import annotations

import pytest

from fermenttrack.recommender import composer as C
from fermenttrack.recommender import gate


def _rows(recipe):  # type: ignore[no-untyped-def]
    return {i.name: (i.role, i.g_per_kg.median) for i in recipe.ingredients}


def test_carrot_and_garlic_is_brined_carrot_with_garlic() -> None:
    """v2 § 4 release 2: "carrot + garlic returns brined carrots with garlic"."""
    (c,) = C.candidates(["Carrot", "Garlic"])
    r = C.compose(c)
    assert c.method == "brine" and r.name == "Brined carrot with garlic"
    rows = _rows(r)
    assert rows["Salt"] == ("additive", pytest.approx(25.0))  # 2.5 % of the batch
    assert rows["Water"][1] + rows["Salt"][1] == pytest.approx(540.0)  # brine 54 % (NCHFP)
    assert rows["Garlic"] == ("flavoring", pytest.approx(25.0))  # 2.5 % (five kimchi recipes)
    assert rows["Carrot"] == ("base", pytest.approx(435.0))
    assert sum(g for _, g in rows.values()) == pytest.approx(1000.0)
    brine_pct = 100 * rows["Salt"][1] / (rows["Salt"][1] + rows["Water"][1])
    assert 1.86 <= brine_pct <= 5.38  # UMN 1-3 Tbsp per quart
    assert gate.check(gate.from_recipe(r), [20.0]).ok


def test_cabbages_are_dry_salted_and_a_plain_cabbage_is_left_to_the_library() -> None:
    assert C.Composition(("Napa cabbage",), ()).method == "dry_salted"
    assert C.Composition(("Cabbage", "Carrot"), ()).method == "brine"  # any brined base
    # dry-salted cabbage alone is the sauerkraut: Proven serves it
    assert C.candidates(["Cabbage"]) == []
    r = C.compose(C.Composition(("Napa cabbage",), ("Garlic",)))
    rows = _rows(r)
    assert "Water" not in rows and rows["Salt"][1] == pytest.approx(22.5)  # 2.25 %
    assert gate.check(gate.from_recipe(r), [20.0]).ok


def test_must_use_items_are_in_every_composition_or_there_is_none() -> None:
    cs = C.candidates(["Radish", "Carrot"], must=["Garlic"])
    assert cs and all("Garlic" in c.aromatics for c in cs)
    assert C.candidates(["Carrot"], must=["Kombucha"]) == []  # not composable: no candidate
    assert C.candidates(["Carrot", "Dill"], must=["Dill"]) == []  # no sourced dill amount yet


def test_more_of_the_pantry_first_and_validation() -> None:
    cs = C.candidates(["Radish", "Chilies", "Garlic"])
    assert cs[0].bases == ("Chilies", "Radish")  # both bases before either alone
    with pytest.raises(C.CompositionError):
        C.composition(["Garlic"], [])  # an aromatic is not a base
    with pytest.raises(C.CompositionError):
        C.composition(["Carrot"], ["Caraway seeds"])  # no sourced amount
    with pytest.raises(C.CompositionError):
        C.composition(["Carrot", "Radish", "Cucumber"], [])  # at most 2 bases
    dup = C.composition(["Carrot", "Carrot"], ["Garlic"])
    assert dup == C.Composition(("Carrot",), ("Garlic",))
