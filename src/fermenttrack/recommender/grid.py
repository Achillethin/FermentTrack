"""The recommender's precomputed grid (design § 8): every active library recipe at its grid
temperatures, and every single grid operator applied to it (recommender.operators: (i), (ii)
at the recipe's grid temperatures, (iii) at its own temperature), as E / U / P per series over
time, milestone crossing times and card metadata.

Built by scripts/build_recommender_grid.py; how a recipe runs and how a run becomes these
statistics is recommender/run.py. Read lazily here, and the file is checked against its
manifest's hash on load.

Per series s (16 aroma series, 4 tastes) and member n, L = the engine's log10 summed odour
activity (`aroma:<s>`) or log10 taste activity ratio (`taste:<s>`), and with τ = score.TAU:
- E = Σ wₙ σ(Lₙ/τ); U = the weighted P90 of σ(Lₙ/τ); P = Σ wₙ 1[Lₙ > 0] (recommender.score).

A series the engine does not produce for a recipe is absent from the entry, never zero.
Statistics are stored as float16 (design § 8.2).

Entries are addressed by (recipe key, temperature, operator key); operator None is the recipe
itself. A temperature operator (iii) is the recipe at another temperature: where that is one
of the recipe's grid temperatures its entry shares the recipe's row. `axis` / `interp_axis`
read the recipe on its grid temperatures plus its temperature operators' (screening, § 8.5),
while `temps` / `interp_temp` stay on the grid temperatures (the Proven cards).
"""

from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from fermenttrack.prediction.priors import FloatArray

HERE = Path(__file__).parent
PACKAGE = HERE.parent  # src/fermenttrack
GRID_NPZ = HERE / "recommender_grid_v1.npz"
MANIFEST_JSON = HERE / "recommender_grid_v1.manifest.json"
REBUILD = "python scripts/build_recommender_grid.py --workers 4"
SCHEMA = 2  # 2: operator entries (B7)
MAX_BYTES = 5 * 1024 * 1024  # design § 8.2: over budget, the npz becomes a release asset
STATISTICS = ("E", "U", "P")
SAFETY_MILESTONE = "ph_below_4_6"  # stored wherever the profile has ph_safety_line
LEVAIN_PEAK = "levain_peak"  # sourdough (bake) entries only
# Design § 8.3: a change to any of these makes the grid stale. Paths are relative to the
# fermenttrack package; an absent file hashes as None.
INPUTS = (
    "prediction/profiles.py",
    "prediction/aroma_compounds_v1.csv",
    "prediction/aroma_data.py",
    "recommender/recipes_v1.csv",
    "recommender/recipe_ingredients_v1.csv",
    "recommender/ingredient_use_levels_v1.csv",
)
_TEMP_TOL = 1e-6
AXIS = "@axis"  # internal: a recipe's grid temperatures plus its temperature operators'
_INTERP_CACHE = 4096  # interpolated entries kept (cards ask for the same temperatures again)


class GridError(RuntimeError):
    """The grid file is missing, or does not match its manifest."""


def sha256_text(path: Path) -> str:
    """Hash of a text input, line endings normalised: a CRLF checkout (core.autocrlf) must
    hash like the LF one in the repository."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_hashes() -> dict[str, str | None]:
    """The current hash of every grid input (design § 8.3)."""
    return {
        name: sha256_text(PACKAGE / name) if (PACKAGE / name).exists() else None for name in INPUTS
    }


@dataclass(frozen=True)
class MilestoneTimes:
    """Crossing time quantiles over the members, hours from the start. inf: that share of
    the members does not cross within the span searched (RecipeGrid.milestone_end_h)."""

    p10: float
    p50: float
    p90: float
    reached: float  # the weighted share of members that cross it


@dataclass(frozen=True)
class Entry:
    recipe_key: str
    temp_c: float  # the grid temperature (interp_temp: the requested one, clamped)
    t_h: FloatArray  # (L,) strictly increasing: 24 log-spaced + documented d_lo/d_med/d_hi
    e: Mapping[str, FloatArray]  # series -> (L,); present series only
    u: Mapping[str, FloatArray]
    p: Mapping[str, FloatArray]
    milestones: Mapping[str, MilestoneTimes]
    members: int
    # the planned temperature the entry ran with, (start hour, °C); () = constant temp_c
    schedule: tuple[tuple[float, float], ...]
    # aroma series -> (its top compound, that compound's evidence tier), for card labels
    top_compound: Mapping[str, tuple[str, str]]
    not_modelled: tuple[str, ...]  # ingredients without aroma data
    skipped: tuple[str, ...]  # recipe rows not run: not a catalogue ingredient (`new`) or no mass
    operator: str | None = None  # the grid operator applied (operators.Operator.key); None: none


@dataclass(frozen=True)
class OperatorGrid:
    """One single grid operator of a recipe: its kind and where it was computed."""

    key: str
    kind: str  # add | swap | temperature
    temps: tuple[float, ...]  # kept temperatures, increasing
    dropped: tuple[tuple[float, tuple[str, ...]], ...]  # (°C, why), e.g. the gate's reasons


@dataclass(frozen=True)
class RecipeGrid:
    key: str
    fermentation_type: str
    engine: str  # "service" (prediction.service) | "bake" (prediction.bake, sourdough)
    temps: tuple[float, ...]  # kept grid temperatures, increasing
    dropped: tuple[tuple[float, tuple[str, ...]], ...]  # (°C, gate reasons)
    duration_h: tuple[float, float, float] | None  # documented (lo, med, hi); None: planner
    horizon_h: float  # the profile horizon
    end_h: float  # the last grid time: min(1.5 * d_hi, horizon_h), or horizon_h
    milestone_end_h: float  # milestone crossings were searched over [0, this]
    operators: tuple[OperatorGrid, ...] = ()  # the single grid operators, sorted by key


def _lerp(a: float, b: float, f: float) -> float:
    if f <= 0.0:
        return a
    if f >= 1.0:
        return b
    if math.isinf(a) or math.isinf(b):  # not reached on one side: not reached
        return math.inf
    return (1.0 - f) * a + f * b


class Grid:
    """One loaded grid file. Use the module-level functions for the committed grid."""

    def __init__(self, npz: Path = GRID_NPZ, manifest: Path = MANIFEST_JSON) -> None:
        if not npz.exists() or not manifest.exists():
            raise GridError(f"no recommender grid at {npz}: run `{REBUILD}`")
        self.manifest: dict[str, Any] = json.loads(manifest.read_text(encoding="utf-8"))
        digest = sha256_file(npz)
        if digest != self.manifest.get("grid_sha256"):
            raise GridError(f"{npz.name} does not match its manifest: run `{REBUILD}`")
        self._version = digest
        with np.load(npz, allow_pickle=False) as z:
            arrays = {k: z[k] for k in z.files}
        index = json.loads(arrays["index"].tobytes().decode("utf-8"))
        if index["schema"] != SCHEMA:
            raise GridError(f"grid schema {index['schema']} != {SCHEMA}: run `{REBUILD}`")
        self.series: tuple[str, ...] = tuple(index["series"])
        self.kinds: Mapping[str, str] = MappingProxyType(dict(index["kinds"]))
        self._index = index
        self._t = arrays["t_h"]
        self._n_t = arrays["n_t"]
        self._stats = arrays["stats"]
        self._present = arrays["present"]
        self._milestones = arrays["milestones"]
        self._recipes = {
            key: RecipeGrid(
                key=key,
                fermentation_type=r["fermentation_type"],
                engine=r["engine"],
                temps=tuple(r["temps"]),
                dropped=tuple((d["temp_c"], tuple(d["reasons"])) for d in r["dropped"]),
                duration_h=None if r["duration_h"] is None else tuple(r["duration_h"]),
                horizon_h=r["horizon_h"],
                end_h=r["end_h"],
                milestone_end_h=r["milestone_end_h"],
                operators=tuple(
                    OperatorGrid(
                        op, o["kind"], tuple(o["temps"]),
                        tuple((d["temp_c"], tuple(d["reasons"])) for d in o["dropped"]),
                    )  # fmt: skip
                    for op, o in sorted(r["operators"].items())
                ),
            )
            for key, r in index["recipes"].items()
        }
        # (recipe, operator) -> (temps, rows); operator None: the recipe itself
        self._axes: dict[tuple[str, str | None], tuple[tuple[float, ...], tuple[int, ...]]] = {}
        for key, r in index["recipes"].items():
            self._axes[key, None] = (tuple(r["temps"]), tuple(r["rows"]))
            by_temp = dict(zip(r["temps"], r["rows"], strict=True))
            for op, o in r["operators"].items():
                self._axes[key, op] = (tuple(o["temps"]), tuple(o["rows"]))
                if o["kind"] == "temperature":
                    by_temp.update(zip(o["temps"], o["rows"], strict=True))
            axis = sorted(by_temp.items())
            self._axes[key, AXIS] = (tuple(t for t, _ in axis), tuple(i for _, i in axis))
        self._entries: dict[int, Entry] = {}
        self._interp: dict[tuple[str, str | None, float], Entry] = {}

    def version(self) -> str:
        """The grid's identity for stored forecasts (B5's grid_version): the npz sha256."""
        return self._version

    def recipe_keys(self) -> tuple[str, ...]:
        return tuple(self._recipes)

    def recipe(self, recipe_key: str) -> RecipeGrid:
        try:
            return self._recipes[recipe_key]
        except KeyError:
            raise KeyError(f"{recipe_key!r} is not in the recommender grid") from None

    def operators(self, recipe_key: str) -> tuple[str, ...]:
        """The recipe's single grid operators (operators.Operator.key), sorted."""
        return tuple(o.key for o in self.recipe(recipe_key).operators)

    def _axis(
        self, recipe_key: str, operator: str | None
    ) -> tuple[tuple[float, ...], tuple[int, ...]]:
        self.recipe(recipe_key)
        try:
            return self._axes[recipe_key, operator]
        except KeyError:
            raise KeyError(f"{operator!r} is not a grid operator of {recipe_key!r}") from None

    def temps(self, recipe_key: str, operator: str | None = None) -> tuple[float, ...]:
        return self._axis(recipe_key, operator)[0]

    def axis(self, recipe_key: str) -> tuple[float, ...]:
        """The recipe's grid temperatures plus its temperature operators' (iii)."""
        return self._axis(recipe_key, AXIS)[0]

    def _row(self, i: int) -> Entry:
        cached = self._entries.get(i)
        if cached is not None:
            return cached
        meta = self._index["entries"][i]
        n = int(self._n_t[i])
        stats = self._stats[i, :, :, :n].astype(np.float64)
        stats.flags.writeable = False  # rows are shared by every caller
        t_h = self._t[i, :n].astype(np.float64)
        t_h.flags.writeable = False
        present = [j for j, _ in enumerate(self.series) if self._present[i, j]]
        by_stat = [
            MappingProxyType({self.series[j]: stats[k, j] for j in present})
            for k in range(len(STATISTICS))
        ]
        ms = self._milestones[i]
        row = Entry(
            recipe_key=meta["recipe"],
            temp_c=meta["temp_c"],
            t_h=t_h,
            e=by_stat[0],
            u=by_stat[1],
            p=by_stat[2],
            milestones=MappingProxyType({
                name: MilestoneTimes(*(float(x) for x in ms[j]))
                for j, name in enumerate(meta["milestones"])
            }),
            members=meta["members"],
            schedule=tuple((h, c) for h, c in meta["schedule"]),
            top_compound=MappingProxyType(
                {s: (c, t) for s, (c, t) in meta["top_compound"].items()}
            ),
            not_modelled=tuple(meta["not_modelled"]),
            skipped=tuple(meta["skipped"]),
            operator=meta["operator"],
        )  # fmt: skip
        self._entries[i] = row
        return row

    def _at(self, recipe_key: str, temp_c: float, operator: str | None) -> Entry:
        temps, rows = self._axis(recipe_key, operator)
        for i, t in zip(rows, temps, strict=True):
            if abs(t - temp_c) <= _TEMP_TOL:
                row = self._row(i)
                op = None if operator == AXIS else operator
                return row if row.operator == op else replace(row, operator=op)
        where = "on the axis" if operator == AXIS else f"of {operator!r}" if operator else ""
        raise KeyError(f"{temp_c:g} °C is not a grid temperature {where} of {recipe_key!r}")

    def entry(self, recipe_key: str, temp_c: float, operator: str | None = None) -> Entry:
        """The entry at one of the grid temperatures of the recipe, or of one of its grid
        operators (temps(recipe_key, operator))."""
        return self._at(recipe_key, temp_c, operator)

    def interp_temp(self, recipe_key: str, temp_c: float, operator: str | None = None) -> Entry:
        """Statistics and milestones linear in temperature between the two grid temperatures
        around temp_c, clamped to the end ones outside them (the card's interpolated window,
        design § 6). Series and milestones present at both temperatures only; metadata from
        the nearer grid temperature. operator: a grid operator's temperatures instead."""
        return self._interpolate(recipe_key, temp_c, operator)

    def interp_axis(self, recipe_key: str, temp_c: float) -> Entry:
        """interp_temp on the axis: the grid temperatures plus the temperature operators'."""
        return self._interpolate(recipe_key, temp_c, AXIS)

    def _interpolate(self, recipe_key: str, temp_c: float, operator: str | None) -> Entry:
        if not math.isfinite(temp_c):
            raise ValueError("temp_c must be a finite number")
        cache_key = (recipe_key, operator, float(temp_c))
        cached = self._interp.get(cache_key)  # one read: another thread may clear the cache
        if cached is not None:
            return cached
        temps = self._axis(recipe_key, operator)[0]
        t = min(max(temp_c, temps[0]), temps[-1])
        k = bisect_left(temps, t - _TEMP_TOL)
        if abs(temps[k] - t) <= _TEMP_TOL:
            out = replace(self._at(recipe_key, temps[k], operator), temp_c=t)
        else:
            lo = self._at(recipe_key, temps[k - 1], operator)
            hi = self._at(recipe_key, temps[k], operator)
            out = _mix(recipe_key, lo, hi, t)
        if len(self._interp) >= _INTERP_CACHE:
            self._interp.clear()
        self._interp[cache_key] = out
        return out


def _mix(recipe_key: str, lo: Entry, hi: Entry, t: float) -> Entry:
    f = (t - lo.temp_c) / (hi.temp_c - lo.temp_c)
    near = lo if f < 0.5 else hi

    def mix(a: Mapping[str, FloatArray], b: Mapping[str, FloatArray]) -> Mapping[str, Any]:
        return MappingProxyType({s: (1.0 - f) * a[s] + f * b[s] for s in a if s in b})

    milestones = {
        name: MilestoneTimes(*(
            _lerp(getattr(m, x), getattr(hi.milestones[name], x), f)
            for x in ("p10", "p50", "p90", "reached")
        ))
        for name, m in lo.milestones.items()
        if name in hi.milestones
    }  # fmt: skip
    return Entry(
        recipe_key=recipe_key, temp_c=t, t_h=lo.t_h, e=mix(lo.e, hi.e), u=mix(lo.u, hi.u),
        p=mix(lo.p, hi.p), milestones=MappingProxyType(milestones),
        members=min(lo.members, hi.members), schedule=near.schedule,
        top_compound=near.top_compound, not_modelled=near.not_modelled, skipped=near.skipped,
        operator=near.operator,
    )  # fmt: skip


@cache
def load() -> Grid:
    """The committed grid, loaded (and hash-checked) on first use."""
    return Grid()


def version() -> str:
    return load().version()


def recipe(recipe_key: str) -> RecipeGrid:
    return load().recipe(recipe_key)


def temps(recipe_key: str, operator: str | None = None) -> tuple[float, ...]:
    return load().temps(recipe_key, operator)


def operators(recipe_key: str) -> tuple[str, ...]:
    return load().operators(recipe_key)


def axis(recipe_key: str) -> tuple[float, ...]:
    return load().axis(recipe_key)


def entry(recipe_key: str, temp_c: float, operator: str | None = None) -> Entry:
    return load().entry(recipe_key, temp_c, operator)


def interp_temp(recipe_key: str, temp_c: float, operator: str | None = None) -> Entry:
    return load().interp_temp(recipe_key, temp_c, operator)


def interp_axis(recipe_key: str, temp_c: float) -> Entry:
    return load().interp_axis(recipe_key, temp_c)
