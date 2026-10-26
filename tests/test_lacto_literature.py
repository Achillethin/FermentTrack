"""Recommender v2 release 2: the lacto forecast against published pH(t) curves, and the
seasoning that carries kimchi's lactic flora. Data and sources:
docs/superpowers/research/lacto-ph/curves.md (every point from a table or the text)."""

from __future__ import annotations

import numpy as np
import pytest

from fermenttrack.prediction import service
from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.recommender import library, run

# Kristek et al. 2004 Czech J Food Sci 22:125, Table 1, control, cycles I-III: 21 °C, 2.5 %
KRISTEK_DAYS = (0, 1, 2, 3, 4, 5, 6, 7, 14, 21, 28)
KRISTEK = (
    (6.20, 5.98, 5.34, 4.80, 4.46, 4.35, 4.22, 4.18, 3.91, 3.82, 3.78),
    (6.03, 5.78, 5.41, 5.08, 4.62, 4.21, 4.16, 4.08, 3.88, 3.74, 3.69),
    (6.28, 5.92, 5.54, 5.26, 4.80, 4.48, 4.30, 4.20, 3.92, 3.72, 3.66),
)
# kimchi at 20 °C: Kim et al. 2020 Foods 9:1075 (0, 48, 240 h); Hong et al. 2016 J Food Sci
# 81:C2623 (48 h)
KIMCHI_20 = ((0, 5.93), (48, 4.43), (240, 3.83), (48, 4.41))


def _band(recipe_key: str, temp_c: float, hours: list[float], salt_g: float | None = None):  # type: ignore[no-untyped-def]
    """(P05, P50, P95) of the forecast pH at each hour, the library recipe as the engine
    runs it (no readings)."""
    recipe = library.get(recipe_key)
    assert recipe is not None
    inputs = run.prediction_inputs(recipe, temp_c)
    service.clear_caches()
    t, values, w = service.member_values(inputs, max(hours) + 24.0)
    wn = w / w.sum()
    return [
        weighted_quantiles(run.at_times(t, values["ph"], np.array([max(h, 0.5)]))[:, 0], wn,
                           (0.05, 0.5, 0.95))
        for h in hours
    ]  # fmt: skip


@pytest.fixture(scope="module")
def coverage() -> dict[str, list[tuple[float, float, float, float]]]:
    """Per dataset: (hour, observed pH, P05, P95)."""
    kraut_h = [24.0 * d for d in KRISTEK_DAYS]
    kraut = _band("sauerkraut_dry_salted", 21.0, kraut_h)
    kim_h = [float(h) for h, _ in KIMCHI_20]
    kim = _band("napa_kimchi_room_temp", 20.0, kim_h)
    return {
        "kristek2004": [
            (h, obs, b[0], b[2])
            for cycle in KRISTEK for h, obs, b in zip(kraut_h, cycle, kraut, strict=True)
        ],  # fmt: skip
        "kimchi20": [(h, obs, b[0], b[2]) for (h, obs), b in zip(KIMCHI_20, kim, strict=True)],
    }


def test_the_90_percent_band_covers_85_to_95_percent_of_the_literature(coverage) -> None:  # type: ignore[no-untyped-def]
    """Release 2 exit criterion (v2 § 4). 2026-10-26, with L. sakei: 35 of 37 (94.6 %); the
    two misses are Kristek's slowest cycle at 120 and 144 h, just above P95 (4.48 vs 4.44,
    4.30 vs 4.29). Before L. sakei (2026-10-24) the misses were kimchi at 48 h."""
    pts = [p for ds in coverage.values() for p in ds]
    inside = sum(lo <= obs <= hi for _, obs, lo, hi in pts)
    print(f"\n{inside}/{len(pts)} literature points inside the 90 % band")
    assert 0.85 <= inside / len(pts) <= 0.95


def test_sauerkraut_follows_kristek_2004(coverage) -> None:  # type: ignore[no-untyped-def]
    pts = coverage["kristek2004"]
    assert sum(lo <= obs <= hi for _, obs, lo, hi in pts) >= 0.9 * len(pts)


def test_kimchi_reaches_ph_4_4_by_48_h_at_20_c(coverage) -> None:  # type: ignore[no-untyped-def]
    """Two studies measure pH 4.4 at 48 h. Until 2026-10-26 the band ended at ~4.44 (median
    5.26): L. plantarum is mesophilic. L. sakei, the cold-active homofermenter, brought the
    median to 4.75 and the band to 3.98-5.55."""
    pts = [p for p in coverage["kimchi20"] if p[0] == 48]
    assert all(lo <= obs <= hi for _, obs, lo, hi in pts)


# ── the seasoning's flora (profiles.CarriedFlora) ───────────────────────


def _spec(rows):  # type: ignore[no-untyped-def]
    profile = PROFILES["lacto_ferment"]
    init = service._initial_state(profile, tuple(rows))
    inputs = service.PredictionInputs(
        fermentation_type="lacto_ferment", now_h=0.0, expected_temperature_c=20.0,
        organisms=tuple(
            service.OrganismIn(n, "bacteria", ()) for n in sorted(profile.inoculum)
        ),
        organism_source="default", recipe=tuple(rows), measurements=(),
    )  # fmt: skip
    plans = service._plan_organisms(inputs, profile)
    sched = service._schedule(inputs, profile, None, 48.0)[0]
    spec, _ = service._spec(profile, plans, init, sched, None)
    return init, spec


CABBAGE = {"water": 92.2, "sugars_total": 3.2, "glucose": 1.67, "fructose": 1.45}
SALT = {"water": 0.2, "sodium": 38.8}


def _row(name: str, g: float, n: dict[str, float]) -> service.RecipeIn:
    return service.RecipeIn(name, g, "g", n, "base")


def test_plain_cabbage_keeps_the_vegetables_own_flora() -> None:
    init, spec = _spec([_row("Cabbage", 979.0, CABBAGE), _row("Salt", 21.0, SALT)])
    assert init.flora_fraction == 0.0
    by_name = {o.name: p.median for o, p in zip(spec.organisms, spec.inoculum, strict=True)}
    assert by_name == {
        n: PROFILES["lacto_ferment"].inoculum[n].median for n in by_name
    }  # fmt: skip
    assert spec.profile.ph0 == PROFILES["lacto_ferment"].ph0


def test_kimchi_seasoning_starts_the_flora_where_foods_2025_measured_it() -> None:
    """~8 % seasoning carries ~1e5.5 Leuconostoc and ~1e5.7 lactobacilli per g (measured
    1e5.50 and 1e5.64 an hour after seasoning; the lactobacilli are L. plantarum and L. sakei
    together) and lowers the starting pH by ~0.45."""
    rows = [
        _row("Napa cabbage", 895.0, CABBAGE), _row("Salt", 25.0, SALT),
        _row("Chilies", 30.0, {"water": 88.0}), _row("Garlic", 20.0, {"water": 59.0}),
        _row("Fresh ginger", 8.0, {"water": 79.0}), _row("Onion", 22.0, {"water": 89.0}),
    ]  # fmt: skip
    init, spec = _spec(rows)
    assert init.flora_fraction == pytest.approx(0.08)
    by_name = {o.name: p.median for o, p in zip(spec.organisms, spec.inoculum, strict=True)}
    assert by_name["Leuconostoc mesenteroides"] == pytest.approx(5.53, abs=0.05)
    lactobacilli = np.log10(
        10 ** by_name["Lactobacillus plantarum"] + 10 ** by_name["Lactobacillus sakei"]
    )
    assert lactobacilli == pytest.approx(5.67, abs=0.05)
    assert spec.profile.ph0.median == pytest.approx(
        PROFILES["lacto_ferment"].ph0.median - 0.448, abs=0.01
    )
