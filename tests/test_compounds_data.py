"""Data lint for the derived layer's curated reference data (prediction/compounds.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fermenttrack.prediction import compounds as C


def test_thresholds_are_positive_log_priors() -> None:
    for p in (C.SWEET_THRESHOLD, C.SOUR_THRESHOLD, C.UMAMI_THRESHOLD, C.ALCOHOL_THRESHOLD):
        assert 0 < p.lo < p.median < p.hi and p.scale == "log"


def test_sucrose_threshold_is_the_panel_recognition_median() -> None:
    # Höhl et al. 2014: 3.7 log10 µmol/L = 5.01 mmol/L x 342.3 g/mol = 1.72 g/L
    assert C.SWEET_THRESHOLD.median == pytest.approx(10**3.7 * 1e-6 * 342.3, rel=0.01)
    # 90 % of the panel within 10^(±1.645 x 0.5) of the median
    assert C.SWEET_THRESHOLD.hi / C.SWEET_THRESHOLD.median == pytest.approx(
        10 ** (1.6448536 * 0.5), rel=1e-3
    )


def test_sweetness_and_glutamate_shares_are_sane() -> None:
    assert C.SWEETNESS["sucrose"].median == 1.0
    for p in C.SWEETNESS.values():
        assert 0.1 <= p.lo <= p.hi <= 2.0
    for p in C.GLUTAMATE_SHARE.values():
        assert 0.0 < p.lo <= p.hi < 1.0


def test_energy_factors_are_annex_xiv() -> None:
    assert C.ENERGY == {
        "carbohydrate": (4.0, 17.0), "protein": (4.0, 17.0), "fat": (9.0, 37.0),
        "alcohol": (7.0, 29.0), "organic_acid": (3.0, 13.0), "fibre": (2.0, 8.0),
    }  # fmt: skip


def test_every_number_is_cited() -> None:
    text = Path(C.__file__).read_text(encoding="utf-8")
    for cited in ("Höhl", "Johanningsmeier", "Mattes", "Park et al. 2002", "1169/2011", "est."):
        assert cited in text
