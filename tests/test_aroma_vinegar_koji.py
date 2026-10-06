"""Vinegar and koji aroma against curation § 7 (tests 11-13, 16-18)."""

from __future__ import annotations

import pytest

from tests.test_aroma_lacto import At, medians

D = 24.0
Run = tuple[At, float]


@pytest.fixture(scope="module")
def vinegar() -> Run:
    # wine base, ethanol0 55 g/kg (the profile's typical recipe), surface culture, 30 °C;
    # "end" = ethanol below 5 g/kg, else 60 d
    c = medians("vinegar", 30.0, 60 * D)
    end = next((h for h in range(0, 60 * 24 + 1, 24) if c("ethanol", h) < 5e6), 60 * D)
    return c, float(end)


def _ratio(v: Run, key: str) -> float:
    c, end = v
    start, last = c(key, 0.0), c(key, end)
    if start <= 0.0:
        return float("inf") if last > 0.0 else float("nan")
    return last / start


@pytest.mark.parametrize("key", ["methylbutanol_3", "methylbutanol_2", "methylpropanol_2",
                                 "acetaldehyde"])  # fmt: skip
def test_11_aab_sink(vinegar: Run, key: str) -> None:
    assert _ratio(vinegar, key) < 0.5


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.1 kmax_aab_pe (0-0.02 lin): even with its median at 0, the prior's upper half "
    "(to 0.02/d x an AAB gate of ~1.5 over 60 d) pulls the median end/start to 0.75; "
    "02:V3, V4's x1.5-1.6 rises suggest ~0"))
def test_11_phenylethanol_kept(vinegar: Run) -> None:
    assert 0.8 <= _ratio(vinegar, "phenylethanol_2") <= 2.0


@pytest.mark.parametrize("key", ["methylbutanoic_3", "methylpropanoic_2", "acetoin"])
def test_12_aab_products(vinegar: Run, key: str) -> None:
    assert _ratio(vinegar, key) > 1.5


@pytest.mark.parametrize("key,hi", [
    pytest.param("ethyl_acetate", 0.5, marks=pytest.mark.xfail(strict=True, reason=(
        "§ 5.5 vs § 5.12: esterification of acetic acid with the remaining ethanol (the "
        "engine's 30 °C surface culture still holds 18 g/kg at 60 d) forms ethyl acetate "
        "faster than the surface strips it (0.66 x start even at ester_k 1 and k_surf 80); "
        "02:V3's -99 % needs the ethanol gone"))),
    ("ethyl_hexanoate", 0.5), ("ethyl_octanoate", 0.5), ("ethyl_decanoate", 0.5),
    pytest.param("ethyl_2methylpropanoate", 0.5, marks=pytest.mark.xfail(strict=True, reason=(
        "§ 6.2: the wine base (05:Saerens10 Table 2) lists no ethyl 2-methylpropanoate and "
        "vinegar has no yeast, so it is absent (no start value to fall from)"))),
    ("isoamyl_acetate", 0.7), ("isobutyl_acetate", 0.7),
])  # fmt: skip
def test_13_surface_stripping(vinegar: Run, key: str, hi: float) -> None:
    assert _ratio(vinegar, key) < hi


@pytest.fixture(scope="module")
def koji() -> At:
    return medians("koji", 30.0, 48.0)  # steamed rice, profile inoculum (02:J1)


@pytest.mark.parametrize("key", ["octen3ol", "octanone_3", "octanol_3", "heptanone_2",
                                 "nonanone_2"])  # fmt: skip
def test_16_c8_and_methyl_ketones(koji: At, key: str) -> None:
    assert koji(key, 12.0) < koji(key, 24.0) < koji(key, 48.0)


@pytest.mark.xfail(strict=True, reason=(
    "§ 5.2 mould a-term: the engine's koji grows fastest at 40-48 h (mycelium 35 % at 40 h, "
    "75 % at 48 h), so growth-linked esters peak at 42-46 h even with fungal esterase 2/d "
    "and k_surf 200/d; 02:J1's mid-course peak is on bran"))
@pytest.mark.parametrize("key", ["ethyl_acetate", "isoamyl_acetate"])
def test_17_transient_acetate_esters(koji: At, key: str) -> None:
    peak = max(range(0, 49), key=lambda h: koji(key, float(h)))
    assert 12 <= peak <= 40 and koji(key, 48.0) < koji(key, float(peak))


def test_18_hexanal_on_rice(koji: At) -> None:
    assert koji("hexanal", 48.0) <= 2.0 * koji("hexanal", 0.0)
