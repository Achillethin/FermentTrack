"""Recommendation scores (design § 5.3, build plan B3), on hand-built member arrays."""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from fermenttrack.prediction.aroma_data import COMPOUNDS
from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.recommender import score as S


def _sigma(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def test_constants() -> None:
    assert (S.TAU, S.LAMBDA, S.OPTIMISTIC_Q, S.CHARACTER_P) == (0.25, 0.5, 0.9, 0.5)
    assert (S.LOW_MED, S.MED_HIGH) == (0.33, 0.67)
    assert {"solvent", "sulfurous", "fishy", "cheesy", "phenolic"} == S.OFF_NOTES


def test_off_notes_are_aroma_series() -> None:
    series = {s for c in COMPOUNDS.values() for s in c.series}
    assert S.OFF_NOTES <= series


def test_soft_is_the_logistic_of_l_over_tau() -> None:
    assert S.soft(0.0) == pytest.approx(0.5)
    assert S.soft(0.25) == pytest.approx(_sigma(1.0))
    assert S.soft(-0.5) == pytest.approx(_sigma(-2.0))
    assert S.soft(0.5, tau=0.5) == pytest.approx(_sigma(1.0))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert S.soft([-1e6, 1e6]).tolist() == [0.0, 1.0]


L3 = np.array([[0.0, 0.25], [0.25, -0.25], [-0.25, 0.0]])  # 3 members x 2 times
W3 = np.array([0.5, 0.25, 0.25])


def test_central_is_the_weighted_mean_of_the_soft_indicator() -> None:
    expected = [
        0.5 * 0.5 + 0.25 * _sigma(1) + 0.25 * _sigma(-1),
        0.5 * _sigma(1) + 0.25 * _sigma(-1) + 0.25 * 0.5,
    ]
    assert S.central(L3, W3) == pytest.approx(expected)
    assert S.central(L3, 4 * W3) == pytest.approx(expected)  # weights are normalised
    assert S.central(L3[:, 0], W3) == pytest.approx(expected[0])


def test_central_tends_to_noticeable_for_sharp_signals() -> None:
    L = np.array([[2.0, -3.0], [-1.5, 4.0], [3.0, 2.5], [-2.0, -2.0]])
    w = np.array([0.1, 0.2, 0.3, 0.4])
    assert S.central(L, w) == pytest.approx(S.noticeable(L, w), abs=1e-3)


def test_noticeable_counts_l_strictly_above_zero() -> None:
    assert S.noticeable([0.0, 1e-9, -1.0], [1.0, 1.0, 1.0]) == pytest.approx(1 / 3)
    assert S.noticeable(L3, W3) == pytest.approx([0.25, 0.5])


def test_optimistic_is_the_weighted_p90_of_the_soft_indicator() -> None:
    L = np.array([-1.0, -0.5, 0.0, 0.5, 1.0])
    w = np.array([0.1, 0.1, 0.5, 0.25, 0.05])  # cumulative 0.1, 0.2, 0.7, 0.95, 1.0
    assert S.optimistic(L, w) == pytest.approx(_sigma(2.0))
    assert S.optimistic(L[::-1], w[::-1]) == pytest.approx(_sigma(2.0))  # order-free
    assert S.optimistic(L, 10 * w) == pytest.approx(_sigma(2.0))
    assert S.optimistic(L, np.full(5, 0.2)) == pytest.approx(_sigma(4.0))  # P90 of 5 = the top


def test_optimistic_uses_the_engines_weighted_quantile_per_time() -> None:
    rng = np.random.default_rng(7)
    L = rng.normal(0.0, 0.5, size=(64, 6))
    w = rng.random(64)
    u = S.optimistic(L, w)
    assert u.shape == (6,)
    assert u == pytest.approx(weighted_quantiles(S.soft(L), w / w.sum(), (0.9,))[0])
    for j in range(6):
        assert u[j] == pytest.approx(S.optimistic(L[:, j], w))
    assert np.all(u >= np.min(S.soft(L), axis=0))


def test_one_weight_per_member() -> None:
    for f in (S.central, S.optimistic, S.noticeable):
        with pytest.raises(ValueError):
            f(L3, [0.5, 0.5])


@pytest.mark.parametrize(
    "w", [[0.0, 0.0, 0.0], [0.5, 0.75, -0.25], [0.5, math.nan, 0.5], [0.5, math.inf, 0.5]]
)
def test_weights_must_be_finite_non_negative_and_not_all_zero(w: list[float]) -> None:
    for f in (S.central, S.optimistic, S.noticeable):
        with pytest.raises(ValueError, match="weights"):
            f(L3, w)


def test_target_average_is_the_mean_over_targets() -> None:
    per_series = {"fruity": [0.2, 0.4], "sour": [0.6, 0.8], "cheesy": [1.0, 1.0]}
    assert S.target_average(per_series, ["fruity", "sour"]) == pytest.approx([0.4, 0.6])
    assert S.target_average(per_series, ["sour"]) == pytest.approx([0.6, 0.8])
    assert S.target_average(per_series, ["sour", "sour", "fruity"]) == pytest.approx([0.4, 0.6])
    with pytest.raises(ValueError):
        S.target_average(per_series, [])
    with pytest.raises(KeyError):
        S.target_average(per_series, ["floral"])


def test_target_average_of_central_equals_central_of_the_member_mean() -> None:
    rng = np.random.default_rng(3)
    La, Lb = rng.normal(size=(2, 32, 4))
    w = rng.random(32)
    exact = (w / w.sum()) @ ((S.soft(La) + S.soft(Lb)) / 2)
    by_series = {"a": S.central(La, w), "b": S.central(Lb, w)}
    assert S.target_average(by_series, ["a", "b"]) == pytest.approx(exact)


def test_character_series_is_reported_plus_likely_at_median_duration() -> None:
    c = S.character_series(("fishy",), {"sulfurous": 0.5, "cheesy": 0.49, "fruity": 0.9})
    assert c == {"fishy", "sulfurous", "fruity"}
    assert S.character_series((), {}) == frozenset()


def test_off_note_series_excludes_targets_and_character() -> None:
    expected = {"solvent", "fishy", "phenolic"}
    assert S.off_note_series(["cheesy"], {"sulfurous", "fruity"}) == expected
    assert S.off_note_series([], []) == S.OFF_NOTES


VAR_P = {"solvent": 0.7, "sulfurous": 0.9, "fishy": 0.2, "cheesy": 0.6, "phenolic": 0.3}
PAR_P = {"solvent": 0.5, "sulfurous": 0.1, "fishy": 0.4, "cheesy": 0.1, "phenolic": 0.0}


def test_off_note_penalty_hand_computed() -> None:
    var_p, par_p = {**VAR_P, "fruity": 0.9}, {**PAR_P, "fruity": 0.1}  # fruity: not an off-note
    # solvent +0.2, fishy -0.2 -> 0, phenolic +0.3; cheesy is a target, sulfurous character
    assert S.off_note_penalty(var_p, par_p, ["cheesy"], {"sulfurous"}) == pytest.approx(0.25)
    assert S.off_note_penalty(var_p, par_p, ["cheesy"], {"sulfurous"}, lam=1) == pytest.approx(0.5)
    # every off-note counts without targets or character: 0.2 + 0.8 + 0 + 0.5 + 0.3
    assert S.off_note_penalty(var_p, par_p, [], []) == pytest.approx(0.5 * 1.8)


def test_a_sulfurous_kimchi_is_never_penalised_for_being_sulfurous() -> None:
    character = S.character_series(("sour", "pungent"), {"sulfurous": 0.8})
    assert S.off_note_penalty({"sulfurous": 1.0}, {"sulfurous": 0.8}, [], character) == 0.0


def test_off_note_penalty_treats_a_missing_series_as_zero() -> None:
    assert S.off_note_penalty({"solvent": 0.4}, {}, [], []) == pytest.approx(0.2)
    assert S.off_note_penalty({}, {"solvent": 0.4}, [], []) == 0.0


@pytest.mark.parametrize(
    ("e", "label"),
    [(0.0, "Low"), (0.3299, "Low"), (0.33, "Med"), (0.6699, "Med"), (0.67, "High"), (1.0, "High")],
)
def test_low_med_high_thresholds(e: float, label: str) -> None:
    assert S.low_med_high(e) == label


@pytest.mark.parametrize("e", [math.nan, math.inf, -math.inf])
def test_low_med_high_rejects_a_non_finite_score(e: float) -> None:
    with pytest.raises(ValueError):
        S.low_med_high(e)
