"""Pantry ranking (recommender v2 § 3.2, V7, V11): the list is what the user has, starred
items are must-include, and a ferment the ingredients are tagged for ranks above one that
needs operator (v) to take them in. On the committed grid, no database."""

from __future__ import annotations

import pytest

from fermenttrack.recommender import library, operators, service


def _types(cards: list[service.Card]) -> list[str]:
    return [c.recipe.fermentation_type for c in cards]


def _keys(cards: list[service.Card]) -> list[str]:
    return [(c.variant.parent.recipe.key if c.variant else c.recipe.key) for c in cards]


def test_coverage_is_the_share_of_non_staple_mass_the_user_has() -> None:
    kraut = library.get("sauerkraut_dry_salted")
    kimchi = library.get("napa_kimchi_room_temp")
    assert kraut is not None and kimchi is not None
    assert service.coverage(kraut, ["Cabbage"]) == pytest.approx(1.0)  # salt is a staple
    assert service.coverage(kraut, ["Carrot"]) == 0.0
    assert 0.5 < service.coverage(kimchi, ["Napa cabbage"]) < 1.0  # napa, not the aromatics


def test_foreign_counts_v_foods_in_a_type_they_are_not_tagged_for() -> None:
    carrot = operators.Operator("usda", "Carrot", share=0.05)
    picked = operators.Operator("usda", "Persimmon", share=0.05, fdc_id=1)
    assert service.foreign((carrot,), "kombucha") == 1  # Carrot is tagged lacto_ferment
    assert service.foreign((carrot,), "lacto_ferment") == 0
    assert service.foreign((picked,), "kombucha") == 0  # a user's own USDA pick is intended


def test_carrot_and_garlic_go_to_a_lacto_ferment_not_a_kombucha() -> None:
    cards = service.experimental_cards(["Carrot", "Garlic"], (), None)
    assert cards and _types(cards)[0] == "lacto_ferment", _keys(cards)


def test_a_pantry_item_no_recipe_uses_does_not_exclude_recipes() -> None:
    cards, _ = service.proven_cards([], (), None, pantry=["Cabbage", "Carrot"])
    assert "sauerkraut_dry_salted" in _keys(cards)


def test_starred_items_stay_must_include() -> None:
    cards, _ = service.proven_cards(["Napa cabbage"], (), None, pantry=["Cabbage"])
    assert _keys(cards) == ["napa_kimchi_room_temp"]


def test_recipes_using_nothing_from_the_pantry_are_left_out() -> None:
    proven, _ = service.proven_cards([], (), None, pantry=["Cabbage"])
    experimental = service.experimental_cards([], (), None, pantry=["Cabbage"])
    for c in (*proven, *experimental):
        assert service.coverage(c.recipe, ["Cabbage"]) > 0, c.recipe.key


def test_no_ingredients_at_all_leaves_every_recipe_in() -> None:
    targets = service.parse_targets(["fruity"], [])
    with_pantry, _ = service.proven_cards([], targets, None, pantry=[])
    without, _ = service.proven_cards([], targets, None)
    assert _keys(with_pantry) == _keys(without) and len(without) == service.CARDS_PER_SECTION


def test_more_of_the_pantry_ranks_first_without_targets() -> None:
    cards, _ = service.proven_cards([], (), None, pantry=["Cabbage", "Napa cabbage"])
    assert _keys(cards)[:2] == ["sauerkraut_dry_salted", "napa_kimchi_room_temp"]


def test_experimental_ties_on_upside_break_on_the_central_score() -> None:
    targets = service.parse_targets(["fruity"], [])
    cards = service.experimental_cards([], targets, None)
    keys = [service.experimental_rank_key(c) for c in cards]
    assert keys == sorted(keys)
    for a, b in zip(cards, cards[1:], strict=False):
        ea, eb = a.evaluation, b.evaluation
        assert ea.u is not None and eb.u is not None and ea.e is not None and eb.e is not None
        if ea.u - ea.penalty == eb.u - eb.penalty:
            assert ea.e >= eb.e
