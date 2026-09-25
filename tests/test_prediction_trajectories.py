"""Literature sanity checks: each fermentation type's prior forecast (typical recipe, typical
temperature, reference organisms, no readings) against published trajectories.

Ranges are deliberately loose (these are priors, not fits), and each cites its source. A
failure here means a parameter change moved a ferment out of its documented behaviour.
Record: docs/superpowers/specs/2026-09-24-fermentation-prediction-design.md § 5.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from fermenttrack.biochem import FERMENTATION_TYPE_ORGANISMS, ORGANISMS
from fermenttrack.prediction.service import OrganismIn, PredictionInputs, predict


def _forecast(ferment: str, temp: float | None = None, horizon: float | None = None) -> Any:
    inputs = PredictionInputs(
        fermentation_type=ferment,
        now_h=0.0,
        expected_temperature_c=temp,
        organisms=tuple(
            OrganismIn(n, ORGANISMS[n], ()) for n in FERMENTATION_TYPE_ORGANISMS[ferment]
        ),
        organism_source="default",
        recipe=(),
        measurements=(),
    )
    return predict(inputs, horizon_h=horizon)


def _at(body: Any, key: str, t_h: float, q: str = "p50") -> float:
    s = next(s for s in body["series"] if s["key"] == key)
    return float(np.interp(t_h, s["t_h"], s[q]))


def _milestone(body: Any, key: str) -> Any:
    return next(m for m in body["milestones"] if m["key"] == key)


def test_sauerkraut() -> None:
    # Plengvidhya et al. 2007 (2.3 % NaCl, ~18 °C): pH <= 3.9 by ~day 7, 3.4-3.7 at day 14;
    # LAB 1e4-1e6 -> 1e8-1e9 CFU/g; Pederson & Albury: 1.5-2.3 % acidity when finished.
    b = _forecast("lacto_ferment", 18.0)
    assert 3.4 <= _at(b, "ph", 14 * 24) <= 4.2
    assert _at(b, "ph", 7 * 24, "p05") <= 3.9 <= _at(b, "ph", 7 * 24, "p95")
    assert 8.0 <= _at(b, "pop:Lactobacillus plantarum", 7 * 24) <= 9.5
    assert 8.0 <= _at(b, "lactic_acid", 28 * 24) <= 25.0
    # Leuconostoc leads early, then declines as acid builds (the classic succession)
    leuco = [_at(b, "pop:Leuconostoc mesenteroides", t) for t in (48, 28 * 24)]
    assert leuco[1] < leuco[0]


def test_kombucha() -> None:
    # Jayabalan et al. 2007 (24 ± 3 °C): pH ~5 -> ~3 by day 12, acetic acid rising over
    # two weeks; Chen & Liu 2000: ethanol stays a few g/L.
    b = _forecast("kombucha", 24.0)
    assert _at(b, "ph", 12 * 24, "p05") <= 3.0 <= _at(b, "ph", 12 * 24, "p95") + 0.4
    assert _at(b, "ph", 14 * 24) < _at(b, "ph", 0) - 0.3
    assert _at(b, "acetic_acid", 14 * 24) > _at(b, "acetic_acid", 0) + 1.0
    assert _at(b, "ethanol", 14 * 24) < 10.0
    assert _at(b, "sucrose", 14 * 24) < _at(b, "sucrose", 0) - 15.0


def test_sourdough() -> None:
    # Minervini et al. 2012 / baking practice: pH ~6 -> 3.8-4.2 in 8-16 h at 25-30 °C with a
    # 10-20 % starter; LAB ~1e9 and yeast ~1e7 CFU/g.
    b = _forecast("sourdough", 27.0)
    assert _at(b, "ph", 16, "p05") <= 4.2
    assert _at(b, "ph", 16) <= 4.6
    assert 8.7 <= _at(b, "pop:Lactobacillus sanfranciscensis", 12) <= 9.7
    assert 6.3 <= _at(b, "pop:Saccharomyces cerevisiae", 12) <= 8.0


def test_cheese_acidification() -> None:
    # Poudel et al. 2022 / practice: pH 6.6 -> 5.2-5.4 in ~4-6 h (fast) to 6+ h at 30-32 °C.
    b = _forecast("cheese", 31.0)
    t = _milestone(b, "ph_below_5_3")["t_h"]
    assert t["p05"] <= 6.0 and 4.0 <= t["p50"] <= 10.0


def test_kefir() -> None:
    # Irigoyen et al. 2005 / practice: pH 4.2-4.6 after ~24 h at 20-25 °C, 0.8-1 % lactic.
    b = _forecast("kefir", 22.0)
    assert 4.1 <= _at(b, "ph", 24) <= 4.9
    assert 5.0 <= _at(b, "lactic_acid", 24) <= 14.0


def test_vinegar() -> None:
    # Home static culture with a mother: ~1-3 g/L/day, table strength (4 %) in 3-8 weeks.
    b = _forecast("vinegar", 27.0)
    gained = _at(b, "acetic_acid", 30 * 24) - _at(b, "acetic_acid", 0)
    assert 10.0 <= gained <= 90.0
    t = _milestone(b, "acetic_above_40")["t_h"]
    assert t["p05"] is not None and t["p05"] <= 8 * 7 * 24


def test_koji() -> None:
    # Koji is harvested after 40-48 h at ~30 °C (Ito & Matsuyama 2021; Bechman et al. 2012);
    # free glucose barely rises in the bed itself (te Biesebeke et al. 2002).
    b = _forecast("koji", 30.0)
    assert not any(s["key"] == "ph" for s in b["series"])
    t = _milestone(b, "mycelium_90pct")["t_h"]
    assert t["p50"] is not None and 36.0 <= t["p50"] <= 62.0
    assert _at(b, "hexoses", 42) < 10.0
    assert b["model"]["confidence"] == "exploratory"


def test_miso() -> None:
    # Miso: pH ~6.2 -> 4.8-5.3 over months; koji enzymes break down starch within weeks
    # and protein over months, solubilising more than they free as amino acids (Allwood
    # et al. 2021; Ohnishi 1982; more in test_prediction_enzymes.py).
    b = _forecast("miso", 25.0)
    assert 4.7 <= _at(b, "ph", 180 * 24) <= 5.8
    assert _at(b, "starch", 30 * 24) < 0.3 * _at(b, "starch", 0)
    assert _at(b, "amino_acids", 180 * 24) > _at(b, "amino_acids", 30 * 24) > 0.0
    assert _at(b, "soluble_protein", 90 * 24) > 1.5 * _at(b, "amino_acids", 90 * 24)


@pytest.mark.parametrize(
    ("ferment", "lo", "hi"),
    [("lacto_ferment", 16.0, 24.0), ("kombucha", 20.0, 28.0), ("sourdough", 22.0, 30.0)],
)
def test_warmer_within_range_is_faster(ferment: str, lo: float, hi: float) -> None:
    t = 7 * 24 if ferment != "sourdough" else 12
    assert _at(_forecast(ferment, hi), "ph", t) < _at(_forecast(ferment, lo), "ph", t)
