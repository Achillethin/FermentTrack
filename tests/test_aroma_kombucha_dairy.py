"""Kombucha, kefir and cheese aroma against curation § 7 (tests 1-10, 26-37)."""

from __future__ import annotations

from functools import cache

import numpy as np
import pytest

from fermenttrack.prediction import aroma, engine
from fermenttrack.prediction.priors import FloatArray
from fermenttrack.prediction.profiles import PROFILES
from tests.test_aroma_lacto import At, medians
from tests.test_engine_diagnostics import _setup

D = 24.0


def _xf(reason: str) -> pytest.MarkDecorator:
    return pytest.mark.xfail(strict=True, reason=reason)


_STILL_FERMENTING = (
    "the engine's kombucha yeast still ferments from D7 to D14 (ethanol 1.25 -> 1.74 g/kg at "
    "30 °C), so its b-term products keep rising instead of levelling off (02:K1, K2)"
)
_EARLY_ESTERS = (
    "§ 5.2: yeast esters follow the sugar flux, fastest in the first days, and the open "
    "surface (k_surf x K_aw) strips them after; 02:K2's esters appear late (D7-D14)"
)
_BOUND_POOL = (
    "§ 5.9 / § 6.1: the tea's bound pool (~1 mg/kg batch, 05:Zhou26tea) released at >= 0.02/d "
    "and split 100 % between linalool, geraniol and methyl salicylate releases far more than "
    "their free pools (2-10 µg/kg); most of the bound aglycones are linalool oxides and "
    "benzyl/phenylethyl glycosides, which the split does not have"
)
_SLOW_KEFIR_YEAST = (
    "§ 5.2: the engine's kefir K. marxianus ferments slowly and steadily at 22 °C (ethanol "
    "0.07 g/kg at 24 h, 0.19 g/kg at 48 h), so yeast esters grow ~linearly to 48 h"
)


@cache
def _kombucha(temp: float) -> At:
    # sweet tea 70 g/kg sucrose, 10 % starter (profile), tea 5 g/kg (default), profile organisms
    return medians("kombucha", temp, 14 * D)


def _k(temp: float, key: str, day: float) -> float:
    return _kombucha(temp)(key, day * D)


# ── kombucha (tests 1-10) ───────────────────────────────────────────────


def test_01_methylbutanol_rises() -> None:
    assert _k(28.0, "methylbutanol_3", 7) > 2.0 * _k(28.0, "methylbutanol_3", 0)


def test_01_methylbutanol_d12() -> None:
    assert 233.0 <= _k(28.0, "methylbutanol_3", 12) <= 6_000.0


def test_02_methylpropanol_d12() -> None:
    assert 233.0 <= _k(28.0, "methylpropanol_2", 12) <= 6_000.0


def test_03_phenylethanol_rises() -> None:
    assert _k(30.0, "phenylethanol_2", 7) > 2.0 * _k(30.0, "phenylethanol_2", 0)


@_xf(_STILL_FERMENTING)
def test_03_phenylethanol_plateau() -> None:
    assert 0.67 <= _k(30.0, "phenylethanol_2", 14) / _k(30.0, "phenylethanol_2", 7) <= 1.5


@pytest.mark.parametrize("key", ["methylbutanoic_3", "methylpropanoic_2"])
def test_04_fusel_acids_rise(key: str) -> None:
    assert _k(30.0, key, 14) > _k(30.0, key, 2)


@_xf(
    "§ 5.2 / § 5.5: yeast ethyl acetate follows the early sugar flux, and esterification at "
    "kombucha's ~1.5 g/kg ethanol adds little; 02:K2's late acceleration (x8.4, half after "
    "D7) is not reproduced"
)
def test_05_ethyl_acetate_accelerates() -> None:
    e = [_k(28.0, "ethyl_acetate", d) for d in (0, 7, 14)]
    assert e[2] - e[1] > e[1] - e[0]


def test_05_ethyl_acetate_d12() -> None:
    assert 17.0 <= _k(28.0, "ethyl_acetate", 12) <= 21_000.0


@_xf(_EARLY_ESTERS)
@pytest.mark.parametrize("key", ["isoamyl_acetate", "ethyl_hexanoate"])
def test_06_late_esters(key: str) -> None:
    assert _k(30.0, key, 4) < 0.25 * _k(30.0, key, 14)


@_xf(_EARLY_ESTERS)
def test_06_phenylethyl_acetate() -> None:
    assert _k(30.0, "phenylethyl_acetate", 14) > 3.0 * _k(30.0, "phenylethyl_acetate", 2)


def test_06_ethyl_decanoate() -> None:
    assert _k(30.0, "ethyl_decanoate", 7) > _k(30.0, "ethyl_decanoate", 0)
    assert 0.67 <= _k(30.0, "ethyl_decanoate", 14) / _k(30.0, "ethyl_decanoate", 7) <= 1.5


@pytest.mark.parametrize("key", ["hexanoic", "octanoic", "decanoic"])
def test_07_mcfa_rise(key: str) -> None:
    assert _k(30.0, key, 7) > _k(30.0, key, 0)


@_xf(_STILL_FERMENTING)
@pytest.mark.parametrize("key", ["hexanoic", "octanoic", "decanoic"])
def test_07_mcfa_plateau(key: str) -> None:
    assert 0.5 <= _k(30.0, key, 14) / _k(30.0, key, 7) <= 1.5


def test_08_hexanal_falls() -> None:
    assert _k(30.0, "hexanal", 9) < 0.3 * _k(30.0, "hexanal", 0)


def test_08_nonanal_no_late_rise() -> None:
    assert _k(30.0, "nonanal", 14) <= max(_k(30.0, "nonanal", d) for d in range(2, 8))


@_xf(_BOUND_POOL)
def test_09_geraniol() -> None:
    assert 0.3 <= _k(30.0, "geraniol", 14) / _k(30.0, "geraniol", 0) <= 1.0


@pytest.mark.parametrize("key,day,hi", [
    pytest.param("methyl_salicylate", 4, 0.1, marks=_xf(_BOUND_POOL)), ("ionone_beta", 4, 0.2),
])  # fmt: skip
def test_09_fast_tea_losses(key: str, day: int, hi: float) -> None:
    assert _k(30.0, key, day) / _k(30.0, key, 0) < hi


def test_09_limonene() -> None:
    assert _k(30.0, "limonene", 11) / _k(30.0, "limonene", 2) < 0.5


@_xf(_BOUND_POOL + " (D14 linalool ~110 µg/kg; 54 even at the release and split lows)")
def test_10_linalool_d14() -> None:
    assert 1.4 <= _k(28.0, "linalool", 14) <= 34.0


# ── kefir (tests 26-32): whole milk + 3 % grains, profile organisms, 22 °C, 48 h ──


@cache
def _kefir() -> At:
    return medians("kefir", 22.0, 48.0)


def _f(key: str, h: float) -> float:
    return _kefir()(key, h)


@pytest.mark.parametrize("key,lo,hi", [("acetaldehyde", 1_270.0, 71_000.0),
                                       ("acetoin", 8_300.0, 75_000.0)])  # fmt: skip
@pytest.mark.parametrize("h", [24.0, 48.0])
def test_26_carbonyl_end_points(key: str, lo: float, hi: float, h: float) -> None:
    assert lo <= _f(key, h) <= hi


@pytest.mark.parametrize("key", ["diacetyl", "pentanedione_23"])
def test_27_c4_rise(key: str) -> None:
    assert _f(key, 8.0) > _f(key, 0.0)


def test_27_diacetyl_upper_bound() -> None:
    assert _f("diacetyl", 24.0) <= 5_600.0


@pytest.mark.parametrize("key", ["ethyl_acetate", "ethyl_butanoate", "ethyl_hexanoate",
                                 "isoamyl_acetate"])  # fmt: skip
def test_28_esters_rise(key: str) -> None:
    assert _f(key, 24.0) > _f(key, 0.0)


@_xf(_SLOW_KEFIR_YEAST)
def test_28_ethyl_octanoate_transient() -> None:
    v = [_f("ethyl_octanoate", float(h)) for h in range(49)]
    peak = max(range(49), key=lambda h: v[h])
    assert peak <= 36 and v[48] / v[24] < 0.6


@_xf(_SLOW_KEFIR_YEAST)
def test_28_ethyl_decanoate_late() -> None:
    assert _f("ethyl_decanoate", 24.0) < 0.3 * _f("ethyl_decanoate", 48.0)


@pytest.mark.parametrize("key", ["hexanoic", "octanoic", "decanoic"])
def test_29_mcfa_non_decreasing(key: str) -> None:
    v = [_f(key, float(h)) for h in range(0, 49, 4)]
    assert all(b >= a - 1e-9 for a, b in zip(v, v[1:], strict=False))


@_xf(
    "§ 5.2 / § 5.8: the milk brings ~1 mg/kg octanoic acid (03:S34) and the slow kefir yeast "
    "adds ~1 %; 03:S23's x2-4 rise (UHT milk) needs in-ferment lipolysis, not curated"
)
@pytest.mark.parametrize("key", ["octanoic", "decanoic"])
def test_29_mcfa_rise(key: str) -> None:
    assert _f(key, 48.0) / _f(key, 0.0) >= 1.5


def test_30_decalactone() -> None:
    v = [_f("decalactone_delta", float(h)) for h in range(0, 49, 4)]
    assert all(b >= a - 1e-9 for a, b in zip(v, v[1:], strict=False))
    assert v[-1] / v[0] >= 3.0


def test_30_dodecalactone() -> None:
    assert _f("dodecalactone_delta", 48.0) / _f("dodecalactone_delta", 24.0) >= 1.3


@pytest.mark.xfail(strict=True, reason=(
    "§ 6.2: 2-nonanone comes with UHT milk (03:S23), which is not a catalogue ingredient; "
    "the pasteurised milk of the default recipe has none (03:S34)"))
def test_30_nonanone_falls() -> None:
    start = _f("nonanone_2", 0.0)
    assert start > 0.0 and _f("nonanone_2", 24.0) / start < 0.5


def test_31_phenylethanol_second_day() -> None:
    assert _f("phenylethanol_2", 48.0) / _f("phenylethanol_2", 24.0) >= 2.0


@pytest.mark.parametrize("key", ["methylbutanol_3", "methylbutanol_2", "methylpropanol_2",
                                 "methylbutanal_3", "methylbutanal_2"])  # fmt: skip
def test_31_ehrlich_rise(key: str) -> None:
    assert _f(key, 24.0) > _f(key, 0.0)


def test_32_hexanal() -> None:
    assert 17.0 <= _f("hexanal", 48.0) <= 154.0


# ── cheese (tests 34-37): milk, Lc. lactis, 30 °C, 24 h ─────────────────


@cache
def _cheese_run(share: float) -> tuple[FloatArray, dict[str, FloatArray], FloatArray]:
    """Medians over a prior ensemble with the citrate-active share fixed (§ 7)."""
    n = 32
    p, _ = _setup("cheese", n, ["Lactococcus lactis"], 30.0)
    t = np.linspace(0.0, 24.0, 97)
    tr = engine.simulate(p, t, keep_states=True)
    seg = aroma.Segment(p, tr, {"Milk": 1.0})
    ctx = aroma.build_context(seg, PROFILES["cheese"], PROFILES["cheese"].co2_escapes)
    d = aroma.draws(n, 11)
    d = {**d, "share_cit_lc": np.full_like(d["share_cit_lc"], share)}
    c, _ = aroma.concentrations(ctx, d)
    med = {k: np.median(v, axis=0) for k, v in c.items()}
    return t, med, d["ing:Milk:@citrate"][:, 0] * 1000.0


def _at(t: FloatArray, v: FloatArray, h: float) -> float:
    return float(np.interp(h, t, v))


_SLOW_LC = (
    "§ 5.4: citrate uptake is gated by Lc. lactis biomass (X/x_max), which the engine's "
    "cheese culture reaches only after ~10 h at 30 °C; even at kmax_citrate 30/d, 21 % of "
    "the citrate is left at 8 h and α-acetolactate peaks at ~10 h (03:S30: ~6 h)"
)


@_xf(_SLOW_LC)
def test_34_citrate_used_by_8_h() -> None:
    t, c, p0 = _cheese_run(1.0)
    assert _at(t, c["_citrate"], 8.0) < 0.1 * float(np.median(p0))


@_xf(_SLOW_LC)
def test_34_acetolactate_peaks_at_citrate_exhaustion() -> None:
    t, c, _ = _cheese_run(1.0)
    peak = float(t[int(np.argmax(c["_acetolactate"]))])
    assert 4.0 <= peak <= 8.0


def test_34_diacetyl_rising_and_bounded() -> None:
    t, c, _ = _cheese_run(1.0)
    d12, d24 = _at(t, c["diacetyl"], 12.0), _at(t, c["diacetyl"], 24.0)
    assert 0.0 < d12 < d24 <= 41_000.0


def test_35_acetoin() -> None:
    t, c, _ = _cheese_run(1.0)
    assert np.all(np.diff(c["acetoin"]) >= -1e-9)
    assert _at(t, c["acetoin"], 24.0) / _at(t, c["diacetyl"], 24.0) > 3.0
    assert _at(t, c["acetoin"], 24.0) <= 690_000.0


def test_36_citrate_switch() -> None:
    _, c, p0 = _cheese_run(0.0)
    assert np.allclose(c["_citrate"], np.median(p0))


@pytest.mark.parametrize("key,milk", [
    ("butanoic", 1_094.0), ("octanoic", 1_037.0), ("decanoic", 380.0),
    ("decalactone_delta", 138.0), ("dodecalactone_delta", 844.0), ("hexanal", 51.3),
])  # fmt: skip
def test_37_milk_baselines(key: str, milk: float) -> None:
    v = medians("cheese", 30.0, 24.0)(key, 24.0)
    assert milk / 3.0 <= v <= milk * 3.0
