"""Freeze the curation spec's § 3 compound table into src/.../aroma_compounds_v1.csv.

Run: python scripts/build_aroma_compounds.py   (tests/test_aroma_catalogue.py guards drift)
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/superpowers/specs/2026-10-05-aroma-curation.md"
OUT = ROOT / "src/fermenttrack/prediction/aroma_compounds_v1.csv"
FIELDS = (
    "key", "name", "pubchem", "chebi", "kegg", "descriptor", "series", "thr_median", "thr_lo",
    "thr_hi", "basis", "ph_kind", "pka", "templates", "status", "conc_only", "p0_pending",
)  # fmt: skip
_SECTION = re.compile(r"^## 3\. Compound table$(.*?)^## 4\.", re.M | re.S)
_NUM = r"\d+(?:\.\d+)?"


def _id(part: str) -> str:
    tok = part.strip().split("/")[0].split()[0] if part.strip() else ""
    return "" if tok in ("—", "-") else tok


def parse_compound_table(spec_text: str) -> list[dict[str, str]]:
    m = _SECTION.search(spec_text)
    if not m:
        raise ValueError("§ 3 not found")
    out = []
    for line in m.group(1).splitlines():
        if not line.startswith("| ") or line.startswith(("| key", "|---")):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 9:
            raise ValueError(f"expected 9 cells: {line}")
        key, name, ids, desc, thr, basis, ph, template, status = cells
        idp = (ids.split("·") + ["", "", ""])[:3]
        dm = re.match(r"(.*)\(([^()]*)\)\s*$", desc)
        descriptor, series = (dm.group(1).strip(), dm.group(2)) if dm else (desc, "")
        nums = [] if thr.startswith("none") else re.findall(_NUM, thr.split("(")[0])
        b = re.sub(r"\*", "", basis).split("·")[0].strip().split()[0].rstrip(".")
        ph_kind, pka = "", ""
        if ph.startswith(("acid", "base")):
            ph_kind, pka = ph.split()[0], re.findall(_NUM, ph)[0]
        s = re.sub(r"\*", "", status)
        kind = "drop" if s.startswith("drop") else "inactive" if s.startswith("inactive") else "active"
        out.append({
            "key": key, "name": name, "pubchem": _id(idp[0]), "chebi": _id(idp[1]),
            "kegg": _id(idp[2]), "descriptor": descriptor,
            "series": ";".join(x.strip() for x in series.split(",") if x.strip()),
            "thr_median": nums[0] if nums else "", "thr_lo": nums[1] if nums else "",
            "thr_hi": nums[2] if nums else "", "basis": b, "ph_kind": ph_kind, "pka": pka,
            "templates": ";".join(re.findall(r"T\d+", template)) or ("engine" if "engine" in template else ""),
            "status": kind, "conc_only": "1" if "conc-only" in s else "0",
            "p0_pending": "1" if "P0 pending" in s else "0",
        })  # fmt: skip
    return out


if __name__ == "__main__":
    rows = parse_compound_table(SPEC.read_text(encoding="utf-8"))
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} compounds -> {OUT}", file=sys.stderr)
