"""Sanity checks on the committed, frozen KEGG biochemistry snapshot (v3, the default)."""

from __future__ import annotations

import re
from collections import Counter

from fermenttrack.biochem import (
    FERMENTATION_TYPE_ORGANISMS,
    KEGG_BIOCHEM_V1,
    KEGG_BIOCHEM_V2,
    KNOWN_FERMENTATION_TYPES,
    load_snapshot,
    snapshot_delta,
)

SNAP = load_snapshot()  # v3
ORGANISMS = {o["name"] for o in SNAP["organisms"]}
ENZYMES = {e["ec_number"] for e in SNAP["enzymes"]}
COMPOUNDS = {c["name"] for c in SNAP["compounds"]}
FTYPES = {r["fermentation_type"] for r in SNAP["fermentation_type_organisms"]}


def test_organism_references_resolve() -> None:
    assert {r["organism"] for r in SNAP["fermentation_type_organisms"]} <= ORGANISMS
    assert {r["organism"] for r in SNAP["organism_enzymes"]} <= ORGANISMS


def test_enzyme_and_compound_references_resolve() -> None:
    assert {r["ec_number"] for r in SNAP["enzyme_reactions"]} <= ENZYMES
    assert {r["ec_number"] for r in SNAP["organism_enzymes"]} <= ENZYMES
    for r in SNAP["enzyme_reactions"]:
        assert r["substrate"] in COMPOUNDS and r["product"] in COMPOUNDS


def test_fermentation_types_cover_full_vocabulary() -> None:
    assert FTYPES == set(FERMENTATION_TYPE_ORGANISMS)
    assert FTYPES <= KNOWN_FERMENTATION_TYPES
    assert FTYPES == {
        "kombucha", "sourdough", "koji", "cheese", "kefir",
        "miso", "garum", "vinegar", "lacto_ferment",
    }  # fmt: skip


def test_no_duplicate_links_and_compound_ids_well_formed() -> None:
    pairs = [(r["organism"], r["ec_number"]) for r in SNAP["organism_enzymes"]]
    assert len(set(pairs)) == len(pairs)
    ft = [(r["fermentation_type"], r["organism"]) for r in SNAP["fermentation_type_organisms"]]
    assert len(set(ft)) == len(ft)
    ids = [c["kegg_compound_id"] for c in SNAP["compounds"]]
    assert max(Counter(ids).values()) == 1
    assert all(re.fullmatch(r"C\d{5}", i) for i in ids)


def test_enzymes_have_ec_shape_and_names() -> None:
    for e in SNAP["enzymes"]:
        assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", e["ec_number"])
        assert e["name"].strip()


def test_snapshots_are_nested_v1_v2_v3() -> None:
    v1, v2 = load_snapshot(KEGG_BIOCHEM_V1), load_snapshot(KEGG_BIOCHEM_V2)
    assert SNAP["schema_version"] == "kegg_biochem_v3"
    assert v2["schema_version"] == "kegg_biochem_v2" and v1["schema_version"] == "kegg_biochem_v1"
    for old, new in ((v1, v2), (v2, SNAP)):
        delta = snapshot_delta(old, new)  # raises ValueError if any old row is missing
        for table, rows in delta.items():
            assert len(new[table]) == len(old[table]) + len(rows)


def _enzymes_of(organism: str) -> set[str]:
    return {r["ec_number"] for r in SNAP["organism_enzymes"] if r["organism"] == organism}


def _organisms_of(ftype: str) -> set[str]:
    rows = SNAP["fermentation_type_organisms"]
    return {r["organism"] for r in rows if r["fermentation_type"] == ftype}


def test_v2_curation_outcomes() -> None:
    assert {"3.5.1.2", "3.4.21.63"} <= _enzymes_of("Aspergillus oryzae")
    assert "Zygosaccharomyces rouxii" in _organisms_of("miso")
    assert "1.1.1.28" in _enzymes_of("Leuconostoc mesenteroides")
    assert "1.1.1.27" not in _enzymes_of("Leuconostoc mesenteroides")
    assert "1.1.1.28" not in _enzymes_of("Lactococcus lactis")
    assert {"1.1.1.27", "1.1.1.28"} <= _enzymes_of("Lactobacillus plantarum")
    assert "3.2.1.23" not in _enzymes_of("Lactococcus lactis")
    assert "1.1.1.27" in _enzymes_of("Tetragenococcus halophilus")

    cid = {c["name"]: c["kegg_compound_id"] for c in SNAP["compounds"]}
    reactions = {
        (r["ec_number"], cid[r["substrate"]], cid[r["product"]]) for r in SNAP["enzyme_reactions"]
    }
    assert ("4.1.1.1", "C00022", "C00011") in reactions  # pyruvate -> CO2
    assert ("4.1.1.1", "C00022", "C00084") in reactions  # ... alongside pyruvate -> acetaldehyde
    assert ("1.1.5.5", "C00469", "C00084") in reactions  # ethanol -> acetaldehyde
    assert ("1.1.1.28", "C00022", "C00256") in reactions  # pyruvate -> D-lactate


def _derived_enzymes(ftype: str) -> set[str]:
    """EC numbers a batch of this type gets by default (mirrors get_batch_biochemistry)."""
    return {ec for org in _organisms_of(ftype) for ec in _enzymes_of(org)}


def test_v3_koji_garum() -> None:
    v2 = load_snapshot(KEGG_BIOCHEM_V2)
    assert _organisms_of("garum") == {"Tetragenococcus halophilus", "Aspergillus oryzae"}
    assert {"3.5.1.2", "3.4.21.63"} <= _derived_enzymes("garum")  # glutaminase, oryzin
    v2_types = {
        r["fermentation_type"]: {
            x["organism"] for x in v2["fermentation_type_organisms"]
            if x["fermentation_type"] == r["fermentation_type"]
        }
        for r in v2["fermentation_type_organisms"]
    }
    for ftype in FTYPES - {"garum"}:
        assert _organisms_of(ftype) == v2_types[ftype], ftype
