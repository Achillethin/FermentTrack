"""Additive screening (design § 8.5, build plan B7): logit-additive per series and time,
clipped to ±6, on hand-built entries; and the service's screened statistics on the grid."""

from __future__ import annotations

import math
from types import MappingProxyType

import numpy as np
import pytest

from fermenttrack.recommender import grid, library, operators, screen
from fermenttrack.recommender import service as S

T = np.array([1.0, 10.0, 100.0])
KRAUT = "sauerkraut_dry_salted"


def _entry(
    e: dict[str, list[float]],
    *,
    safe: tuple[float, float, float, float] = (10.0, 20.0, 30.0, 1.0),
    top: dict[str, tuple[str, str]] | None = None,
    t: np.ndarray = T,
) -> grid.Entry:
    arrays = {s: np.asarray(v, dtype=np.float64) for s, v in e.items()}
    stats = MappingProxyType(arrays)
    return grid.Entry(
        recipe_key="r", temp_c=20.0, t_h=t, e=stats, u=stats, p=stats,
        milestones=MappingProxyType({grid.SAFETY_MILESTONE: grid.MilestoneTimes(*safe)}),
        members=160, schedule=(), top_compound=MappingProxyType(top or {}), not_modelled=(),
        skipped=(),
    )  # fmt: skip


def _lg(p: float) -> float:
    return math.log(p / (1.0 - p))


def test_logit_and_expit_are_inverse_and_clipped() -> None:
    p = np.array([0.01, 0.2, 0.5, 0.9, 0.99])
    np.testing.assert_allclose(screen.expit(screen.logit(p)), p)
    assert screen.logit(0.0)[()] == -screen.CLIP and screen.logit(1.0)[()] == screen.CLIP
    assert screen.logit(1e-9)[()] == -screen.CLIP


def test_one_operator_at_the_same_temperature_is_its_own_entry() -> None:
    parent = _entry({"fruity": [0.1, 0.3, 0.5]})
    variant = _entry({"fruity": [0.2, 0.6, 0.7]})
    got = screen.screen(parent, [screen.Component(variant, parent)])
    np.testing.assert_allclose(got.e["fruity"], variant.e["fruity"])


def test_differences_add_in_logit_space() -> None:
    parent = _entry({"fruity": [0.1, 0.3, 0.5]})
    a = _entry({"fruity": [0.2, 0.4, 0.5]})
    b = _entry({"fruity": [0.1, 0.6, 0.4]})
    other_parent = _entry({"fruity": [0.15, 0.35, 0.55]})  # b's pair read elsewhere
    got = screen.screen(parent, [screen.Component(a, parent), screen.Component(b, other_parent)])
    for i, (p, x, y, q) in enumerate(zip([0.1, 0.3, 0.5], [0.2, 0.4, 0.5], [0.1, 0.6, 0.4],
                                         [0.15, 0.35, 0.55], strict=True)):  # fmt: skip
        want = _lg(p) + (_lg(x) - _lg(p)) + (_lg(y) - _lg(q))
        assert got.e["fruity"][i] == pytest.approx(1.0 / (1.0 + math.exp(-want)))
    pairs = [screen.Component(b, other_parent), screen.Component(a, parent)]
    swapped = screen.screen(parent, pairs)
    np.testing.assert_allclose(swapped.e["fruity"], got.e["fruity"])  # order-free
    np.testing.assert_allclose(got.u["fruity"], got.e["fruity"])  # U and P screened the same
    np.testing.assert_allclose(got.p["fruity"], got.e["fruity"])


def test_logits_are_clipped_at_6() -> None:
    parent = _entry({"fruity": [0.5, 0.5, 0.5]})
    up = _entry({"fruity": [0.999, 0.999, 0.999]})
    got = screen.screen(parent, [screen.Component(up, parent)] * 3)
    np.testing.assert_allclose(got.e["fruity"], screen.expit(screen.CLIP))
    down = _entry({"fruity": [1e-6, 1e-6, 1e-6]})
    low = screen.screen(parent, [screen.Component(down, parent)] * 3)
    np.testing.assert_allclose(low.e["fruity"], screen.expit(-screen.CLIP))


def test_a_series_absent_somewhere_counts_as_zero_and_absent_everywhere_stays_absent() -> None:
    parent = _entry({"sour": [0.1, 0.5, 0.9]})
    fishy = _entry({"sour": [0.1, 0.5, 0.9], "fishy": [0.3, 0.4, 0.5]})
    got = screen.screen(parent, [screen.Component(fishy, parent)])
    np.testing.assert_allclose(got.e["fishy"], [0.3, 0.4, 0.5])  # −6 + (logit − (−6))
    assert "floral" not in got.e
    only = screen.screen(parent, [screen.Component(fishy, parent)], series=["sour"])
    assert set(only.e) == {"sour"}


def test_milestones_are_the_latest_and_labels_the_strongest() -> None:
    parent = _entry({"fruity": [0.1, 0.2, 0.3]}, safe=(10, 20, 30, 1.0), top={"fruity": ("a", "x")})
    slower = _entry({"fruity": [0.1, 0.8, 0.9]}, safe=(12, 18, math.inf, 0.6),
                    top={"fruity": ("b", "y")})  # fmt: skip
    got = screen.screen(parent, [screen.Component(slower, parent)])
    m = got.milestones[grid.SAFETY_MILESTONE]
    assert (m.p10, m.p50, m.p90, m.reached) == (12, 20, math.inf, 0.6)
    assert got.top_compound["fruity"] == ("b", "y")


def test_screening_needs_one_time_axis() -> None:
    parent = _entry({"fruity": [0.1, 0.2, 0.3]})
    other = _entry({"fruity": [0.1, 0.2, 0.3]}, t=np.array([1.0, 5.0, 100.0]))
    with pytest.raises(ValueError, match="time axis"):
        screen.screen(parent, [screen.Component(other, parent)])


# ── the service on the grid ─────────────────────────────────────────────


def _variant(key: str, *op_keys: str) -> S.Variant:
    recipe = library.get(key)
    assert recipe is not None
    ops = {op.key: op for op in operators.singles(recipe, usda_ids=[169941])}
    return S.make_variant(S.Parent(recipe, "library", recipe.name), [ops[k] for k in op_keys])


def test_one_grid_operator_is_its_grid_entry_not_screened() -> None:
    v = _variant(KRAUT, "add:Fresh ginger")
    temp = S.variant_temperature(v, None)
    assert not v.screened
    got = S.screened_statistics(v, temp)
    want = grid.interp_temp(KRAUT, temp.served_c, "add:Fresh ginger")
    np.testing.assert_array_equal(got.e["pungent"], want.e["pungent"])


def test_two_operators_are_screened_from_their_grid_entries() -> None:
    v = _variant(KRAUT, "add:Fresh ginger", "swap:Cabbage>Napa cabbage")
    temp = S.variant_temperature(v, None)  # 22.5 °C: a grid temperature of all three
    assert v.screened and temp.served_c == 22.5
    got = S.screened_statistics(v, temp)
    base = grid.entry(KRAUT, 22.5)
    parts = [screen.Component(grid.entry(KRAUT, 22.5, k), base)
             for k in ("add:Fresh ginger", "swap:Cabbage>Napa cabbage")]  # fmt: skip
    want = screen.screen(base, parts)
    assert set(got.e) == set(want.e)
    for s in want.e:
        np.testing.assert_allclose(got.e[s], want.e[s])
        np.testing.assert_allclose(got.p[s], want.p[s])


def test_a_temperature_operator_reads_the_parent_on_its_axis() -> None:
    v = _variant(KRAUT, "temp:24", "add:Fresh ginger")
    temp = S.variant_temperature(v, None)
    assert (temp.served_c, temp.slider_c, temp.source_only) == (24.0, None, False)
    got = S.screened_statistics(v, temp)
    assert got.temp_c == 24.0  # the axis has the 24 °C temperature-operator entry
    base = grid.entry(KRAUT, 24.0, "temp:24")
    ginger = screen.Component(grid.entry(KRAUT, 22.5, "add:Fresh ginger"), grid.entry(KRAUT, 22.5))
    np.testing.assert_allclose(got.e["sour"], screen.screen(base, [ginger]).e["sour"])


def test_a_usda_food_adds_nothing_until_confirmed() -> None:
    v = _variant(KRAUT, "usda:fdc:169941")
    temp = S.variant_temperature(v, None)
    assert v.screened  # its effect is unknown until a live forecast
    got = S.screened_statistics(v, temp)
    np.testing.assert_array_equal(got.e["sour"], grid.interp_temp(KRAUT, temp.served_c).e["sour"])
