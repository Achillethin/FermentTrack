"""Build the recommender's precomputed grid (design § 8.4): every active library recipe at its
grid temperatures, and every single grid operator applied to it (recommender.operators; (v) is
user-specific and live only), through the forecast engine with no readings, summarised per
series as E / U / P over time, plus milestone crossing times and card metadata. Writes
src/fermenttrack/recommender/recommender_grid_v1.npz and its manifest; recommender/grid.py
reads them and tests/test_recommender_grid.py checks they are current.

Run: python scripts/build_recommender_grid.py --workers 4
     python scripts/build_recommender_grid.py --recipes KEY [KEY ...] --out DIR   (a subset)

How a recipe runs: recommender/run.py (shared with the live forecast). Here:
- Temperatures (§ 8.1): the profile's temp_range[0], temp_c and temp_range[1]; the recipe's
  own temperature (its first stage when staged), clipped into temp_range (Q26), replaces the
  nearest of the three (the lower one on a tie). Only temperatures that pass gate.check for
  the recipe are kept; the others are recorded with the gate's reasons.
- Operators (§ 8.1, B7): (i) add and (ii) swap run at the recipe's kept temperatures, each
  gated again for the variant (dropped with the reasons where it fails); (iii) runs at its own
  temperature, sharing the recipe's row where that is a grid temperature. A variant the engine
  cannot summarise is dropped with the reason; it never stops the build.
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
from fermenttrack.prediction.bake import BakeInputs, _peak_times
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.sourdough import plan_from_dict, plan_to_dict
from fermenttrack.recommender import gate, grid, library, operators, run, score
from fermenttrack.recommender.library import Recipe
from fermenttrack.recommender.run import (
    AROMA_SERIES,
    FIRST_H,
    N_LOG_TIMES,
    SERIES,
    bake_plan,
    crossing_times,
    milestones_for,
    planned_schedule,
    prediction_inputs,
    recipe_rows,
    series_statistics,
    summarise_times,
    top_compounds,
)

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
    """The recipe's time axis (run.time_axis): its documented duration and profile horizon."""
    d = recipe.duration_h
    duration = None if d is None else (d.lo, d.median, d.hi)
    return run.time_axis(duration, float(PROFILES[recipe.fermentation_type].horizon_h))


# ── operators ───────────────────────────────────────────────────────────

Dropped = list[tuple[float, tuple[str, ...]]]


def operator_plans(recipe: Recipe, kept: list[float]) -> dict[str, dict[str, Any]]:
    """Per single grid operator: {"kind", "temps", "dropped", "run"}. (i) and (ii) at the
    recipe's kept temperatures, gated again for the variant; (iii) at its own temperature
    (operators.singles already gated it); "run": the temperatures that need their own entry
    ((iii) shares the recipe's row at one of its grid temperatures)."""
    plans: dict[str, dict[str, Any]] = {}
    for op in operators.grid_operators(recipe):
        if op.kind == "temperature":
            assert op.to_c is not None
            run_at = [] if op.to_c in kept else [op.to_c]
            plans[op.key] = {"kind": op.kind, "temps": [op.to_c], "dropped": [], "run": run_at}
            continue
        variant = operators.apply(recipe, [op])
        like = gate.from_recipe(variant)
        temps: list[float] = []
        dropped: Dropped = []
        for temp in kept:
            seen = [c for _, c in planned_schedule(variant, temp)] or [temp]
            why = (*operators.bounds_reasons(recipe, [op]), *gate.check(like, seen).reasons)
            if why:
                dropped.append((temp, tuple(why)))
            else:
                temps.append(temp)
        plans[op.key] = {"kind": op.kind, "temps": temps, "dropped": dropped, "run": temps}
    return plans


def variant_recipe(key: str, op_key: str | None) -> Recipe:
    recipe = library.get(key)
    if recipe is None or recipe.status != "active":
        raise BuildError(f"{key}: not an active library recipe")
    if op_key is None:
        return recipe
    ops = {op.key: op for op in operators.grid_operators(recipe)}
    if op_key not in ops:
        raise BuildError(f"{key}: {op_key!r} is not one of its grid operators")
    return operators.apply(recipe, [ops[op_key]])


# ── one entry ───────────────────────────────────────────────────────────


def run_entry(task: tuple[str, float] | tuple[str, float, str | None]) -> dict[str, Any]:
    """One grid entry: the recipe, or one of its single grid operators, at one temperature (a
    worker's unit of work). A variant the engine cannot summarise comes back with "error"."""
    key, temp_c = task[0], task[1]
    op_key = task[2] if len(task) > 2 else None
    recipe = variant_recipe(key, op_key)
    try:
        return _run(recipe, temp_c, op_key)
    except BuildError as exc:
        if op_key is None:
            raise
        return {"recipe": key, "temp_c": float(temp_c), "operator": op_key, "error": str(exc)}


def _run(recipe: Recipe, temp_c: float, op_key: str | None) -> dict[str, Any]:
    key = recipe.key
    where = f"{key}{f' + {op_key}' if op_key else ''} at {temp_c:g} °C"
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
        raise BuildError(f"{where}: the engine returned an unusable run")
    stats, present = series_statistics(t, values, w, t_dst)
    if not present[len(AROMA_SERIES) :].all() or not present[: len(AROMA_SERIES)].any():
        raise BuildError(f"{where}: taste or aroma missing (engine failure?)")
    crossings = {m.key: c for m in milestones if (c := crossing_times(m, t, values)) is not None}
    crossings.update(extra)
    return {
        "recipe": key,
        "operator": op_key,
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
    """The npz arrays (rows in build order) and the JSON index stored inside it. A variant
    result with an "error" gets no row: its temperature is recorded as dropped."""
    good = [r for r in results if "error" not in r]
    n, n_ms = len(good), max(len(r["milestones"]) for r in good)
    t_h = np.full((n, MAX_TIMES), np.nan)
    n_t = np.zeros(n, dtype=np.int16)
    stats = np.full((n, 3, len(SERIES), MAX_TIMES), np.nan, dtype=np.float16)
    present = np.zeros((n, len(SERIES)), dtype=bool)
    milestones = np.full((n, n_ms, 4), np.nan, dtype=np.float32)
    entries = []
    row: dict[tuple[str, str | None, float], int] = {}
    for i, r in enumerate(good):
        k = len(r["t_h"])
        t_h[i, :k], n_t[i] = r["t_h"], k
        stats[i, :, :, :k] = r["stats"].astype(np.float16)
        present[i] = r["present"]
        for j, values in enumerate(r["milestones"].values()):
            milestones[i, j] = values
        entries.append({
            "recipe": r["recipe"], "operator": r["operator"], "temp_c": r["temp_c"],
            "members": r["members"], "schedule": r["schedule"],
            "milestones": list(r["milestones"]), "top_compound": r["top_compound"],
            "not_modelled": r["not_modelled"], "skipped": r["skipped"],
        })  # fmt: skip
        row[r["recipe"], r["operator"], r["temp_c"]] = i
    failed = {
        (r["recipe"], r["operator"], r["temp_c"]): r["error"] for r in results if "error" in r
    }
    index_recipes = {}
    for recipe in recipes:
        kept, dropped, op_plans = plans[recipe.key]
        mine = [r for r in good if r["recipe"] == recipe.key]
        if any(not np.array_equal(m["t_h"], mine[0]["t_h"]) for m in mine):
            raise BuildError(f"{recipe.key}: grid entries disagree on the time axis")
        ops = {}
        for op_key, plan in op_plans.items():
            temps, rows, lost = [], [], list(plan["dropped"])
            for t in plan["temps"]:
                at = (recipe.key, op_key if t in plan["run"] else None, t)
                if at in row:
                    temps.append(t)
                    rows.append(row[at])
                else:
                    lost.append((t, (failed[at],)))
            ops[op_key] = {
                "kind": plan["kind"], "temps": temps, "rows": rows,
                "dropped": [{"temp_c": t, "reasons": list(why)} for t, why in sorted(lost)],
            }  # fmt: skip
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
            "rows": [row[recipe.key, None, t] for t in kept],
            "operators": ops,
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


Task = tuple[str, float, str | None]


def build(
    keys: list[str] | None, workers: int
) -> tuple[dict[str, np.ndarray], dict[str, Any], list[dict[str, Any]]]:
    recipes = [r for r in library.active() if keys is None or r.key in keys]
    missing = set(keys or ()) - {r.key for r in recipes}
    if missing:
        raise BuildError(f"not active library recipes: {sorted(missing)}")
    plans = {}
    for r in recipes:
        kept, dropped = grid_temperatures(r)
        plans[r.key] = (kept, dropped, operator_plans(r, kept))
    tasks: list[Task] = []
    for r in recipes:
        kept, _, op_plans = plans[r.key]
        tasks += [(r.key, temp, None) for temp in kept]
        tasks += [(r.key, temp, op) for op, p in op_plans.items() for temp in p["run"]]
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
    good = [r for r in results if "error" not in r]
    slowest = sorted(good, key=lambda r: -r["seconds"])[:5]
    engines = {key: r["engine"] for key, r in index["recipes"].items()}
    members = {
        engine: sorted({r["members"] for r in good if engines[r["recipe"]] == engine})
        for engine in ("service", "bake")
    }
    ops = {
        key: {
            op: {k: o[k] for k in ("kind", "temps", "dropped")} for op, o in r["operators"].items()
        }
        for key, r in index["recipes"].items()
    }
    kinds = [o["kind"] for r in ops.values() for o in r.values()]
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
        # single grid operators per recipe (recommender.operators.grid_operators); (v) is
        # live only. A temperature operator at a grid temperature shares the recipe's entry.
        "operators": ops,
        "operator_counts": {k: kinds.count(k) for k in sorted(set(kinds))},
        "members_per_forecast": members,
        "recipes": len(index["recipes"]),
        "entries": len(good),
        "operator_entries": sum(r["operator"] is not None for r in good),
        # bit-identical rebuilds hold on one numeric stack; another may differ in the last bits
        "platform": PLATFORM,
        "build_date": datetime.now(UTC).isoformat(timespec="seconds"),
        "build_seconds": round(seconds, 1),
        "workers": workers,
        "slowest": [
            [r["recipe"], r["operator"], r["temp_c"], round(r["seconds"], 1)] for r in slowest
        ],
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
        f"{body['entries']} entries ({body['recipes']} recipes, {body['operator_entries']} "
        f"operator entries, operators {body['operator_counts']}) in {seconds:.1f} s with "
        f"{args.workers} worker(s): {npz} {size / 1024:.1f} KiB, sha256 {body['grid_sha256']}"
    )
    print("slowest: " + ", ".join(
        f"{k}{f' + {op}' if op else ''} @ {t:g} °C {s:g} s" for k, op, t, s in body["slowest"]
    ))  # fmt: skip
    for key, temps in body["temperatures"].items():
        for d in temps["dropped"]:
            print(f"dropped {key} @ {d['temp_c']:g} °C: {'; '.join(d['reasons'])}")
    for key, ops in body["operators"].items():
        for op, o in ops.items():
            for d in o["dropped"]:
                print(f"dropped {key} + {op} @ {d['temp_c']:g} °C: {'; '.join(d['reasons'])}")
    if size > grid.MAX_BYTES:
        print(f"over the {grid.MAX_BYTES} byte budget: see design § 8.2", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
