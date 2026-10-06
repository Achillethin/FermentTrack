"""The compound catalogue in code matches the curation spec's § 3 table, row for row."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/superpowers/specs/2026-10-05-aroma-curation.md"
CSV = ROOT / "src/fermenttrack/prediction/aroma_compounds_v1.csv"


def _builder() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bac", ROOT / "scripts/build_aroma_compounds.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rows() -> list[dict[str, str]]:
    return list(_builder().parse_compound_table(SPEC.read_text(encoding="utf-8")))


def test_csv_matches_spec_table() -> None:
    with CSV.open(encoding="utf-8", newline="") as f:
        frozen = list(csv.DictReader(f))
    assert _rows() == frozen


def test_catalogue_counts_and_rules() -> None:
    rows = _rows()
    assert len(rows) == 85
    status = [r["status"] for r in rows]
    assert status.count("inactive") == 3 and status.count("drop") == 5
    for r in rows:
        if r["thr_median"]:
            lo, med, hi = float(r["thr_lo"]), float(r["thr_median"]), float(r["thr_hi"])
            assert lo <= med / 3 * 1.0001 and hi >= med * 3 * 0.9999, r["key"]
        else:
            assert r["basis"] == "none", r["key"]
            assert r["status"] != "active" or r["conc_only"] == "1", r["key"]


@pytest.mark.parametrize(
    "key,median", [("ionone_beta", 0.021), ("acetic", 5600.0), ("dmts", 0.0099)]
)
def test_latest_reliable_determination_is_the_median(key: str, median: float) -> None:
    rows = {r["key"]: r for r in _rows()}
    assert float(rows[key]["thr_median"]) == pytest.approx(median)
