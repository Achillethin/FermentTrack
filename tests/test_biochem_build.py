"""Pure checks on KEGG flat-file/TSV parsing and snapshot assembly. No network, no DB."""

from __future__ import annotations

from pathlib import Path

import pytest

from fermenttrack.biochem import (
    COMPOUNDS,
    ENZYME_ORGANISMS,
    build_snapshot,
    kegg_entry_name,
    kegg_find_id,
    load_snapshot,
    parse_kegg_flatfile,
    snapshot_seed_rows,
    write_snapshot,
)

ENZYME_FLATFILE = """ENTRY       EC 1.1.1.1                  Enzyme
NAME        alcohol dehydrogenase;
            aldehyde reductase
CLASS       Oxidoreductases
///
"""

COMPOUND_FLATFILE = """ENTRY       C00469                      Compound
NAME        Ethanol;
            Ethyl alcohol
///
"""

FIND_RESPONSE = "cpd:C00469\tEthanol; Ethyl alcohol; EtOH\n"


def _fake_enzyme_names() -> dict[str, str]:
    return {ec: f"enzyme for {ec}" for ec in ENZYME_ORGANISMS}


def _fake_compound_lookup() -> dict[str, tuple[str, str]]:
    return {name: (f"C{i:05d}", name) for i, name in enumerate(COMPOUNDS, start=1)}


def test_parse_kegg_flatfile_multiline_name() -> None:
    fields = parse_kegg_flatfile(ENZYME_FLATFILE)
    assert fields["NAME"] == ["alcohol dehydrogenase;", "aldehyde reductase"]
    assert fields["CLASS"] == ["Oxidoreductases"]


def test_kegg_entry_name_strips_semicolon() -> None:
    assert kegg_entry_name(ENZYME_FLATFILE) == "alcohol dehydrogenase"
    assert kegg_entry_name(COMPOUND_FLATFILE) == "Ethanol"


def test_kegg_entry_name_missing_name_field_raises_valueerror() -> None:
    """Entry with no NAME field raises ValueError."""
    no_name_flatfile = """ENTRY       EC 1.1.1.1                  Enzyme
CLASS       Oxidoreductases
///
"""
    with pytest.raises(ValueError, match="KEGG entry has no NAME field"):
        kegg_entry_name(no_name_flatfile)


def test_kegg_find_id_happy_path() -> None:
    """Find exact match in KEGG find response."""
    assert kegg_find_id(FIND_RESPONSE, "Ethanol") == "C00469"


def test_kegg_find_id_case_insensitive() -> None:
    """Find is case-insensitive."""
    assert kegg_find_id(FIND_RESPONSE, "ethanol") == "C00469"


def test_kegg_find_id_two_lines_takes_correct_hit() -> None:
    """When first hit is wrong (Ethanolamine), find second hit (Ethanol)."""
    response = "cpd:C00189\tEthanolamine; 2-Aminoethanol\ncpd:C00469\tEthanol; Ethyl alcohol\n"
    assert kegg_find_id(response, "Ethanol") == "C00469"


def test_kegg_find_id_no_match_raises_valueerror() -> None:
    """No exact match raises ValueError."""
    with pytest.raises(ValueError, match="no exact KEGG match for 'Nonexistent'"):
        kegg_find_id(FIND_RESPONSE, "Nonexistent")


def test_kegg_find_id_empty_text_raises_valueerror() -> None:
    """Empty response raises ValueError."""
    with pytest.raises(ValueError, match="no exact KEGG match for 'Ethanol'"):
        kegg_find_id("", "Ethanol")


def test_build_snapshot_requires_every_curated_enzyme_and_compound() -> None:
    with pytest.raises(ValueError, match="missing KEGG enzyme names"):
        build_snapshot({}, _fake_compound_lookup())
    with pytest.raises(ValueError, match="missing KEGG compound lookups"):
        build_snapshot(_fake_enzyme_names(), {})


def test_build_snapshot_and_seed_rows_round_trip(tmp_path: Path) -> None:
    data = build_snapshot(_fake_enzyme_names(), _fake_compound_lookup())
    assert data["schema_version"] == "kegg_biochem_v1"
    assert {o["name"] for o in data["organisms"]} >= {"Saccharomyces cerevisiae"}
    assert {e["ec_number"] for e in data["enzymes"]} == set(ENZYME_ORGANISMS)

    path = tmp_path / "snap.json.gz"
    write_snapshot(data, path)
    write_snapshot(data, tmp_path / "snap2.json.gz")
    assert path.read_bytes() == (tmp_path / "snap2.json.gz").read_bytes()  # gzip mtime=0
    assert load_snapshot(path) == data

    seed = snapshot_seed_rows(data)
    assert len(seed["organisms"]) == len(data["organisms"])
    organism_ids = {o["id"] for o in seed["organisms"]}
    assert all(row["organism_id"] in organism_ids for row in seed["fermentation_type_organisms"])
    compound_ids = {c["id"] for c in seed["compounds"]}
    assert all(
        row["substrate_id"] in compound_ids and row["product_id"] in compound_ids
        for row in seed["enzyme_reactions"]
    )


def test_unknown_fermentation_type_rejected() -> None:
    import fermenttrack.biochem as biochem

    original = dict(biochem.FERMENTATION_TYPE_ORGANISMS)
    biochem.FERMENTATION_TYPE_ORGANISMS["not_a_real_type"] = ["Saccharomyces cerevisiae"]
    try:
        with pytest.raises(ValueError, match="unknown fermentation_type"):
            build_snapshot(_fake_enzyme_names(), _fake_compound_lookup())
    finally:
        biochem.FERMENTATION_TYPE_ORGANISMS.clear()
        biochem.FERMENTATION_TYPE_ORGANISMS.update(original)
