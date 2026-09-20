"""Multi-substrate stage machine tests (docs/ARCHITECTURE.md § Stage State Machines)."""

from __future__ import annotations

import pytest

from fermenttrack.stages import (
    InvalidStageError,
    first_stage,
    get_stage,
    next_stage_name,
)


def test_kombucha_progression_unchanged() -> None:
    assert first_stage("kombucha") == "brew_sweet_tea"
    assert next_stage_name("kombucha", "brew_sweet_tea") == "1F"
    assert next_stage_name("kombucha", "bottling") == "conditioning"
    assert next_stage_name("kombucha", "ready") is None


def test_sourdough_progression() -> None:
    assert first_stage("sourdough") == "feed_starter"
    assert next_stage_name("sourdough", "feed_starter") == "bulk_ferment"
    assert next_stage_name("sourdough", "bulk_ferment") == "shape"
    assert next_stage_name("sourdough", "shape") == "cold_retard"
    assert next_stage_name("sourdough", "cold_retard") == "bake"
    assert next_stage_name("sourdough", "bake") == "done"
    assert next_stage_name("sourdough", "done") is None


def test_koji_progression() -> None:
    assert first_stage("koji") == "soak"
    order = ["soak", "steam", "inoculate", "incubate", "harvest", "done"]
    for current, expected_next in zip(order, order[1:] + [None]):
        assert next_stage_name("koji", current) == expected_next


def test_cheese_progression() -> None:
    assert first_stage("cheese") == "heat_milk"
    order = ["heat_milk", "culture", "rennet", "cut_curd", "cook", "press", "salt", "age", "ready"]
    for current, expected_next in zip(order, order[1:] + [None]):
        assert next_stage_name("cheese", current) == expected_next


def test_lacto_ferment_progression() -> None:
    assert first_stage("lacto_ferment") == "prep_and_salt"
    order = ["prep_and_salt", "ferment", "ready"]
    for current, expected_next in zip(order, order[1:] + [None]):
        assert next_stage_name("lacto_ferment", current) == expected_next


def test_lacto_ferment_reminder_flags_brine_submersion() -> None:
    stage = get_stage("lacto_ferment", "prep_and_salt")
    assert "submerged" in stage.reminder_action


def test_miso_progression() -> None:
    assert first_stage("miso") == "cook_soybeans"
    order = ["cook_soybeans", "mix_koji_salt", "ferment", "ready"]
    for current, expected_next in zip(order, order[1:] + [None]):
        assert next_stage_name("miso", current) == expected_next


def test_garum_progression() -> None:
    assert first_stage("garum") == "salt_fish"
    order = ["salt_fish", "ferment", "strain", "ready"]
    for current, expected_next in zip(order, order[1:] + [None]):
        assert next_stage_name("garum", current) == expected_next


def test_substrate_without_stage_machine_uses_in_progress_pseudo_stage() -> None:
    assert first_stage("kefir") == "in_progress"
    assert next_stage_name("kefir", "in_progress") is None
    stage = get_stage("kefir", "in_progress")
    assert stage.reminder_action is None
    assert stage.expected_duration is None


def test_invalid_stage_name_within_known_machine_raises() -> None:
    with pytest.raises(InvalidStageError):
        get_stage("kombucha", "bogus_stage")


def test_invalid_stage_name_for_no_machine_substrate_raises() -> None:
    with pytest.raises(InvalidStageError):
        get_stage("kefir", "bogus_stage")


def test_bottling_is_critical_urgency() -> None:
    assert get_stage("kombucha", "bottling").urgency == "critical"
