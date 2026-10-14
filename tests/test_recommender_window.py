"""Time window (design § 6, build plan B3), on hand-built arrays."""

from __future__ import annotations

import math

import numpy as np
import pytest

from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import library as L
from fermenttrack.recommender import window as W
from fermenttrack.recommender.window import Window

T = np.arange(0.0, 101.0)  # hourly grid, 0-100 h
D = (20.0, 40.0, 60.0)  # documented duration (lo, med, hi)
H = 100.0


def tri(center: float, width: float = 50.0) -> np.ndarray:
    """E peaking at 1.0 at `center`, falling 1/width per hour on both sides."""
    return np.clip(1.0 - np.abs(T - center) / width, 0.0, None)


def win(e: np.ndarray | None, mode: str = "proven", t_safe: float = 0.0, **kw: object) -> Window:
    off = kw.pop("off", {})
    horizon = kw.pop("horizon", H)
    return W.compute(T, e, off, t_safe, D, horizon, mode, **kw)  # type: ignore[arg-type]


def same(w: Window, taste_from: float, peak: float, stop_by: float) -> bool:
    return (w.taste_from_h, w.peak_h, w.stop_by_h) == pytest.approx((taste_from, peak, stop_by))


def test_constants() -> None:
    assert (W.EXPERIMENTAL_CEILING, W.DECLINE, W.OFF_NOTE_P) == (1.5, 0.8, 0.5)
    assert {"proven", "community", "experimental"} == W.MODES


def test_peak_is_the_argmax_and_stop_by_the_80_percent_decline() -> None:
    w = win(tri(40))  # E(t) < 0.8 once t > 50
    assert same(w, 20, 40, 50) and w.notes == ()


def test_interpolates_between_log_spaced_grid_times() -> None:
    t = [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0]
    e = [0.0, 0.2, 0.6, 1.0, 0.9, 0.5, 0.1]
    solvent = [0.0, 0.0, 0.1, 0.2, 0.3, 0.7, 0.9]  # reaches 0.5 halfway from 16 to 32 h
    w = W.compute(t, e, {"solvent": solvent}, 0.0, (4.0, 8.0, 32.0), 64.0, "proven")
    # 0.8 x 1.0 is crossed a quarter of the way from 16 h (0.9) to 32 h (0.5)
    assert same(w, 4, 8, 20)
    assert w.notes == ("solvent likely noticeable from about 24 h",)


def test_peak_ties_take_the_earliest_time() -> None:
    plateau = np.minimum(np.minimum(T / 30.0, 1.0), np.clip(1.0 - (T - 50.0) / 50.0, 0, 1))
    assert same(win(plateau), 20, 30, 60)


# ── ceilings and floor ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mode", "ceiling"), [("proven", 60), ("community", 60), ("experimental", 90)]
)
def test_proven_and_community_clip_to_d_hi_experimental_to_1_5_d_hi(
    mode: str, ceiling: float
) -> None:
    assert same(win(T / 100.0, mode), 20, ceiling, ceiling)


@pytest.mark.parametrize("mode", sorted(W.MODES))
def test_taste_from_is_never_below_d_lo(mode: str) -> None:
    w = win(tri(10), mode)  # E peaks at 10 h, before d_lo
    assert same(w, 20, 20, 28)  # E(20) = 0.8; below 0.64 after 28 h


# ── safety milestone ────────────────────────────────────────────────────────────────────────


def test_milestone_later_than_d_lo_delays_taste_from_and_the_peak_search() -> None:
    assert same(win(tri(25), t_safe=30.0), 30, 30, 39)  # E(30) = 0.9; below 0.72 after 39 h
    assert same(win(tri(40), t_safe=30.0), 30, 40, 50)


def test_milestone_past_the_ceiling_collapses_the_window_at_the_milestone() -> None:
    w = win(tri(40), t_safe=70.0)
    assert same(w, 70, 70, 70)
    assert w.notes == ("modelled acidification (P90) is slower than the documented duration",)
    assert same(win(tri(40), "experimental", t_safe=70.0), 70, 70, 74)


def test_milestone_not_reached_counts_as_the_end_of_the_forecast() -> None:
    w = win(tri(40), t_safe=math.inf)
    assert same(w, 100, 100, 100)
    assert w.notes == (
        "modelled acidification (P90) not reached within the forecast",
        "modelled acidification (P90) is slower than the documented duration",
    )
    w = win(tri(40), t_safe=math.inf, horizon=50.0)
    assert same(w, 50, 50, 60)
    assert w.notes == ("modelled acidification (P90) not reached within the forecast",)


# ── off-notes ───────────────────────────────────────────────────────────────────────────────


def test_off_note_before_the_peak_ends_the_window_and_pulls_the_peak_back() -> None:
    w = win(tri(40), off={"fishy": T / 60.0})  # P = 0.5 at 30 h, before the 40 h peak
    assert same(w, 20, 30, 30)
    assert w.notes == ("fishy likely noticeable from about 30 h (before the aroma peak)",)


def test_off_note_after_the_peak_ends_the_window_before_the_decline() -> None:
    w = win(tri(40), off={"fishy": T / 90.0})  # P = 0.5 at 45 h; the decline would be 50 h
    assert same(w, 20, 40, 45)
    assert w.notes == ("fishy likely noticeable from about 45 h",)


def test_off_note_already_likely_at_taste_from() -> None:
    w = win(tri(40), off={"cheesy": np.full_like(T, 0.6)})
    assert same(w, 20, 20, 20)


def test_off_note_only_counts_after_taste_from() -> None:
    transient = np.clip((15.0 - T) / 5.0, 0.0, 1.0)  # P >= 0.5 until 12.5 h, 0 from 15 h
    w = win(tri(40), off={"phenolic": transient})
    assert same(w, 20, 40, 50) and w.notes == ()


def test_the_earliest_off_notes_are_named() -> None:
    off = {"solvent": T / 100.0, "fishy": T / 90.0, "cheesy": T / 90.0}
    w = win(tri(40), off=off)
    assert same(w, 20, 40, 45)
    assert w.notes == ("cheesy, fishy likely noticeable from about 45 h",)


# ── no targets ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("m_user", "m_source", "peak"),
    [
        (30.0, 40.0, 30.0),  # warmer: the milestone comes sooner, so does the peak
        (80.0, 40.0, 60.0),  # clipped to d_hi
        (10.0, 40.0, 20.0),  # clipped to taste-from
        (None, None, 40.0),  # d_med
        (math.inf, 40.0, 40.0),
        (30.0, 0.0, 40.0),
    ],
)
def test_no_targets_peak_is_d_med_shifted_by_the_milestone_ratio(
    m_user: float | None, m_source: float | None, peak: float
) -> None:
    w = win(None, m_user_h=m_user, m_source_h=m_source)
    assert same(w, 20, peak, 60) and w.notes == ()


def test_no_targets_off_note_still_ends_the_window() -> None:
    w = win(None, off={"sulfurous": T / 70.0})  # P = 0.5 at 35 h, before d_med
    assert same(w, 20, 35, 35)
    assert w.notes == ("sulfurous likely noticeable from about 35 h",)


# ── beyond the horizon (Q26) ────────────────────────────────────────────────────────────────


def test_beyond_horizon_searches_the_peak_to_the_horizon_only() -> None:
    w = win(T / 100.0, horizon=30.0, model_scope=("beyond_horizon",), off={"fishy": T / 50.0})
    # peak at the horizon; taste-from and stop-by from the source; no model stop-by rules
    assert same(w, 20, 30, 60)
    assert w.notes == ("aroma estimate covers the first 1.25 days only",)


def test_beyond_horizon_window_starting_after_the_horizon_takes_the_documented_peak() -> None:
    w = win(T / 100.0, horizon=12.0, model_scope=("temp_outside_profile", "beyond_horizon"))
    assert same(w, 20, 40, 60)
    assert w.notes == (
        "aroma estimate covers the first 0.5 days only",
        "aroma peak lies past the forecast: peak from the documented duration",
    )


def test_beyond_horizon_window_starting_at_the_horizon_takes_the_documented_peak() -> None:
    red_miso = L.get("red_rice_miso_kagawa_long")
    assert red_miso is not None and red_miso.duration_h is not None
    d = red_miso.duration_h
    horizon = PROFILES["miso"].horizon_h
    assert (d.lo, d.median, d.hi, horizon) == (4320, 6540, 8760, 4320)  # d_lo == horizon
    t = np.geomspace(1.0, horizon, 24)
    w = W.compute(
        t, t / horizon, {}, 0.0, (d.lo, d.median, d.hi), horizon, "proven",
        model_scope=red_miso.model_scope,
    )  # fmt: skip
    assert same(w, 4320, 6540, 8760)
    assert w.notes == (
        "aroma estimate covers the first 180 days only",
        "aroma peak lies past the forecast: peak from the documented duration",
    )


# ── served temperature outside the profile (Q26) ────────────────────────────────────────────

SOURCE_NOTE = W.SOURCE_ONLY_NOTE


@pytest.mark.parametrize("clip", [True, False])
@pytest.mark.parametrize("mode", sorted(W.MODES))
def test_source_only_window_is_the_documented_span(mode: str, clip: bool) -> None:
    # Nothing from the model applies: not its milestone, off-notes, peak or ceilings.
    off = {"fishy": T / 60.0}
    w = win(tri(10), mode, t_safe=30.0, off=off, clip=clip, source_only=True)
    assert same(w, 20, 40, 60)
    assert w.notes == (SOURCE_NOTE,)
    assert same(win(None, mode, m_user_h=10.0, m_source_h=40.0, source_only=True), 20, 40, 60)


def test_source_only_keeps_the_horizon_note() -> None:
    scope = ("temp_outside_profile", "beyond_horizon")  # e.g. the sand-lance fish sauce
    w = win(T / 100.0, horizon=30.0, model_scope=scope, source_only=True)
    assert same(w, 20, 40, 60)
    assert w.notes == ("aroma estimate covers the first 1.25 days only", SOURCE_NOTE)


def test_part_of_the_span_outside_the_profile_keeps_the_model_window() -> None:
    assert win(tri(40), model_scope=("temp_outside_profile",)) == win(tri(40))


# ── unclipped, for evaluation (E3) ──────────────────────────────────────────────────────────


def test_unclipped_window_has_no_d_lo_floor_and_no_d_hi_ceiling() -> None:
    assert same(win(tri(10), t_safe=5.0, clip=False), 5, 10, 20)
    assert same(win(tri(10), t_safe=5.0), 20, 20, 28)
    assert same(win(T / 100.0, clip=False), 0, 100, 100)
    beyond = {"horizon": 30.0, "model_scope": ("beyond_horizon",)}
    assert win(T / 100.0, clip=False, **beyond) == win(T / 100.0, **beyond)


# ── inputs and invariants ───────────────────────────────────────────────────────────────────


def test_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="mode"):
        win(tri(40), "both")
    with pytest.raises(ValueError, match="duration"):
        W.compute(T, tri(40), {}, 0.0, (40.0, 20.0, 60.0), H, "proven")
    with pytest.raises(ValueError, match="one value per time"):
        win(tri(40)[:-1])
    with pytest.raises(ValueError, match="one value per time"):
        win(tri(40), off={"fishy": [0.1, 0.2]})
    with pytest.raises(ValueError, match="increasing"):
        W.compute(T[::-1], tri(40), {}, 0.0, D, H, "proven")


def test_window_invariants_on_random_series() -> None:
    rng = np.random.default_rng(20261008)
    for _ in range(300):
        d_lo, d_med, d_hi = np.sort(rng.uniform(1.0, 500.0, 3))
        horizon = float(rng.uniform(0.3, 2.0) * d_hi)
        t = np.unique(np.geomspace(1.0, 1.5 * d_hi, 24).tolist() + [d_lo, d_med, d_hi])
        e = None if rng.random() < 0.2 else rng.random(t.size)
        off = {"fishy": rng.random(t.size) * rng.uniform(0.0, 1.2)}
        t_safe = float(rng.choice([0.0, rng.uniform(0.0, 1.6 * d_hi), math.inf]))
        mode = str(rng.choice(sorted(W.MODES)))
        scope = ("beyond_horizon",) if rng.random() < 0.3 else ("in_range",)
        w = W.compute(t, e, off, t_safe, (d_lo, d_med, d_hi), horizon, mode, model_scope=scope)
        ceiling = d_hi * (1.5 if mode == "experimental" else 1.0)
        assert w.taste_from_h >= d_lo
        if math.isfinite(t_safe):
            assert w.taste_from_h >= t_safe  # never earlier than the safety milestone
        assert w.taste_from_h <= w.peak_h <= w.stop_by_h
        if w.taste_from_h <= ceiling:
            assert w.stop_by_h <= ceiling
