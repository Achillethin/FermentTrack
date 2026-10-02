"""Taste and nutrition in the forecast (service path)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction import derived, service
from fermenttrack.prediction.service import OrganismIn, PredictionInputs, RecipeIn, predict

CABBAGE = {
    "water": 92.2, "protein": 1.28, "carbohydrate": 5.8, "fiber": 2.5, "sugars_total": 3.2,
    "sucrose": 0.08, "glucose": 1.67, "fructose": 1.45, "sodium": 0.018,
}  # fmt: skip
SALT = {"water": 0.2, "sodium": 38.8}


@pytest.fixture(autouse=True)
def _fresh() -> None:
    service.clear_caches()


def _inputs(
    ferment: str, temp: float | None = None, recipe: tuple[RecipeIn, ...] = (),
    organisms: list[str] | None = None, now_h: float = 0.0,
) -> PredictionInputs:  # fmt: skip
    names = organisms if organisms is not None else FERMENTATION_TYPE_ORGANISMS[ferment]
    return PredictionInputs(
        fermentation_type=ferment, now_h=now_h, expected_temperature_c=temp,
        organisms=tuple(OrganismIn(n, ORGANISMS.get(n, "bacteria"), ()) for n in names),
        organism_source="default" if organisms is None else "custom",
        recipe=recipe, measurements=(),
    )  # fmt: skip


def _phase_prob(body: dict[str, Any], name: str, i: int) -> float:
    return float(body["sensory"]["taste_phases"]["prob"][name][i])


def _row(body: dict[str, Any], key: str) -> dict[str, Any]:
    return next(r for r in body["sensory"]["nutrition_label"] if r["key"] == key)


def test_sauerkraut_is_sour_by_two_weeks() -> None:
    # Pederson & Albury: 1.5-2.3 % acidity at day 14 (18 °C)
    body = predict(_inputs("lacto_ferment", 18.0), horizon_h=14 * 24)
    assert _phase_prob(body, "fresh", 0) > 0.9
    assert _phase_prob(body, "sour", -1) > 0.5


def test_kombucha_leaves_the_sweet_phase() -> None:
    body = predict(_inputs("kombucha", 24.0), horizon_h=21 * 24)
    assert _phase_prob(body, "sweet", 0) > 0.9
    assert _phase_prob(body, "sweet", -1) < 0.2


def test_kefir_is_tangy_within_a_day() -> None:
    # Irigoyen et al. 2005: 0.8-1 % lactic acid at 24 h
    body = predict(_inputs("kefir", 22.0), horizon_h=24)
    assert _phase_prob(body, "tangy", -1) + _phase_prob(body, "sour", -1) > 0.7


def test_kombucha_alcohol_in_the_published_range() -> None:
    # Chen & Liu 2000, Jayabalan 2007: a few g/L ethanol, i.e. ~0.1-1.5 % ABV
    body = predict(_inputs("kombucha", 24.0), horizon_h=10 * 24)
    assert 0.1 <= _row(body, "alcohol")["end"]["p50"] <= 1.5


def test_recipe_nutrients_carry_through() -> None:
    recipe = (
        RecipeIn("Cabbage", 1000, "g", CABBAGE, "base"),
        RecipeIn("Salt", 20, "g", SALT, "additive"),
    )
    body = predict(_inputs("lacto_ferment", 18.0, recipe), horizon_h=7 * 24)
    salt = (1000 * 0.018 + 20 * 38.8) / 100 * 2.5 / 1020 * 100  # g/100 g at the start
    assert _row(body, "salt")["start"]["p50"] == pytest.approx(salt, rel=0.02)
    assert _row(body, "fat")["start"] is None  # cabbage here reports no fat: unknown
    groups = {s["group"] for s in body["series"]}
    assert {"taste", "nutrition"} <= groups
    assert any(m["lens"] == "taste" for m in body["milestones"])
    assert all(m["lens"] in ("process", "taste", "nutrition") for m in body["milestones"])


def test_typical_recipe_nutrition_is_partial() -> None:
    body = predict(_inputs("lacto_ferment", 18.0), horizon_h=7 * 24)
    assert _row(body, "fat")["start"] is None and _row(body, "salt")["start"] is not None
    assert _row(body, "energy_kcal")["start"]["lower_bound"]


def test_what_if_moves_taste() -> None:
    base = predict(_inputs("kombucha", 24.0), horizon_h=14 * 24)
    warm = predict(_inputs("kombucha", 24.0), temperature_c=30.0, horizon_h=14 * 24)
    assert warm["sensory"] is not None
    assert warm["sensory"]["taste_phases"] != base["sensory"]["taste_phases"]


def test_koji_has_no_taste_ladder() -> None:
    body = predict(_inputs("koji", 30.0), horizon_h=48)
    assert body["sensory"]["taste_phases"] is None
    assert not [m for m in body["milestones"] if m["lens"] == "taste"]
    assert _row(body, "carbohydrate")["start"] is not None


def test_unmodelled_organisms_still_get_a_label() -> None:
    body = predict(_inputs("lacto_ferment", 18.0, organisms=["Nonexistent bacterium"]))
    assert body["sensory"]["nutrition_label"]


def test_forecast_survives_a_derived_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    good = predict(_inputs("kefir", 22.0), horizon_h=24)
    service.clear_caches()

    def boom(*a: object, **k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(derived, "evaluate", boom)
    bad = predict(_inputs("kefir", 22.0), horizon_h=24)
    assert bad["sensory"] is None and derived.FAILED_WARNING in bad["warnings"]

    def kinetic(b: dict[str, Any]) -> list[Any]:
        return [s for s in b["series"] if s["group"] not in ("taste", "nutrition")]

    assert kinetic(bad) == kinetic(good)  # the solve is unchanged by the derived layer
    assert np.isfinite(bad["series"][0]["p50"][-1])
