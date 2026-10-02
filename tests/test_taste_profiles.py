"""Taste ladders and milestone lenses in the per-type profiles."""

from __future__ import annotations

import pytest

from fermenttrack.prediction import compounds as C
from fermenttrack.prediction.profiles import GENERIC_PROFILE, PROFILES, TasteSpec

METRICS = {"sugar_acid", "acetic", "acidity_pct", "umami"}


def test_every_type_but_koji_has_a_taste_ladder() -> None:
    for name, p in {**PROFILES, "generic": GENERIC_PROFILE}.items():
        if name == "koji":
            assert p.taste is None
            continue
        assert p.taste is not None, name
        assert {b.metric for b in p.taste.boundaries} <= METRICS
        assert p.taste.glutamate in C.GLUTAMATE_SHARE


def test_a_ladder_needs_one_boundary_and_note_per_step() -> None:
    with pytest.raises(ValueError):
        TasteSpec(("a", "b"), (), ())


def test_nutrition_milestones_carry_their_lens() -> None:
    lens = {m.key: m.lens for m in PROFILES["kombucha"].milestones}
    assert lens["abv_over_0_5"] == "nutrition"
    assert lens["ph_below_4_2"] == "process"
    assert {m.key: m.lens for m in PROFILES["kefir"].milestones}["lactose_half"] == "nutrition"


def test_dough_keeps_its_gas() -> None:
    assert not PROFILES["sourdough"].co2_escapes
    assert PROFILES["kombucha"].co2_escapes
