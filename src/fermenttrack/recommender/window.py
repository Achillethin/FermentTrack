"""The time window (design § 6): taste from / peak / stop by, in hours from the start.

Pure: the caller passes grid statistics on a time axis (the target-averaged E, the P of each
off-note in O \\ C), the P90 time of the safety milestone and the documented duration. Values
between grid times are linear in time. The safety milestone only delays tasting; it is never
shown as a clearance.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from fermenttrack.prediction.priors import FloatArray

MODES = frozenset({"proven", "community", "experimental"})
EXPERIMENTAL_CEILING = 1.5  # Experimental may run to 1.5 × d_hi
DECLINE = 0.8  # stop once E falls below this share of E(peak)
OFF_NOTE_P = 0.5  # an off-note this likely noticeable ends the window


@dataclass(frozen=True)
class Window:
    taste_from_h: float
    peak_h: float
    stop_by_h: float
    notes: tuple[str, ...] = ()


def _series(values: ArrayLike, t: FloatArray) -> FloatArray:
    v = np.asarray(values, dtype=np.float64)
    if v.shape != t.shape:
        raise ValueError("every series needs one value per time")
    return v


def _knots(t: FloatArray, start: float, end: float) -> FloatArray:
    return np.concatenate(([start], t[(t > start) & (t < end)], [end]))


def _argmax(t: FloatArray, v: FloatArray, start: float, end: float) -> float:
    """The earliest time of the maximum of v over [start, end]."""
    k = _knots(t, start, end)
    return float(k[int(np.argmax(np.interp(k, t, v)))])


def _first(
    t: FloatArray, v: FloatArray, start: float, end: float, level: float, *, rising: bool
) -> float | None:
    """The first time in [start, end] with v ≥ level (rising) or v < level (falling)."""
    if end < start:
        return None
    k = _knots(t, start, end)
    vals = np.interp(k, t, v)
    hit = vals >= level if rising else vals < level
    if not hit.any():
        return None
    i = int(np.argmax(hit))
    if i == 0:
        return start
    frac = (level - vals[i - 1]) / (vals[i] - vals[i - 1])
    return float(k[i - 1] + frac * (k[i] - k[i - 1]))


def _off_note(
    t: FloatArray, p: Mapping[str, FloatArray], start: float, end: float
) -> tuple[float | None, tuple[str, ...]]:
    """The first time any off-note reaches P ≥ 0.5, and which ones do then."""
    hits = {k: _first(t, v, start, end, OFF_NOTE_P, rising=True) for k, v in sorted(p.items())}
    found = {k: x for k, x in hits.items() if x is not None}
    if not found:
        return None, ()
    first = min(found.values())
    return first, tuple(k for k, x in found.items() if x == first)


def _kinetic_ratio(m_user_h: float | None, m_source_h: float | None) -> float:
    """m(T_user) / m(T_source); 1 when either median is unknown."""
    if m_user_h is None or m_source_h is None:
        return 1.0
    ok = all(math.isfinite(m) and m > 0 for m in (m_user_h, m_source_h))
    return m_user_h / m_source_h if ok else 1.0


def compute(
    times_h: ArrayLike,
    e: ArrayLike | None,
    off_note_p: Mapping[str, ArrayLike],
    t_safe_h: float,
    duration_h: tuple[float, float, float],
    horizon_h: float,
    mode: str,
    *,
    m_user_h: float | None = None,
    m_source_h: float | None = None,
    model_scope: Iterable[str] = (),
    clip: bool = True,
    source_only: bool = False,
) -> Window:
    """The window at one temperature.

    times_h: the grid times (increasing). e: the target-averaged E on them, None without
    targets. off_note_p: P of each off-note in O minus C (score.off_note_series). t_safe_h:
    the safety milestone's P90 crossing (0 without a pH safety line; inf if not reached).
    duration_h: the documented (lo, med, hi). mode: proven | community | experimental.
    m_user_h, m_source_h: median times to the profile's main milestone at the user's and the
    source's temperature (the no-target peak shift). clip=False gives the model's own window
    for evaluation (design § 13.1 E3): no d_lo floor, no d_hi ceiling, up to the last
    modelled time. source_only: set it when the recipe's served (median) temperature is
    outside the profile's temp_range (Q26, design § 4.3); the window is then the documented
    (lo, med, hi) in every mode, also with clip=False, because the model can't place time at
    a temperature it doesn't cover.
    """
    d_lo, d_med, d_hi = duration_h
    if not 0.0 <= d_lo <= d_med <= d_hi:
        raise ValueError("duration_h is (lo, med, hi)")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    t = np.asarray(times_h, dtype=np.float64)
    if t.ndim != 1 or t.size == 0 or np.any(np.diff(t) <= 0):
        raise ValueError("times_h must be strictly increasing")
    ev = None if e is None else _series(e, t)
    pv = {k: _series(v, t) for k, v in off_note_p.items()}

    notes: list[str] = []
    # Q26: past the horizon, aroma and peak run to the horizon; taste-from and stop-by come
    # from the source, also for evaluation.
    from_source = "beyond_horizon" in model_scope
    if from_source:
        notes.append(f"aroma estimate covers the first {horizon_h / 24:g} days only")
    if source_only:
        notes.append("window from the source: the model does not cover this temperature")
        return Window(float(d_lo), float(d_med), float(d_hi), tuple(notes))
    t_max = d_hi * (EXPERIMENTAL_CEILING if mode == "experimental" else 1.0)
    model_end = min(horizon_h, float(t[-1]))
    floor, ceiling = (d_lo, t_max) if clip or from_source else (0.0, model_end)

    if not math.isfinite(t_safe_h):
        notes.append("modelled acidification (P90) not reached within the forecast")
        t_safe_h = model_end
    taste_from = float(max(floor, t_safe_h))
    if taste_from > ceiling:  # never taste earlier than the milestone: the window collapses
        notes.append("modelled acidification (P90) is slower than the documented duration")
        return Window(taste_from, taste_from, taste_from, tuple(notes))

    search_end = min(ceiling, model_end)
    t_off, offenders = (None, ()) if from_source else _off_note(t, pv, taste_from, search_end)
    before_peak = False
    # Past the horizon the model has nothing inside a window that starts at the horizon.
    model_peak = taste_from < search_end if from_source else taste_from <= search_end
    if ev is not None and model_peak:
        peak = _argmax(t, ev, taste_from, search_end)
        if t_off is not None and t_off < peak:
            before_peak = True
            peak = _argmax(t, ev, taste_from, t_off)
    else:
        if ev is not None:
            notes.append("aroma peak lies past the forecast: peak from the documented duration")
        latest = ceiling if t_off is None else t_off
        peak = min(max(d_med * _kinetic_ratio(m_user_h, m_source_h), taste_from), latest)

    stop_by = ceiling
    if ev is not None and not from_source:
        level = DECLINE * float(np.interp(peak, t, ev))
        t_decline = _first(t, ev, peak, search_end, level, rising=False)
        if t_decline is not None:
            stop_by = min(stop_by, t_decline)
    if t_off is not None:
        stop_by = min(stop_by, t_off)
        where = " (before the aroma peak)" if before_peak else ""
        notes.append(f"{', '.join(offenders)} likely noticeable from about {t_off:.0f} h{where}")
    return Window(taste_from, float(peak), float(stop_by), tuple(notes))
