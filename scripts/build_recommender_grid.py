"""Build the recommender's precomputed grid (design § 8.4): every active library recipe at its
grid temperatures, through the forecast engine with no readings, summarised per series as
E / U / P over time, plus milestone crossing times and card metadata. Writes
src/fermenttrack/recommender/recommender_grid_v1.npz and its manifest; recommender/grid.py
reads them and tests/test_recommender_grid.py checks they are current.

Run: python scripts/build_recommender_grid.py --workers 4
     python scripts/build_recommender_grid.py --recipes KEY [KEY ...] --out DIR   (a subset)

How a recipe runs: recommender/run.py (shared with the live forecast). Here:
- Temperatures (§ 8.1): the profile's temp_range[0], temp_c and temp_range[1]; the recipe's
  own temperature (its first stage when staged), clipped into temp_range (Q26), replaces the
  nearest of the three (the lower one on a tie). Only temperatures that pass gate.check for
  the recipe are kept; the others are recorded with the gate's reasons.
- Service recipes: member_values over min(1.5 * d_hi, horizon), default members (160).
- Sourdough styles (handoff = planner): the levain build is held for
  max(grid end, bake.PEAK_SEARCH_H) so every member's levain peak is resolved like the
  planner's search (128 resampled members). The planner sets the window (Q31).
- Per entry the caches are cleared (member_values depends on them), so the result depends on
  its inputs only: any worker count and order give the same file, byte for byte on one
  platform (the zip is written with fixed timestamps and attributes).
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import scipy  # type: ignore[import-untyped]

from fermenttrack.prediction import aroma, bake, derived, service
from fermenttrack.prediction import aroma_data as A
from fermenttrack.prediction.bake import BakeInputs, _peak_times
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.sourdough import plan_from_dict, plan_to_dict
from fermenttrack.recommender import gate, grid, library, score
from fermenttrack.recommender.library import Recipe
from fermenttrack.recommender.run import (
    AROMA_SERIES,
    SERIES,
    at_times,
    bake_plan,
    crossing_times,
    engine_key,
    milestones_for,
    planned_schedule,
    prediction_inputs,
    recipe_rows,
    series_statistics,
    summarise_times,
)

N_LOG_TIMES = 24
FIRST_H = 1.0
CEILING = 1.5  # the grid runs to the Experimental ceiling, 1.5 x d_hi, within the horizon
MAX_TIMES = N_LOG_TIMES + 3  # plus d_lo, d_med, d_hi
PLATFORM = {
    "os": sys.platform, "machine": platform.machine(), "numpy": np.__version__,
    "scipy": scipy.__version__,
}  # fmt: skip


class BuildError(RuntimeError):
    pass


# ── grid temperatures and the time axis ────────────────────────────────


def own_temperature(recipe: Recipe) -> float:
    """The recipe's place on the temperature axis: its first stage when staged (the axis
    shifts that stage only, Q27), else its median; clipped into the profile's range (Q26)."""
    if recipe.temp_c is None:
        raise BuildError(f"{recipe.key}: an active recipe needs a temperature")
    lo, hi = PROFILES[recipe.fermentation_type].temp_range
    own = recipe.temp_schedule[0][1] if recipe.temp_schedule else recipe.temp_c.median
    return min(max(own, lo), hi)


def candidate_temperatures(recipe: Recipe) -> list[float]:
    """Design § 8.1: temp_range[0], temp_c, temp_range[1], the recipe's own temperature
    replacing the nearest (the lower one on a tie)."""
    profile = PROFILES[recipe.fermentation_type]
    cands = [profile.temp_range[0], profile.temp_c, profile.temp_range[1]]
    own = own_temperature(recipe)
    cands[min(range(3), key=lambda i: abs(cands[i] - own))] = own
    return sorted(set(cands))


def grid_temperatures(recipe: Recipe) -> tuple[list[float], list[tuple[float, tuple[str, ...]]]]:
    """(kept, dropped with the gate's reasons). Each candidate is gated with the temperatures
    its run would see; an active recipe keeps at least one."""
    like = gate.from_recipe(recipe)
    kept: list[float] = []
    dropped: list[tuple[float, tuple[str, ...]]] = []
    for temp in candidate_temperatures(recipe):
        seen = [c for _, c in planned_schedule(recipe, temp)] or [temp]
        result = gate.check(like, seen)
        if result.ok:
            kept.append(temp)
        else:
            dropped.append((temp, result.reasons))
    if not kept:
        raise BuildError(f"{recipe.key}: no grid temperature passes the gate: {dropped}")
    return kept, dropped


def time_axis(recipe: Recipe) -> tuple[FloatArray, float]:
    """24 log-spaced times from 1 h to min(1.5 * d_hi, horizon), plus the documented
    d_lo, d_med and d_hi that fall inside; planner styles without a duration: to the
    horizon."""
    horizon = float(PROFILES[recipe.fermentation_type].horizon_h)
    extra: tuple[float, ...] = ()
    end = horizon
    if recipe.duration_h is not None:
        d = recipe.duration_h
        end, extra = min(CEILING * d.hi, horizon), (d.lo, d.median, d.hi)
    t = np.geomspace(FIRST_H, end, N_LOG_TIMES)
    inside = [x for x in extra if FIRST_H <= x <= end]
    return np.unique(np.concatenate([t, np.asarray(inside, dtype=float)])), end


# ── card metadata ───────────────────────────────────────────────────────


def top_compounds(
    ftype: str, t_src: FloatArray, values: dict[str, FloatArray], w: FloatArray,
    t_dst: FloatArray, stats: FloatArray,
) -> dict[str, list[str]]:  # fmt: skip
    """Aroma series -> [its top compound, that compound's evidence tier]: the compound with
    the largest mean odour activity at the time the series' E peaks (card labels, § 8.1)."""
    evidence = A.EVIDENCE.get(ftype, {})
    made = sorted(k.removeprefix("odor:") for k in values if k.startswith("odor:"))
    wn = w / np.sum(w)
    out: dict[str, list[str]] = {}
    for j, s in enumerate(AROMA_SERIES):
        if engine_key(s) not in values:
            continue
        summed = [
            k for k in made
            if A.COMPOUNDS[k].status == "active" and A.COMPOUNDS[k].threshold is not None
            and s in A.COMPOUNDS[k].series
        ]  # fmt: skip
        t_ref = t_dst[int(np.argmax(stats[0, j]))]
        oav = {
            k: float(wn @ 10.0 ** at_times(t_src, values[f"odor:{k}"], np.array([t_ref]))[:, 0])
            for k in summed
        }
        top = max(summed, key=lambda k: (oav[k], k))
        out[s] = [top, evidence.get(top, ("plausible", "", ()))[0]]
    return out


# ── one entry ───────────────────────────────────────────────────────────


def run_entry(task: tuple[str, float]) -> dict[str, Any]:
    """One grid entry: the recipe at one grid temperature (a worker's unit of work)."""
    key, temp_c = task
    recipe = library.get(key)
    if recipe is None or recipe.status != "active":
        raise BuildError(f"{key}: not an active library recipe")
    profile = PROFILES[recipe.fermentation_type]
    t_dst, end = time_axis(recipe)
    service.clear_caches()  # member_values depends on the cache state (B2): a clean slate
    started = time.perf_counter()
    milestones = milestones_for(profile)
    extra: dict[str, FloatArray] = {}
    if recipe.handoff == "planner":
        plan = plan_from_dict(bake_plan(recipe, temp_c, max(end, bake.PEAK_SEARCH_H)))
        t, values, w = bake.member_values(plan, BakeInputs(plan=plan_to_dict(plan)))
        extra[grid.LEVAIN_PEAK] = _peak_times(t, values["rise"])
        schedule: tuple[tuple[float, float], ...] = ()
        skipped: tuple[str, ...] = ()
        not_modelled: list[str] = []  # the flours carry aroma data; bake books nothing else
    else:
        inputs = prediction_inputs(recipe, temp_c)
        t, values, w = service.member_values(inputs, end)
        schedule = inputs.planned_temperature
        skipped = recipe_rows(recipe)[1]
        items = [(r.name, r.quantity, r.role) for r in inputs.recipe]
        not_modelled = aroma.ingredient_shares(items, recipe.fermentation_type)[1]
    if len(w) < 1 or np.any(np.diff(t) <= 0) or t_dst[-1] > t[-1] + 1e-9:
        raise BuildError(f"{key} at {temp_c:g} °C: the engine returned an unusable run")
    stats, present = series_statistics(t, values, w, t_dst)
    if not present[len(AROMA_SERIES) :].all() or not present[: len(AROMA_SERIES)].any():
        raise BuildError(f"{key} at {temp_c:g} °C: taste or aroma missing (engine failure?)")
    crossings = {m.key: c for m in milestones if (c := crossing_times(m, t, values)) is not None}
    crossings.update(extra)
    return {
        "recipe": key,
        "temp_c": float(temp_c),
        "t_h": t_dst,
        "stats": stats,
        "present": present,
        "milestones": {name: summarise_times(c, w) for name, c in crossings.items()},
        "milestone_end_h": float(t[-1]),
        "members": int(len(w)),
        "schedule": [list(step) for step in schedule],
        "top_compound": top_compounds(recipe.fermentation_type, t, values, w, t_dst, stats),
        "not_modelled": list(not_modelled),
        "skipped": list(skipped),
        "seconds": time.perf_counter() - started,
    }


# ── the file ────────────────────────────────────────────────────────────


def write_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """np.savez_compressed, minus its wall-clock zip timestamps and host-dependent fields."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, arr in arrays.items():
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            data = io.BytesIO()
            np.lib.format.write_array(data, np.ascontiguousarray(arr), allow_pickle=False)
            zf.writestr(info, data.getvalue(), compresslevel=9)
    path.write_bytes(buf.getvalue())


def assemble(
    recipes: list[Recipe], plans: dict[str, Any], results: list[dict[str, Any]]
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """The npz arrays (rows in build order) and the JSON index stored inside it."""
    n, n_ms = len(results), max(len(r["milestones"]) for r in results)
    t_h = np.full((n, MAX_TIMES), np.nan)
    n_t = np.zeros(n, dtype=np.int16)
    stats = np.full((n, 3, len(SERIES), MAX_TIMES), np.nan, dtype=np.float16)
    present = np.zeros((n, len(SERIES)), dtype=bool)
    milestones = np.full((n, n_ms, 4), np.nan, dtype=np.float32)
    entries = []
    for i, r in enumerate(results):
        k = len(r["t_h"])
        t_h[i, :k], n_t[i] = r["t_h"], k
        stats[i, :, :, :k] = r["stats"].astype(np.float16)
        present[i] = r["present"]
        for j, values in enumerate(r["milestones"].values()):
            milestones[i, j] = values
        entries.append({
            "recipe": r["recipe"], "temp_c": r["temp_c"], "members": r["members"],
            "schedule": r["schedule"], "milestones": list(r["milestones"]),
            "top_compound": r["top_compound"], "not_modelled": r["not_modelled"],
            "skipped": r["skipped"],
        })  # fmt: skip
    rows: dict[str, list[int]] = {}
    for i, r in enumerate(results):
        rows.setdefault(r["recipe"], []).append(i)
    index_recipes = {}
    for recipe in recipes:
        kept, dropped = plans[recipe.key]
        mine = [results[i] for i in rows[recipe.key]]
        if any(not np.array_equal(m["t_h"], mine[0]["t_h"]) for m in mine):
            raise BuildError(f"{recipe.key}: grid temperatures disagree on the time axis")
        d = recipe.duration_h
        index_recipes[recipe.key] = {
            "fermentation_type": recipe.fermentation_type,
            "engine": "bake" if recipe.handoff == "planner" else "service",
            "temps": kept,
            "dropped": [{"temp_c": t, "reasons": list(why)} for t, why in dropped],
            "duration_h": None if d is None else [d.lo, d.median, d.hi],
            "horizon_h": float(PROFILES[recipe.fermentation_type].horizon_h),
            "end_h": time_axis(recipe)[1],
            "milestone_end_h": min(m["milestone_end_h"] for m in mine),
            "rows": rows[recipe.key],
        }
    index = {
        "schema": grid.SCHEMA,
        "series": list(SERIES),
        "kinds": {s: "taste" if s in derived.TASTES else "aroma" for s in SERIES},
        "statistics": list(grid.STATISTICS),
        "tau": score.TAU,
        "recipes": index_recipes,
        "entries": entries,
    }
    blob = json.dumps(index, sort_keys=True, separators=(",", ":"), allow_nan=False)
    arrays = {
        "index": np.frombuffer(blob.encode("utf-8"), dtype=np.uint8),
        "t_h": t_h, "n_t": n_t, "stats": stats, "present": present, "milestones": milestones,
    }  # fmt: skip
    return arrays, index


def build(
    keys: list[str] | None, workers: int
) -> tuple[dict[str, np.ndarray], dict[str, Any], list[dict[str, Any]]]:
    recipes = [r for r in library.active() if keys is None or r.key in keys]
    missing = set(keys or ()) - {r.key for r in recipes}
    if missing:
        raise BuildError(f"not active library recipes: {sorted(missing)}")
    plans = {r.key: grid_temperatures(r) for r in recipes}
    tasks = [(r.key, temp) for r in recipes for temp in plans[r.key][0]]
    if workers > 1:  # separate processes: each has its own caches and solve lock
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(run_entry, tasks))
    else:
        results = [run_entry(task) for task in tasks]
    arrays, index = assemble(recipes, plans, results)
    return arrays, index, results


def manifest(
    path: Path, index: dict[str, Any], results: list[dict[str, Any]], seconds: float,
    workers: int,
) -> dict[str, Any]:  # fmt: skip
    slowest = sorted(results, key=lambda r: -r["seconds"])[:5]
    engines = {key: r["engine"] for key, r in index["recipes"].items()}
    members = {
        engine: sorted({r["members"] for r in results if engines[r["recipe"]] == engine})
        for engine in ("service", "bake")
    }
    return {
        "grid": path.name,
        "grid_sha256": grid.sha256_file(path),
        "grid_bytes": path.stat().st_size,
        "schema": grid.SCHEMA,
        "model_version": service.MODEL_VERSION,
        "bake_model_version": bake.MODEL_VERSION,
        "derived_version": derived.DERIVED_VERSION,
        "inputs": grid.input_hashes(),
        "tau": score.TAU,
        "time_grid": {
            "log_spaced": N_LOG_TIMES,
            "from_h": FIRST_H,
            "to_h": "min(1.5 * d_hi, profile horizon); planner styles without a duration: "
            "the horizon",
            "plus": ["d_lo", "d_med", "d_hi"],
        },
        "temperatures": {
            key: {"kept": r["temps"], "dropped": r["dropped"]}
            for key, r in index["recipes"].items()
        },
        "operators": [],  # single operators arrive with the Experimental mode (B7)
        "members_per_forecast": members,
        "recipes": len(index["recipes"]),
        "entries": len(results),
        # bit-identical rebuilds hold on one numeric stack; another may differ in the last bits
        "platform": PLATFORM,
        "build_date": datetime.now(UTC).isoformat(timespec="seconds"),
        "build_seconds": round(seconds, 1),
        "workers": workers,
        "slowest": [[r["recipe"], r["temp_c"], round(r["seconds"], 1)] for r in slowest],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the recommender's precomputed grid.")
    ap.add_argument("--workers", type=int, default=1, help="processes (default 1)")
    ap.add_argument("--recipes", nargs="+", help="build only these active recipes (needs --out)")
    ap.add_argument("--out", type=Path, default=grid.HERE, help="output directory")
    args = ap.parse_args(argv)
    if args.workers < 1:
        ap.error("--workers must be >= 1")
    if args.recipes and args.out.resolve() == grid.HERE.resolve():
        ap.error("a subset build must not replace the committed grid: give --out")
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    arrays, index, results = build(args.recipes, args.workers)
    npz = args.out / grid.GRID_NPZ.name
    write_npz(npz, arrays)
    seconds = time.perf_counter() - started
    body = manifest(npz, index, results, seconds, args.workers)
    (args.out / grid.MANIFEST_JSON.name).write_text(
        json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    size = body["grid_bytes"]
    print(
        f"{body['entries']} entries ({body['recipes']} recipes) in {seconds:.1f} s with "
        f"{args.workers} worker(s): {npz} {size / 1024:.1f} KiB, sha256 {body['grid_sha256']}"
    )
    print("slowest: " + ", ".join(f"{k} @ {t:g} °C {s:g} s" for k, t, s in body["slowest"]))
    for key, temps in body["temperatures"].items():
        for d in temps["dropped"]:
            print(f"dropped {key} @ {d['temp_c']:g} °C: {'; '.join(d['reasons'])}")
    if size > grid.MAX_BYTES:
        print(f"over the {grid.MAX_BYTES} byte budget: see design § 8.2", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
