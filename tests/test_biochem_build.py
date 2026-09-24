"""Pure checks on KEGG flat-file/TSV parsing and snapshot assembly. No network, no DB."""

from __future__ import annotations

from pathlib import Path

import pytest

from fermenttrack.biochem import (
    COMPOUNDS,
    ENZYME_ORGANISMS,
    ENZYME_REACTIONS,
    build_snapshot,
    kegg_entry_name,
    kegg_find_id,
    load_snapshot,
    parse_kegg_flatfile,
    snapshot_delta,
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

# Real KEGG `find/compound` responses carry bare ids (no "cpd:" prefix).
FIND_RESPONSE = "C00469\tEthanol; Ethyl alcohol; EtOH\n"


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
    response = "C00189\tEthanolamine; 2-Aminoethanol\nC00469\tEthanol; Ethyl alcohol\n"
    assert kegg_find_id(response, "Ethanol") == "C00469"


def test_kegg_find_id_accepts_prefixed_ids() -> None:
    """The 'cpd:'-prefixed form (as `find` without a db) also works."""
    assert kegg_find_id("cpd:C00469\tEthanol; Ethyl alcohol\n", "Ethanol") == "C00469"


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
    assert data["schema_version"] == "kegg_biochem_v2"
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


def test_enzyme_reactions_reference_curated_names() -> None:
    assert set(ENZYME_REACTIONS) <= set(ENZYME_ORGANISMS)
    for pairs in ENZYME_REACTIONS.values():
        assert pairs
        for substrate, product in pairs:
            assert substrate in COMPOUNDS and product in COMPOUNDS


def test_build_snapshot_emits_every_reaction_of_an_enzyme() -> None:
    data = build_snapshot(_fake_enzyme_names(), _fake_compound_lookup())
    pdc = {
        (r["substrate"], r["product"])
        for r in data["enzyme_reactions"]
        if r["ec_number"] == "4.1.1.1"
    }
    assert pdc == {("Pyruvate", "Acetaldehyde"), ("Pyruvate", "Carbon dioxide")}
    assert len(data["enzyme_reactions"]) == sum(map(len, ENZYME_REACTIONS.values()))


def _tiny_snapshot(extra: bool) -> dict:
    snap = {
        "organisms": [{"name": "A", "kingdom": "yeast"}],
        "enzymes": [{"ec_number": "1.1.1.1", "name": "adh"}],
        "compounds": [
            {"name": "Ethanol", "kegg_compound_id": "C00469", "category": "alcohol"},
            {"name": "Acetate", "kegg_compound_id": "C00033", "category": "acid"},
        ],
        "organism_enzymes": [{"organism": "A", "ec_number": "1.1.1.1"}],
        "enzyme_reactions": [
            {"ec_number": "1.1.1.1", "substrate": "Ethanol", "product": "Acetate"}
        ],
        "fermentation_type_organisms": [{"fermentation_type": "koji", "organism": "A"}],
    }
    if extra:
        snap["organisms"].append({"name": "B", "kingdom": "mold"})
        # v2 renames a v1 compound: matching must go by kegg_compound_id
        snap["compounds"][1] = {
            "name": "Acetic acid", "kegg_compound_id": "C00033", "category": "acid",
        }
        snap["compounds"].append({"name": "CO2", "kegg_compound_id": "C00011", "category": "gas"})
        snap["enzyme_reactions"] = [
            {"ec_number": "1.1.1.1", "substrate": "Ethanol", "product": "Acetic acid"},
            {"ec_number": "1.1.1.1", "substrate": "Ethanol", "product": "CO2"},
        ]
        snap["organism_enzymes"].append({"organism": "B", "ec_number": "1.1.1.1"})
        snap["fermentation_type_organisms"].append({"fermentation_type": "miso", "organism": "B"})
    return snap


def test_snapshot_delta_returns_only_additions() -> None:
    delta = snapshot_delta(_tiny_snapshot(False), _tiny_snapshot(True))
    assert [o["name"] for o in delta["organisms"]] == ["B"]
    assert delta["enzymes"] == []
    assert [c["kegg_compound_id"] for c in delta["compounds"]] == ["C00011"]
    assert delta["organism_enzymes"] == [{"organism": "B", "ec_number": "1.1.1.1"}]
    assert [(r["substrate_kegg_id"], r["product_kegg_id"]) for r in delta["enzyme_reactions"]] == [
        ("C00469", "C00011")
    ]
    assert delta["fermentation_type_organisms"] == [
        {"fermentation_type": "miso", "organism": "B"}
    ]
    assert all(v == [] for v in snapshot_delta(_tiny_snapshot(True), _tiny_snapshot(True)).values())


def test_snapshot_delta_rejects_non_additive_v2() -> None:
    v1, v2 = _tiny_snapshot(False), _tiny_snapshot(True)
    v2["organism_enzymes"] = []
    with pytest.raises(ValueError, match="not additive: organism_enzymes"):
        snapshot_delta(v1, v2)
    v2 = _tiny_snapshot(True)
    v2["compounds"][2]["kegg_compound_id"] = "C99999"  # ok, only additions differ
    assert snapshot_delta(v1, v2)["compounds"][0]["kegg_compound_id"] == "C99999"
    v2["compounds"][0]["kegg_compound_id"] = "C11111"  # a v1 compound id vanishes
    with pytest.raises(ValueError, match="not additive: compounds"):
        snapshot_delta(v1, v2)


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
