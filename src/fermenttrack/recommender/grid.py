"""The recommender's precomputed grid (design § 8): every active library recipe at its grid
temperatures, as E / U / P per series over time, milestone crossing times and card metadata.

Built by scripts/build_recommender_grid.py; how a recipe runs and how a run becomes these
statistics is recommender/run.py. Read lazily here, and the file is checked against its
manifest's hash on load.

Per series s (16 aroma series, 4 tastes) and member n, L = the engine's log10 summed odour
activity (`aroma:<s>`) or log10 taste activity ratio (`taste:<s>`), and with τ = score.TAU:
- E = Σ wₙ σ(Lₙ/τ); U = the weighted P90 of σ(Lₙ/τ); P = Σ wₙ 1[Lₙ > 0] (recommender.score).

A series the engine does not produce for a recipe is absent from the entry, never zero.
Statistics are stored as float16 (design § 8.2).
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
SCHEMA = 1
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
            )
            for key, r in index["recipes"].items()
        }
        self._rows = {key: tuple(r["rows"]) for key, r in index["recipes"].items()}

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

    def temps(self, recipe_key: str) -> tuple[float, ...]:
        return self.recipe(recipe_key).temps

    def _row(self, i: int) -> Entry:
        meta = self._index["entries"][i]
        n = int(self._n_t[i])
        stats = self._stats[i, :, :, :n].astype(np.float64)
        present = [j for j, _ in enumerate(self.series) if self._present[i, j]]
        by_stat = [
            MappingProxyType({self.series[j]: stats[k, j] for j in present})
            for k in range(len(STATISTICS))
        ]
        ms = self._milestones[i]
        return Entry(
            recipe_key=meta["recipe"],
            temp_c=meta["temp_c"],
            t_h=self._t[i, :n].astype(np.float64),
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
        )  # fmt: skip

    def entry(self, recipe_key: str, temp_c: float) -> Entry:
        """The entry at one of the recipe's grid temperatures (temps(recipe_key))."""
        temps = self.temps(recipe_key)
        for i, t in zip(self._rows[recipe_key], temps, strict=True):
            if abs(t - temp_c) <= _TEMP_TOL:
                return self._row(i)
        raise KeyError(f"{temp_c:g} °C is not a grid temperature of {recipe_key!r}")

    def interp_temp(self, recipe_key: str, temp_c: float) -> Entry:
        """Statistics and milestones linear in temperature between the two grid temperatures
        around temp_c, clamped to the end ones outside them (the card's interpolated window,
        design § 6). Series and milestones present at both temperatures only; metadata from
        the nearer grid temperature."""
        if not math.isfinite(temp_c):
            raise ValueError("temp_c must be a finite number")
        temps = self.temps(recipe_key)
        t = min(max(temp_c, temps[0]), temps[-1])
        k = bisect_left(temps, t - _TEMP_TOL)
        if abs(temps[k] - t) <= _TEMP_TOL:
            return replace(self.entry(recipe_key, temps[k]), temp_c=t)
        lo, hi = self.entry(recipe_key, temps[k - 1]), self.entry(recipe_key, temps[k])
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
        )  # fmt: skip


@cache
def load() -> Grid:
    """The committed grid, loaded (and hash-checked) on first use."""
    return Grid()


def version() -> str:
    return load().version()


def recipe(recipe_key: str) -> RecipeGrid:
    return load().recipe(recipe_key)


def temps(recipe_key: str) -> tuple[float, ...]:
    return load().temps(recipe_key)


def entry(recipe_key: str, temp_c: float) -> Entry:
    return load().entry(recipe_key, temp_c)


def interp_temp(recipe_key: str, temp_c: float) -> Entry:
    return load().interp_temp(recipe_key, temp_c)
