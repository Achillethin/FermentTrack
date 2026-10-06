"""Miso and garum aroma against curation § 7 (tests 38-51). Both are exploratory types:
cells the model cannot meet inside its priors are strict xfails with the reason."""

from __future__ import annotations

from functools import cache

import numpy as np
import pytest

from fermenttrack.prediction import aroma, engine
from fermenttrack.prediction.profiles import PROFILES
from fermenttrack.prediction.service import RecipeIn
from tests.test_aroma_lacto import At, _per_100g, medians
from tests.test_engine_diagnostics import _setup

D = 24.0
MO = 30.4 * D  # a month, h
MISO = ["Aspergillus oryzae", "Tetragenococcus halophilus", "Zygosaccharomyces rouxii"]


def _item(name: str, g: float, role: str = "base") -> RecipeIn:
    return RecipeIn(name, g, "g", _per_100g(name), role)


def _miso(grain: str) -> tuple[RecipeIn, ...]:
    # koji ratio 10 (equal soybean and koji grain), 11 % salt
    return (_item("Soybeans", 450.0), _item(grain, 440.0), _item("Salt", 110.0, "additive"))


@cache
def _run(grain: str, temp: float, days: float, organisms: tuple[str, ...] = tuple(MISO)) -> At:
    return medians("miso", temp, days * D, _miso(grain), list(organisms))


def _series(c: At, key: str, days: int) -> list[float]:
    return [c(key, d * D) for d in range(days + 1)]


def _peak(v: list[float]) -> int:
    return max(range(len(v)), key=lambda i: v[i])


# ── HEMF (tests 38-41) ──────────────────────────────────────────────────

_NO_LAB = (
    "§ 5.11 pH gate (04:M10): without LAB the engine's mash stays at pH 6.2 (koji acids are "
    "not modelled), so Z. rouxii never converts the precursor; the same clauses run on the "
    "default consortium below"
)
_GATE_LATE = (
    "§ 5.11 pH gate: the engine's mash reaches pH 5.6 only after ~40 d at 30 °C (real misos "
    "start at 5.7-5.8: 04:M2, M8, M10), so HEMF peaks at ~63 d, after 04:M9's 30-60 d"
)


@pytest.mark.xfail(strict=True, reason=_NO_LAB)
def test_38_hemf_base_case_without_lab() -> None:
    v = _series(_run("White rice", 30.0, 75, (MISO[0], MISO[2])), "hemf", 75)
    assert 5_700.0 <= max(v) <= 51_000.0


@pytest.fixture(scope="module")
def hemf30() -> list[float]:
    return _series(_run("White rice", 30.0, 75), "hemf", 75)


@pytest.mark.xfail(strict=True, reason=_GATE_LATE)
def test_38_hemf_peak_in_30_to_60_d(hemf30: list[float]) -> None:
    assert 30 <= _peak(hemf30) <= 60


def test_38_hemf_peak_magnitude(hemf30: list[float]) -> None:
    assert 5_700.0 <= max(hemf30) <= 51_000.0


def test_38_hemf_75_d_over_peak(hemf30: list[float]) -> None:
    assert 0.5 <= hemf30[75] / max(hemf30) <= 1.0


def test_39_hemf_needs_yeast(hemf30: list[float]) -> None:
    v = _series(_run("White rice", 30.0, 75, tuple(MISO[:2])), "hemf", 75)
    assert max(v) < 0.01 * max(hemf30)


@pytest.mark.xfail(strict=True, reason=_GATE_LATE)
def test_40_hemf_35_c_peaks_by_30_d() -> None:
    assert _peak(_series(_run("White rice", 35.0, 75), "hemf", 75)) <= 30


def test_40_hemf_35_c_falls() -> None:
    v = _series(_run("White rice", 35.0, 75), "hemf", 75)
    assert v[75] / max(v) < 0.4


def test_40_hemf_25_c_peaks_late() -> None:
    assert _peak(_series(_run("White rice", 25.0, 75), "hemf", 75)) >= 60


@pytest.mark.parametrize("temp,lo,hi", [(30.0, 0.15, 0.45), (20.0, 0.55, 0.95)])
def test_41_hemf_chemical_loss(temp: float, lo: float, hi: float) -> None:
    # 14 610 µg/kg at t0, yeast removed (04:M9 Table 3)
    n = 16
    p, t = _setup("miso", n, list(MISO[:2]), temp)
    tr = engine.simulate(p, t, keep_states=True)
    seg = aroma.Segment(p, tr, {"Soybeans": 0.45, "White rice": 0.44})
    ctx = aroma.build_context(seg, PROFILES["miso"], PROFILES["miso"].co2_escapes)
    c, _ = aroma.concentrations(ctx, aroma.draws(n, 3), {"hemf": np.full(n, 14_610.0)})
    i = int(np.searchsorted(t, 40 * D))
    factor = float(np.median(c["hemf"][:, i])) / 14_610.0
    assert lo <= factor <= hi


# ── furanones and maltol (tests 42-44) ──────────────────────────────────


def test_42_furaneol_increases_with_temperature() -> None:
    v = [_run("Pearl barley", t, 28)("furaneol", 28 * D) for t in (15.0, 20.0, 30.0, 37.0)]
    assert v[0] < v[1] < v[2] < v[3]


def test_42_furaneol_at_30_c() -> None:
    assert 490.0 <= _run("Pearl barley", 30.0, 28)("furaneol", 28 * D) <= 4_400.0


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.11 kmax_norfuraneol_uptake (0.1-0.5/d): the profile's Z. rouxii starts at ~10^2.5/g "
    "and takes ~3 d to grow, while 04:M1 added yeast at t0 to a pre-aged mash; d8/d0 = 0.52 "
    "at the median, 0.39 even at 0.45/d"))
def test_43_norfuraneol_taken_up() -> None:
    c = _run("Pearl barley", 30.0, 8)
    assert 0.1 <= c("norfuraneol", 8 * D) / c("norfuraneol", 0.0) <= 0.35


def test_44_maltol_falls() -> None:
    c = _run("White rice", 25.0, 120)
    assert c("maltol", 120 * D) / c("maltol", 0.0) < 0.3


# ── Ehrlich alcohols in red rice miso (test 45) ─────────────────────────

_NO_ALCOHOL_LOSS = (
    "§ 5.1: a closed miso jar has no loss for fusel alcohols (no AAB, CO2 stripping < 1 %), "
    "so they rise to 180 d instead of falling 20-60 % after a 60-90 d peak (04:M2, M8); and "
    "the first-order aminotransferase route (kmax_at_nonyeast 0.005-0.5/d) on 30-50 g/kg free "
    "amino acids makes ~3.9 g/kg 3-methylbutanol, x150 04:M1's mean"
)


@pytest.fixture(scope="module")
def red() -> dict[float, At]:
    return {t: _run("White rice", t, 180) for t in (25.0, 30.0)}


def _peak_day(c: At, key: str) -> tuple[int, float]:
    v = _series(c, key, 180)
    i = _peak(v)
    return i, v[i]


@pytest.mark.xfail(strict=True, reason=_NO_ALCOHOL_LOSS)
def test_45_methylbutanol_peak_window(red: dict[float, At]) -> None:
    assert 45 <= _peak_day(red[30.0], "methylbutanol_3")[0] <= 120


@pytest.mark.xfail(strict=True, reason=_NO_ALCOHOL_LOSS)
def test_45_methylbutanol_falls_after_peak(red: dict[float, At]) -> None:
    _, pk = _peak_day(red[30.0], "methylbutanol_3")
    assert 0.4 <= red[30.0]("methylbutanol_3", 180 * D) / pk <= 0.8


def test_45_methylbutanol_cooler_peak_higher(red: dict[float, At]) -> None:
    assert _peak_day(red[25.0], "methylbutanol_3")[1] >= _peak_day(red[30.0], "methylbutanol_3")[1]


def test_45_methylbutanol_peak_magnitude(red: dict[float, At]) -> None:
    assert _peak_day(red[30.0], "methylbutanol_3")[1] >= 5_700.0


@pytest.mark.xfail(strict=True, reason=_NO_ALCOHOL_LOSS)
def test_45_phenylethanol(red: dict[float, At]) -> None:
    i, pk = _peak_day(red[30.0], "phenylethanol_2")
    assert 45 <= i <= 120 and 0.25 <= red[30.0]("phenylethanol_2", 180 * D) / pk <= 0.6


@pytest.mark.xfail(strict=True, reason=_NO_ALCOHOL_LOSS)
def test_45_methionol(red: dict[float, At]) -> None:
    i, pk = _peak_day(red[30.0], "methionol")
    assert 45 <= i <= 150 and 0.4 <= red[30.0]("methionol", 180 * D) / pk <= 0.9


@pytest.mark.xfail(strict=True, reason=_NO_ALCOHOL_LOSS)
@pytest.mark.parametrize("key", ["methylbutanol_2", "methylpropanol_2"])
def test_45_branched_alcohols_rise_then_fall(red: dict[float, At], key: str) -> None:
    c = red[30.0]
    assert c(key, 90 * D) > c(key, 30 * D) and c(key, 120 * D) < c(key, 90 * D)


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.2: the acetate esters follow the yeast's sugar flux, fastest in the first weeks "
    "(30 d / 120 d = 0.29); 04:M2's 2-phenylethyl acetate appears only after 60 d"))
def test_45_phenylethyl_acetate_late(red: dict[float, At]) -> None:
    c = red[30.0]
    assert c("phenylethyl_acetate", 30 * D) < 0.2 * c("phenylethyl_acetate", 120 * D)


# ── long barley miso (test 46) and end points (test 47) ─────────────────

_ALDEHYDES_FALL = (
    "§ 5.1 / § 5.11: aldehyde reduction by the yeast and LAB (kmax_ald_reduction 0.5-10/d) "
    "outpaces Strecker formation once the early aminotransferase burst passes, so the "
    "aldehydes peak at ~30 d and fall (04:M3: 365 d > 90 d)"
)
_M3 = (
    *(pytest.param(k, marks=pytest.mark.xfail(strict=True, reason=_ALDEHYDES_FALL)) for k in (
        "methylbutanal_3", "methylbutanal_2", "methylpropanal_2", "phenylacetaldehyde",
    )),
    "ethyl_2methylpropanoate", "ethyl_2methylbutanoate", "ethyl_acetate", "isoamyl_acetate",
    pytest.param("acetaldehyde", marks=pytest.mark.xfail(strict=True, reason=(
        "§ 5.3: yeast acetaldehyde follows its sugar flux (early) and the yeast takes it back "
        "up, so it falls after 30 d"))),
    pytest.param("hexanal", marks=pytest.mark.xfail(strict=True, reason=(
        "§ 6.2: no soybean hexanal pool is curated (P0 pending), so hexanal is 0"))),
)  # fmt: skip


@pytest.mark.parametrize("key", _M3)
def test_46_long_barley_miso_rises(key: str) -> None:
    c = _run("Pearl barley", 28.0, 365)
    assert c(key, 365 * D) > c(key, 90 * D)


@pytest.mark.xfail(strict=True, reason=(
    "§ 4.8 / § 10.2: 1-octen-3-ol keeps rising for a year in 04:M3, but the mould does not "
    "grow in the mash and no non-growth source exists (the spec expects this to fail)"))
def test_46_octenol_rises() -> None:
    c = _run("Pearl barley", 28.0, 365)
    # beyond the <= 2 % that escaping CO2 concentrates every compound (one mass basis, B5)
    assert c("octen3ol", 365 * D) > 1.05 * c("octen3ol", 90 * D)


def _x47(reason: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, reason=reason)


@pytest.mark.parametrize("key,lo,hi", [
    pytest.param("methylbutanoic_3", 2_000.0, 18_000.0, marks=_x47(
        "§ 5.1 aminotransferase acid share and § 5.11 aldehyde oxidation on 30-50 g/kg free "
        "amino acids give ~460 mg/kg, x25 the window")),
    pytest.param("acetoin", 630.0, 5_700.0, marks=_x47(
        "§ 5.4: the LAB sugar route (b_acetoin_lab 2 mg/g) is small and the yeast and LAB "
        "reduce acetoin to 2,3-butanediol (0.2/d), leaving ~5 µg/kg")),
    pytest.param("butanediol_23", 81_000.0, 730_000.0, marks=_x47(
        "§ 5.4: the whole C4 pool of the LAB sugar route is ~18 mg/kg; 04:M1's 240 mg/kg "
        "needs a yeast C4 route, which § 5 does not give")),
    pytest.param("ethyl_lactate", 1_300.0, 11_700.0, marks=_x47(
        "§ 5.5: esterification of the engine's lactic acid with 14 g/kg ethanol over 180 d "
        "gives ~0.3 mg/kg, x4 below the window")),
])  # fmt: skip
def test_47_barley_miso_end_points(key: str, lo: float, hi: float) -> None:
    assert lo <= _run("Pearl barley", 25.0, 180)(key, 180 * D) <= hi


# ── garum (tests 48-51): fish + salt, no koji ───────────────────────────


@cache
def _garum(temp: float, months: float) -> At:
    recipe = (_item("Anchovies", 750.0), _item("Salt", 250.0, "additive"))
    return medians("garum", temp, months * MO, recipe, ["Tetragenococcus halophilus"])


def _g(key: str, mo: float) -> float:
    return _garum(22.0, 48)(key, mo * MO)


_LIPOLYSIS = pytest.mark.xfail(strict=True, reason=(
    "§ 5: no fish-lipolysis template, so the garum fatty acids have no route (P0 pending)"))


@pytest.mark.parametrize("key,a,b,lo,hi", [
    ("methylbutanoic_3", 12, 48, 5.0, np.inf), ("methylpropanoic_2", 12, 48, 3.0, np.inf),
    pytest.param("butanoic", 12, 48, 1.0, 2.5, marks=_LIPOLYSIS),
    pytest.param("hexanoic", 24, 48, 1.5, np.inf, marks=_LIPOLYSIS),
    pytest.param("octanoic", 12, 48, 0.67, 1.5, marks=_LIPOLYSIS),
    pytest.param("decanoic", 12, 48, 0.5, 1.1, marks=_LIPOLYSIS),
    pytest.param("phenylethanol_2", 12, 48, 3.0, np.inf, marks=_x47(
        "§ 5.1: the engine's T. halophilus does not grow in a 25 % salt garum (it declines "
        "from day 0), so nothing reduces phenylacetaldehyde to 2-phenylethanol")),
    pytest.param("ethyl_octanoate", 12, 48, 1.0, 3.0, marks=_x47(
        "§ 5.2: ethyl octanoate is a yeast b-term and a traditional garum has no yeast")),
])  # fmt: skip
def test_48_49_garum_ratios(key: str, a: float, b: float, lo: float, hi: float) -> None:
    start = _g(key, a)
    assert start > 0.0 and lo <= _g(key, b) / start <= hi


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.11: Strecker formation on the growing free amino-acid pool outpaces its slow "
    "oxidation (0.0005-0.01/d), so phenylacetaldehyde rises for 4 years (04:G1: nd at 48 mo)"))
def test_50_phenylacetaldehyde_rises_then_falls() -> None:
    v = [_g("phenylacetaldehyde", m) for m in range(49)]
    i = _peak(v)
    assert i < 24 and v[48] < 0.2 * v[i]


def test_50_nonanal_rises_early() -> None:
    assert _g("nonanal", 7) > _g("nonanal", 3)


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.8: the fish-lipid source is zero-order with a slow loss, so nonanal approaches a "
    "plateau instead of falling x5 from 12 to 48 months (04:G1)"))
def test_50_nonanal_falls_late() -> None:
    assert _g("nonanal", 48) / _g("nonanal", 12) < 0.2


@pytest.mark.parametrize("key", ["methylbutanal_3", "methylbutanal_2", "pentylfuran_2",
                                 "octen3ol"])  # fmt: skip
def test_51_first_seven_months_rise(key: str) -> None:
    c = _garum(20.0, 7)
    assert c(key, 7 * MO) > c(key, 3 * MO)


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.8 / § 6.2: hexanal falls 3 -> 7 months in 04:G2 from a fresh-fish pool that is not "
    "curated; the zero-order fish-lipid source only rises from 0"))
def test_51_hexanal_falls() -> None:
    c = _garum(20.0, 7)
    assert c("hexanal", 7 * MO) < c("hexanal", 3 * MO)
