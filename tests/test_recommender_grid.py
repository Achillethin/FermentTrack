"""The recommender grid (design § 8, build plan B4): the committed artefact is current, within
budget, well formed and reproducible, and grid.py reads and interpolates it."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

from fermenttrack.prediction import bake, derived, service
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import gate, grid, library, run, score

_spec = importlib.util.spec_from_file_location(
    "build_recommender_grid", Path(__file__).parents[1] / "scripts" / "build_recommender_grid.py"
)
assert _spec is not None and _spec.loader is not None
builder = sys.modules["build_recommender_grid"] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)

GARUM = "pacific_sand_lance_rice_koji_fish_sauce"
KOJI = "rice_koji_steamed_rice"
NO_DURATION = ("home_starter", "levain_liquide", "levain_dur", "lievito_madre")


def _recipe(key: str) -> library.Recipe:
    recipe = library.get(key)
    assert recipe is not None
    return recipe


def _entries() -> list[grid.Entry]:
    g = grid.load()
    return [g.entry(k, t) for k in g.recipe_keys() for t in g.temps(k)]


# ── manifest, staleness, size ───────────────────────────────────────────


def test_grid_is_current() -> None:
    manifest = json.loads(grid.MANIFEST_JSON.read_text(encoding="utf-8"))
    current = {
        "inputs": grid.input_hashes(),
        "model_version": service.MODEL_VERSION,
        "bake_model_version": bake.MODEL_VERSION,
        "derived_version": derived.DERIVED_VERSION,
        "tau": score.TAU,
        "schema": grid.SCHEMA,
    }
    stale = [k for k, v in current.items() if manifest.get(k) != v]
    if set(grid.load().recipe_keys()) != {r.key for r in library.active()}:
        stale.append("active recipes")
    assert not stale, f"grid is stale ({', '.join(stale)}): run `{grid.REBUILD}`"


def test_grid_size() -> None:
    size = grid.GRID_NPZ.stat().st_size
    assert size <= grid.MAX_BYTES, f"{size} bytes: over the design § 8.2 budget"
    assert grid.load().manifest["grid_bytes"] == size


def test_the_manifest_records_what_design_8_3_asks() -> None:
    m = grid.load().manifest
    assert set(m["inputs"]) == set(grid.INPUTS)
    assert m["operators"] == [] and m["build_seconds"] > 0 and m["build_date"]
    assert m["time_grid"]["log_spaced"] == 24 and m["time_grid"]["from_h"] == 1.0
    assert m["members_per_forecast"] == {"service": [service.N_MEMBERS], "bake": [bake.N_RESAMPLE]}
    assert set(m["temperatures"]) == {r.key for r in library.active()}
    assert set(m["platform"]) == {"os", "machine", "numpy", "scipy"}


def test_input_hashes_ignore_line_endings_but_not_edits(tmp_path: Path) -> None:
    lf, crlf, edited = (tmp_path / n for n in ("lf.csv", "crlf.csv", "edited.csv"))
    lf.write_bytes(b"key,temp\nkimchi,20\n")
    crlf.write_bytes(b"key,temp\r\nkimchi,20\r\n")
    edited.write_bytes(b"key,temp\nkimchi,21\n")
    assert grid.sha256_text(lf) == grid.sha256_text(crlf) != grid.sha256_text(edited)


def test_the_file_is_checked_against_its_manifest(tmp_path: Path) -> None:
    g = grid.load()
    assert g.version() == g.manifest["grid_sha256"] == grid.version()
    npz, manifest = tmp_path / grid.GRID_NPZ.name, tmp_path / grid.MANIFEST_JSON.name
    shutil.copy(grid.GRID_NPZ, npz)
    shutil.copy(grid.MANIFEST_JSON, manifest)
    assert grid.Grid(npz, manifest).version() == g.version()
    npz.write_bytes(npz.read_bytes() + b"\0")
    with pytest.raises(grid.GridError, match="does not match its manifest"):
        grid.Grid(npz, manifest)
    with pytest.raises(grid.GridError, match="no recommender grid"):
        grid.Grid(tmp_path / "missing.npz", manifest)


def test_the_npz_is_written_byte_for_byte_the_same(tmp_path: Path) -> None:
    arrays = {"a": np.arange(5, dtype=np.float16), "b": np.ones((2, 3), dtype=bool)}
    one, two = tmp_path / "one.npz", tmp_path / "two.npz"
    builder.write_npz(one, arrays)
    builder.write_npz(two, arrays)
    assert one.read_bytes() == two.read_bytes()
    with zipfile.ZipFile(one) as zf:
        assert {i.date_time for i in zf.infolist()} == {(1980, 1, 1, 0, 0, 0)}
    with np.load(one, allow_pickle=False) as z:
        np.testing.assert_array_equal(z["a"], arrays["a"])


# ── temperatures ────────────────────────────────────────────────────────


def test_every_active_recipe_keeps_its_gated_temperatures() -> None:
    for recipe in library.active():
        kept, dropped = builder.grid_temperatures(recipe)
        stored = grid.recipe(recipe.key)
        assert len(stored.temps) >= 1, recipe.key
        assert stored.temps == tuple(kept), recipe.key
        assert [t for t, _ in stored.dropped] == [t for t, _ in dropped], recipe.key
        lo, hi = PROFILES[recipe.fermentation_type].temp_range
        assert all(lo <= t <= hi for t in stored.temps), recipe.key
        like = gate.from_recipe(recipe)
        for t in stored.temps:
            seen = [c for _, c in run.planned_schedule(recipe, t)] or [t]
            assert gate.check(like, seen).ok, (recipe.key, t)


def test_the_gate_drops_hot_garum_and_keeps_certified_koji_warm() -> None:
    garum = grid.recipe(GARUM)
    assert garum.temps == (20.0, 30.0)
    ((t, reasons),) = garum.dropped
    assert t == 60.0 and any(r.startswith("TEMP-001") for r in reasons)
    assert grid.recipe(KOJI).temps == (28.0, 30.0, 35.0)  # Koji spores (A. oryzae): exception
    koji = _recipe(KOJI)
    uncertified = dataclasses.replace(
        koji,
        ingredients=tuple(i for i in koji.ingredients if i.name != gate.CERTIFIED_KOJI_STARTER),
    )
    kept, dropped = builder.grid_temperatures(uncertified)
    assert kept == [28.0, 30.0]
    assert dropped[0][0] == 35.0 and dropped[0][1][0].startswith("KOJI-001")


@pytest.mark.parametrize(
    "key,expected",
    [
        ("wine_orleans_surface", [25.0, 27.0, 30.0]),  # 25 °C replaces the nearest, 24
        ("lactic_fresh_cheese_curd", [28.0, 30.0, 32.0]),  # 21.5 °C: nearest in range (Q26)
        ("shiro_miso_kagawa_sweet", [15.0, 27.5, 30.0]),  # a tie replaces the lower one
        ("type_ii", [22.0, 26.0, 30.0]),  # 37 °C -> 30 °C
        (GARUM, [20.0, 30.0, 60.0]),  # the first stage, 20 °C; the gate drops 60 later
    ],
)
def test_candidate_temperatures(key: str, expected: list[float]) -> None:
    assert builder.candidate_temperatures(_recipe(key)) == expected


def test_a_staged_recipe_moves_its_first_stage_only() -> None:
    garum = _recipe(GARUM)
    assert garum.temp_schedule == ((0.0, 20.0), (48.0, 18.0))
    # the later stage keeps its 18 °C, clipped into the profile's 20-60 °C (Q26)
    assert run.planned_schedule(garum, 30.0) == ((0.0, 30.0), (48.0, 20.0))
    assert grid.entry(GARUM, 30.0).schedule == ((0.0, 30.0), (48.0, 20.0))
    assert grid.entry(GARUM, 20.0).schedule == ((0.0, 20.0), (48.0, 20.0))
    assert run.prediction_inputs(garum, 30.0).expected_temperature_c is None
    assert run.planned_schedule(_recipe("napa_kimchi_room_temp"), 20.0) == ()


@pytest.mark.parametrize(
    "schedule", [((0.0, 20.0), (math.nan, 4.0)), ((0.0, 20.0), (0.0, 4.0)), ((-1.0, 20.0),)]
)
def test_bad_schedules_are_rejected(schedule: tuple[tuple[float, float], ...]) -> None:
    with pytest.raises(run.RecipeError):
        run.validate_schedule(schedule)


# ── entries ─────────────────────────────────────────────────────────────


def test_entries_are_well_formed() -> None:
    g = grid.load()
    assert g.series == (*run.AROMA_SERIES, *derived.TASTES) and len(g.series) == 20
    for key in g.recipe_keys():
        rg, recipe = g.recipe(key), _recipe(key)
        profile = PROFILES[recipe.fermentation_type]
        for temp in rg.temps:
            e = g.entry(key, temp)
            t = e.t_h
            assert np.all(np.diff(t) > 0) and t[0] == 1.0 and t[-1] == rg.end_h, key
            assert 24 <= len(t) <= 27
            if rg.duration_h is not None:
                assert rg.end_h == min(1.5 * rg.duration_h[2], profile.horizon_h)
                assert all(d in t for d in rg.duration_h if d <= rg.end_h)
            assert set(e.e) == set(e.u) == set(e.p)
            assert set(derived.TASTES) <= set(e.e)  # the four tastes, always
            assert set(e.e) & set(run.AROMA_SERIES)  # some aroma, never all absent
            assert all(v.shape == t.shape for s in (e.e, e.u, e.p) for v in s.values())
            assert set(e.top_compound) == set(e.e) - set(derived.TASTES)
            assert all(tier in {"calibrated", "reported", "plausible", "engine"}
                       for _, tier in e.top_compound.values())  # fmt: skip
            assert e.members == (bake.N_RESAMPLE if rg.engine == "bake" else service.N_MEMBERS)
            applicable = {m.key for m in profile.milestones}
            assert set(e.milestones) <= applicable | {grid.SAFETY_MILESTONE, grid.LEVAIN_PEAK}
            if profile.ph_safety_line:
                assert grid.SAFETY_MILESTONE in e.milestones, key
            assert (grid.LEVAIN_PEAK in e.milestones) == (rg.engine == "bake")
            for m in e.milestones.values():
                assert m.p10 <= m.p50 <= m.p90 and 0.0 <= m.reached <= 1.0


def test_an_absent_series_is_absent_not_zero() -> None:
    kombucha = grid.entry("green_dominant_kombucha", 25.0)
    assert "fishy" not in kombucha.e and "fishy" in grid.entry(GARUM, 20.0).e
    g = grid.load()
    for key in g.recipe_keys():  # presence follows the recipe, not the temperature
        present = {frozenset(g.entry(key, t).e) for t in g.temps(key)}
        assert len(present) == 1, key


def test_planner_styles_carry_the_levain_peak() -> None:
    for recipe in library.active():
        rg = grid.recipe(recipe.key)
        assert (rg.engine == "bake") == (recipe.handoff == "planner")
        if recipe.key in NO_DURATION:
            assert rg.duration_h is None and rg.end_h == PROFILES["sourdough"].horizon_h
            for t in rg.temps:
                peak = grid.entry(recipe.key, t).milestones[grid.LEVAIN_PEAK]
                assert 0 < peak.p10 <= peak.p50 <= peak.p90 < math.inf
                assert peak.reached > 0.9
        if rg.engine == "bake":
            assert rg.milestone_end_h >= bake.PEAK_SEARCH_H


def test_statistics_are_consistent() -> None:
    eps = 2.0**-10  # float16 storage rounds E and U by at most half a step each
    for e in _entries():
        for s in e.e:
            E, U, P = e.e[s], e.u[s], e.p[s]
            assert np.all((E >= 0) & (E <= 1) & (U >= 0) & (U <= 1) & (P >= 0) & (P <= 1))
            # U is the weighted P90 (an inverse CDF) of scores in [0, 1], E their mean: at most
            # 10 % of the weight lies above U, and no more than 1 - U above it, so
            # E <= U + 0.1 (1 - U). A skewed ensemble does put E above U (by up to 0.083).
            assert np.all(U >= E - 0.1 * (1.0 - U) - eps), (e.recipe_key, e.temp_c, s)
            # per member |σ(L/τ) - 1[L > 0]| <= 1/2 (at L = 0), so |E - P| <= 1/2; the grid's
            # largest is 0.156 (empirical: members within about τ of L = 0)
            assert np.all(np.abs(E - P) <= 0.5 + eps), (e.recipe_key, e.temp_c, s)


# ── interpolation ───────────────────────────────────────────────────────


def test_interp_temp_is_linear_between_grid_temperatures_and_clamped_outside() -> None:
    key = "napa_kimchi_room_temp"
    lo_t, mid_t, hi_t = grid.temps(key)
    lo, mid = grid.entry(key, lo_t), grid.entry(key, mid_t)
    at = grid.interp_temp(key, mid_t)
    assert at.temp_c == mid_t
    np.testing.assert_array_equal(at.e["sour"], mid.e["sour"])
    half = grid.interp_temp(key, (lo_t + mid_t) / 2)
    for s in lo.e:
        np.testing.assert_allclose(half.e[s], (lo.e[s] + mid.e[s]) / 2)
        np.testing.assert_allclose(half.u[s], (lo.u[s] + mid.u[s]) / 2)
        np.testing.assert_allclose(half.p[s], (lo.p[s] + mid.p[s]) / 2)
    np.testing.assert_array_equal(half.t_h, lo.t_h)
    for name, m in half.milestones.items():
        a, b = lo.milestones[name], mid.milestones[name]
        want = math.inf if math.inf in (a.p50, b.p50) else (a.p50 + b.p50) / 2
        assert m.p50 == pytest.approx(want), name
    cold, hot = grid.interp_temp(key, lo_t - 10), grid.interp_temp(key, hi_t + 10)
    assert (cold.temp_c, hot.temp_c) == (lo_t, hi_t)
    np.testing.assert_array_equal(cold.e["sour"], lo.e["sour"])
    np.testing.assert_array_equal(hot.e["sour"], grid.entry(key, hi_t).e["sour"])
    with pytest.raises(ValueError):
        grid.interp_temp(key, math.nan)
    with pytest.raises(KeyError):
        grid.entry(key, lo_t + 0.5)
    with pytest.raises(KeyError):
        grid.temps("not_a_recipe")


# ── determinism and staleness of the engine behind the grid ─────────────

STALE = f"grid is stale: run {grid.REBUILD}"


def _one_per_type() -> list[str]:
    """The first active recipe of each fermentation type."""
    first: dict[str, str] = {}
    for recipe in library.active():
        first.setdefault(recipe.fermentation_type, recipe.key)
    return list(first.values())


def test_the_rebuild_check_covers_every_fermentation_type() -> None:
    types = {_recipe(k).fermentation_type for k in _one_per_type()}
    assert types == {r.fermentation_type for r in library.active()} == set(PROFILES)  # all 9
    assert "sourdough" in types


@pytest.mark.parametrize("key", _one_per_type())
def test_a_rebuilt_entry_matches_the_committed_one(key: str) -> None:
    """One entry per fermentation type, solved again now (after whatever ran before in this
    process: the builder clears the caches) and stored the same way, equals the committed
    entry: bit for bit on the numeric stack that built it (full builds with 4 and 2 workers
    gave the same file), within a float16 step on another (last-bit solver differences can
    round the other way). The input hashes cover the data, not the engine's code: this is
    the check that the engine behind the grid has not changed."""
    g = grid.load()
    same_stack = g.manifest["platform"] == builder.PLATFORM
    stat_tol, time_rtol = (0.0, 0.0) if same_stack else (2.0**-10, 1e-4)
    temp = g.temps(key)[-1]
    fresh = builder.run_entry((key, temp))
    stored = g.entry(key, temp)
    np.testing.assert_array_equal(fresh["t_h"], stored.t_h, err_msg=STALE)
    as_stored = fresh["stats"].astype(np.float16).astype(np.float64)
    for j, s in enumerate(g.series):
        if not fresh["present"][j]:
            assert s not in stored.e, STALE
            continue
        assert s in stored.e, STALE
        for k, kept in enumerate((stored.e, stored.u, stored.p)):
            np.testing.assert_allclose(
                as_stored[k, j], kept[s], rtol=0.0, atol=stat_tol, err_msg=f"{STALE} ({s})"
            )
    assert list(fresh["milestones"]) == list(stored.milestones), STALE
    for name, values in fresh["milestones"].items():
        m = stored.milestones[name]
        np.testing.assert_allclose(
            np.asarray(values, dtype=np.float32),
            np.asarray([m.p10, m.p50, m.p90, m.reached], dtype=np.float32),
            rtol=time_rtol,
            err_msg=f"{STALE} ({name})",
        )
    top = {s: (c, t) for s, (c, t) in fresh["top_compound"].items()}
    assert top == dict(stored.top_compound), STALE
    assert fresh["members"] == stored.members, STALE
