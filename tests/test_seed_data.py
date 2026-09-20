"""Seed data integrity — no DB needed, pure data checks."""

from __future__ import annotations

from fermenttrack.seed_data import INGREDIENT_SEED_DATA, INGREDIENT_SEED_DATA_V2

VALID_ROLES = {"base", "starter", "flavoring", "additive"}


def test_seed_data_has_twenty_ingredients() -> None:
    assert len(INGREDIENT_SEED_DATA) == 20


def test_seed_data_names_are_unique() -> None:
    names = [name for name, _role, _systems in INGREDIENT_SEED_DATA]
    assert len(names) == len(set(names))


def test_seed_data_roles_are_valid() -> None:
    for name, role, _systems in INGREDIENT_SEED_DATA:
        assert role in VALID_ROLES, f"{name!r} has invalid role {role!r}"


def test_seed_data_every_ingredient_has_at_least_one_system() -> None:
    for name, _role, systems in INGREDIENT_SEED_DATA:
        assert len(systems) >= 1, f"{name!r} has no fermentation_systems"


def test_seed_data_covers_all_four_stage_machine_substrates() -> None:
    all_systems = {s for _name, _role, systems in INGREDIENT_SEED_DATA for s in systems}
    assert {"kombucha", "sourdough", "koji", "cheese"} <= all_systems


def test_seed_data_v2_has_three_ingredients() -> None:
    assert len(INGREDIENT_SEED_DATA_V2) == 3


def test_seed_data_v2_names_are_unique_and_dont_collide_with_v1() -> None:
    v1_names = {name for name, _role, _systems in INGREDIENT_SEED_DATA}
    v2_names = [name for name, _role, _systems in INGREDIENT_SEED_DATA_V2]
    assert len(v2_names) == len(set(v2_names))
    assert not (set(v2_names) & v1_names)


def test_seed_data_v2_roles_are_valid() -> None:
    for name, role, _systems in INGREDIENT_SEED_DATA_V2:
        assert role in VALID_ROLES, f"{name!r} has invalid role {role!r}"


def test_seed_data_v2_covers_lacto_ferment_and_garum() -> None:
    all_systems = {s for _name, _role, systems in INGREDIENT_SEED_DATA_V2 for s in systems}
    assert {"lacto_ferment", "garum"} <= all_systems
