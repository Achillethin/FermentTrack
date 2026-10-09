"""Additive screening of operator combinations (design § 8.5, Q19).

For a combination K of single operators on a parent p, per series s and time t:

    logit Ê_s^K(t) = logit E_s^p(t) + Σ_{k∈K} [logit E_s^{p+k}(t) − logit E_s^p(t)]

with every logit clipped to ±CLIP. U is screened the same way, and so is P (the window's
off-note rule and the off-note penalty read it). A series absent from an entry (the engine does
not produce it there) counts as 0, logit −CLIP, when another entry has it; absent everywhere,
it stays absent.

The caller chooses where each term is read (recommender.service): the parent term at the
variant's temperature, each operator's pair (p + k, p) at one temperature where the grid has
both, so every difference is like for like. The logits and differences depend on the grid only,
so the caller can keep them (`logits`, `difference`) and screen many combinations by summing
(`assemble`). Milestones take the latest crossing over the entries (P10, P50, P90) and the
smallest reached share: tasting is never placed earlier than any component would. Card labels:
each series' top compound comes from the entry with the highest E for that series.

Screened values are an approximation until a live forecast confirms them (design § 10.1); a
card shows "screened" until then.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import ArrayLike

from fermenttrack.prediction.priors import FloatArray
from fermenttrack.recommender import grid

CLIP = 6.0  # logit units (design § 8.5)
STATS = ("e", "u", "p")
_P_MIN = 0.5 * (1.0 + np.tanh(-0.5 * CLIP))  # σ(−CLIP): probabilities are floored here

# stat ("e", "u", "p") -> series -> values; a series absent from the entry is absent here
Logits = Mapping[str, Mapping[str, FloatArray]]


def logit(p: ArrayLike) -> FloatArray:
    """log(p / (1 − p)), clipped to ±CLIP (p = 0 and 1 included)."""
    x = np.clip(np.asarray(p, dtype=np.float64), _P_MIN, 1.0 - _P_MIN)
    return np.asarray(np.clip(np.log(x) - np.log1p(-x), -CLIP, CLIP), dtype=np.float64)


def expit(x: ArrayLike) -> FloatArray:
    """The logistic function (no exp overflow)."""
    return 0.5 * (1.0 + np.tanh(0.5 * np.asarray(x, dtype=np.float64)))


def logits(entry: grid.Entry, series: Iterable[str]) -> Logits:
    """The entry's E, U and P as logits, for the series it has among `series`."""
    keys = list(series)
    return MappingProxyType({
        k: MappingProxyType({s: logit(getattr(entry, k)[s]) for s in keys if s in entry.e})
        for k in STATS
    })  # fmt: skip


def difference(variant: Logits, parent: Logits) -> Logits:
    """logit(with the operator) − logit(without), per stat and series; a side without the
    series counts as −CLIP."""
    out = {}
    for k in STATS:
        a, b = variant[k], parent[k]
        out[k] = MappingProxyType({
            s: np.asarray(a.get(s, -CLIP) - b.get(s, -CLIP), dtype=np.float64)
            for s in sorted({*a, *b})
        })  # fmt: skip
    return MappingProxyType(out)


def _milestones(entries: Sequence[grid.Entry]) -> Mapping[str, grid.MilestoneTimes]:
    out = {}
    for name in entries[0].milestones:
        ms = [e.milestones[name] for e in entries if name in e.milestones]
        out[name] = grid.MilestoneTimes(
            max(m.p10 for m in ms), max(m.p50 for m in ms), max(m.p90 for m in ms),
            min(m.reached for m in ms),
        )  # fmt: skip
    return MappingProxyType(out)


def assemble(
    parent: grid.Entry,
    base: Logits,
    diffs: Sequence[Logits],
    variants: Sequence[grid.Entry],
) -> grid.Entry:
    """The screened entry: `parent` (read at the variant's temperature) and its logits `base`,
    plus one difference per operator that has grid entries (`variants`: the p + k entries, for
    milestones and labels). An operator without grid entries (a (v) USDA food) adds 0."""
    stats = []
    for k in STATS:
        keys = sorted({*base[k], *(s for d in diffs for s in d[k])})
        out = {}
        for s in keys:
            total = base[k].get(s, -CLIP)
            for d in diffs:
                if s in d[k]:
                    total = total + d[k][s]
            out[s] = expit(np.clip(total, -CLIP, CLIP))
        stats.append(MappingProxyType(out))
    entries = [parent, *variants]
    top = {}
    for s in stats[0]:
        holders = [e for e in entries if s in e.e and s in e.top_compound]
        if holders:
            top[s] = max(holders, key=lambda e: float(np.max(e.e[s]))).top_compound[s]
    names = dict.fromkeys(n for e in entries for n in e.not_modelled)
    skipped = dict.fromkeys(n for e in entries for n in e.skipped)
    return grid.Entry(
        recipe_key=parent.recipe_key, temp_c=parent.temp_c, t_h=parent.t_h, e=stats[0],
        u=stats[1], p=stats[2], milestones=_milestones(entries),
        members=min(e.members for e in entries), schedule=parent.schedule,
        top_compound=MappingProxyType(top), not_modelled=tuple(names), skipped=tuple(skipped),
    )  # fmt: skip


@dataclass(frozen=True)
class Component:
    """One operator's grid entries at one temperature: the parent with it, and without it."""

    variant: grid.Entry
    parent: grid.Entry


def screen(
    parent: grid.Entry, components: Sequence[Component], series: Iterable[str] | None = None
) -> grid.Entry:
    """The screened entry of a combination in one call (see assemble). series: only these
    (default: every series of any entry)."""
    for c in components:
        if not (np.array_equal(c.variant.t_h, parent.t_h)
                and np.array_equal(c.parent.t_h, parent.t_h)):  # fmt: skip
            raise ValueError("screening needs every entry on the parent's time axis")
    if series is None:
        every = (parent, *(e for c in components for e in (c.variant, c.parent)))
        series = sorted({s for e in every for s in e.e})
    keys = tuple(series)
    diffs = [difference(logits(c.variant, keys), logits(c.parent, keys)) for c in components]
    return assemble(parent, logits(parent, keys), diffs, [c.variant for c in components])
