"""Lacto-ferment aroma against published time courses (curation spec § 7, tests 19-25)."""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from fermenttrack.prediction import service
from fermenttrack.prediction.inference import weighted_quantiles
from fermenttrack.prediction.service import RecipeIn
from tests.test_prediction_sensory import _inputs

D = 24.0
_CSV = Path(__file__).resolve().parents[1] / "src/fermenttrack/fdc_nutrients_v1.csv"
At = Callable[[str, float], float]


def _per_100g(name: str) -> dict[str, float]:
    with _CSV.open(encoding="utf-8") as f:
        rows = csv.DictReader(f)
        mine = (r for r in rows if r["ingredient_name"] == name)
        return {r["nutrient"]: float(r["amount_per_100g"]) for r in mine}


def _recipe(veg: str, veg_g: float, salt_g: float) -> tuple[RecipeIn, ...]:
    # napa cabbage and cucumber borrow the Cabbage row's nutrients (no catalogue row yet)
    return (RecipeIn(veg, veg_g, "g", _per_100g("Cabbage"), "base"),
            RecipeIn("Salt", salt_g, "g", _per_100g("Salt"), "additive"))  # fmt: skip


def _medians(
    veg: str, salt_g: float, temp: float, days: float, organisms: list[str] | None = None
) -> At:
    """Weighted median of each compound (µg/kg) at a day, prior-only forecast (§ 7)."""
    service.clear_caches()
    inputs = _inputs("lacto_ferment", temp, _recipe(veg, 1000.0 - salt_g, salt_g), organisms)
    t, values, w = service.member_values(inputs, days * D)

    def at(key: str, day: float) -> float:
        rows = values.get(f"conc:{key}")
        if rows is None:
            return 0.0
        col = np.array([np.interp(day * D, t, row) for row in rows])
        return float(weighted_quantiles(col, w, (0.5,))[0])

    return at


def _peak_day(at: At, key: str, days: range) -> int:
    return max(days, key=lambda d: at(key, d))


@pytest.fixture(scope="module")
def kimchi() -> At:
    # napa cabbage brined to 2.5 % salt, then cabbage alone at 15 °C for 15 d (03:S10)
    return _medians("Napa cabbage (salted)", 25.0, 15.0, 15.0)


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.6 gsl_release 0.3-1.5/d at 20 °C is first-order from t0: the ITC peaks at d2-3 even "
    "at the range ends; 03:S10's d7 peak needs ~0.1/d at 15 °C (or a delayed release)"))
def test_19_butenyl_itc(kimchi: At) -> None:
    peak = _peak_day(kimchi, "butenyl_itc", range(16))
    assert 5 <= peak <= 9
    assert kimchi("butenyl_itc", 15) / kimchi("butenyl_itc", peak) < 0.5


def test_20_sulfide_burst_and_dmds_rise(kimchi: At) -> None:
    c = kimchi
    assert c("dmds", 3) / c("dmds", 0) < 0.1 and c("dmds", 15) / c("dmds", 3) > 1.5
    assert c("dmts", 3) / c("dmts", 0) < 0.05


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.7: the DMTS fermentation pool follows cumulative sugar use, and the engine's 15 °C "
    "kimchi still ferments to d15 (pH 6.2 -> 4.3, 11 of 30 g/kg sugar), so d5-d15 spans x3"))
def test_20_dmts_late_plateau(kimchi: At) -> None:
    late = [kimchi("dmts", d) for d in range(5, 16)]
    assert max(late) / min(late) <= 2.0


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.2/5.5: no in-ferment ester loss faster than hydrolysis (t½ ~250 d) or CO2 stripping "
    "(~2 %); with the engine's slow 15 °C kimchi, LAB esters rise to d15 instead of peaking d5-9"))
def test_21_esters(kimchi: At) -> None:
    c = kimchi
    pb = _peak_day(c, "ethyl_butanoate", range(16))
    assert 5 <= pb <= 9 and c("ethyl_butanoate", 3) < 0.2 * c("ethyl_butanoate", pb)
    assert c("ethyl_butanoate", 15) / c("ethyl_butanoate", pb) < 0.4
    pm = _peak_day(c, "ethyl_2methylbutanoate", range(16))
    assert 7 <= pm <= 12
    assert c("ethyl_2methylbutanoate", 15) / c("ethyl_2methylbutanoate", pm) < 0.5


def test_22_green_volatiles(kimchi: At) -> None:
    c = kimchi
    h0 = c("hexanal", 0)
    assert all(h0 / 3 <= c("hexanal", d) <= 3 * h0 for d in range(3, 16))
    assert all(c("z3_hexenal", d) <= c("z3_hexenal", 0) + 1e-9 for d in range(16))
    p = _peak_day(c, "z3_hexenol", range(16))
    assert 3 <= p <= 7 and c("z3_hexenol", p) >= 3 * c("z3_hexenol", 0)
    assert c("z3_hexenol", 15) / c("z3_hexenol", p) < 0.4


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.1: the lacto engine has no free amino-acid pool for vegetables, so methional cannot "
    "rise, and LAB aldehyde reduction (>= 0.5/d) removes phenylacetaldehyde with nothing "
    "forming it"))
def test_23_amino_acid_aldehydes(kimchi: At) -> None:
    c = kimchi
    assert c("methional", 15) >= 2 * c("methional", 0)
    p0 = c("phenylacetaldehyde", 0)
    assert all(p0 / 2 <= c("phenylacetaldehyde", d) <= 2 * p0 for d in range(16))


def test_24_cucumber() -> None:
    # 2 % NaCl, L. plantarum only, 20 °C, 21 d (03:S13). The source brine's 53 mM acetic
    # acid cannot be logged in a recipe yet; the targets are aldehyde losses.
    c = _medians("Cucumber", 20.0, 20.0, 21.0, ["Lactobacillus plantarum"])
    assert c("e2_nonenal", 5) / c("e2_nonenal", 0) < 0.01
    assert 4.0 <= c("hexanal", 21) <= 114.0


@pytest.fixture(scope="module")
def kraut() -> At:
    # white cabbage, 2 % dry salt, Leuc. mesenteroides, 18 °C, 9 months (03:S1)
    return _medians("Cabbage", 20.0, 18.0, 270.0, ["Leuconostoc mesenteroides"])


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.6 conflict: itc_loss 0.08-0.4/d (derived from kimchi d7-d15) empties AITC in weeks, "
    "while 9-month sauerkraut keeps 55-85 µg/kg (03:S1); AITC is stable at pH 5-7 (05:Tsao00)"))
def test_25_sauerkraut_aitc(kraut: At) -> None:
    assert 18.0 <= kraut("allyl_itc", 270) <= 256.0


def test_25_sauerkraut_sulfides(kraut: At) -> None:
    c = kraut
    assert 10.0 <= c("dmds", 270) <= 234.0
    assert 7.0 <= c("dmts", 270) <= 92.0
