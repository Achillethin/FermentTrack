"""Seed data integrity — no DB needed, pure data checks."""

from __future__ import annotations

from fermenttrack.seed_data import INGREDIENT_SEED_DATA

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
