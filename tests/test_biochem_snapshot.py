"""Sanity checks on the committed, frozen KEGG biochemistry snapshot."""

from __future__ import annotations

import re
from collections import Counter

from fermenttrack.biochem import (
    FERMENTATION_TYPE_ORGANISMS,
    KEGG_BIOCHEM_V1,
    KNOWN_FERMENTATION_TYPES,
    load_snapshot,
)

SNAP = load_snapshot(KEGG_BIOCHEM_V1)  # repointed to v2 once the v2 snapshot is built
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
