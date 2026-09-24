"""Fermentation biochemistry reference data: organisms, enzymes, compounds.

Design: docs/superpowers/specs/2026-09-23-fermentation-biochemistry-design.md
Sourced from KEGG (canonical enzyme/compound identity) plus hand-curated
fermentation domain knowledge (which organisms/enzymes are relevant to which
fermentation type — KEGG doesn't expose that mapping directly).
"""

from __future__ import annotations

import gzip
import json
import uuid
from pathlib import Path
from typing import Any

from fermenttrack.stages import STAGE_MACHINES

KEGG_BIOCHEM_V1 = Path(__file__).resolve().parent / "kegg_biochem_v1.json.gz"

SCHEMA_VERSION = "kegg_biochem_v1"

KNOWN_FERMENTATION_TYPES = set(STAGE_MACHINES) | {"kefir", "vinegar"}

# Hand-curated: organism name -> kingdom.
ORGANISMS: dict[str, str] = {
    "Saccharomyces cerevisiae": "yeast",
    "Acetobacter aceti": "bacteria",
    "Aspergillus oryzae": "mold",
    "Lactobacillus plantarum": "bacteria",
    "Lactococcus lactis": "bacteria",
    "Tetragenococcus halophilus": "bacteria",
    "Kluyveromyces marxianus": "yeast",
    # Spec-named organisms; pre-reclassification synonyms (now
    # Fructilactobacillus sanfranciscensis / Komagataeibacter xylinus).
    "Gluconacetobacter xylinus": "bacteria",
    "Lactobacillus sanfranciscensis": "bacteria",
}

# Hand-curated: fermentation_type -> default organisms (dominant, not exhaustive).
FERMENTATION_TYPE_ORGANISMS: dict[str, list[str]] = {
    "kombucha": ["Saccharomyces cerevisiae", "Acetobacter aceti", "Gluconacetobacter xylinus"],
    "sourdough": ["Saccharomyces cerevisiae", "Lactobacillus sanfranciscensis"],
    "koji": ["Aspergillus oryzae"],
    "cheese": ["Lactococcus lactis"],
    "kefir": ["Lactococcus lactis", "Kluyveromyces marxianus"],
    "miso": ["Aspergillus oryzae", "Tetragenococcus halophilus"],
    "garum": ["Tetragenococcus halophilus"],
    "vinegar": ["Acetobacter aceti"],
    "lacto_ferment": ["Lactobacillus plantarum"],
}

# Hand-curated: EC number -> organisms known to express it. Names are fetched
# from KEGG (/get/ec:<num>), not hardcoded here.
ENZYME_ORGANISMS: dict[str, list[str]] = {
    "1.1.1.1": ["Saccharomyces cerevisiae"],  # alcohol dehydrogenase
    "4.1.1.1": ["Saccharomyces cerevisiae"],  # pyruvate decarboxylase
    "1.1.1.27": [  # L-lactate dehydrogenase
        "Lactobacillus plantarum",
        "Lactococcus lactis",
        "Lactobacillus sanfranciscensis",
    ],
    "3.2.1.1": ["Aspergillus oryzae"],  # alpha-amylase
    "1.2.1.3": ["Acetobacter aceti"],  # aldehyde dehydrogenase (NAD+)
}

# Hand-curated: our search name -> category. KEGG compound id + canonical
# name are resolved at build time (/find/compound/<name>, /get/cpd:<id>).
COMPOUNDS: dict[str, str] = {
    "Ethanol": "alcohol",
    "Acetaldehyde": "other",
    "Pyruvate": "other",
    "L-Lactic acid": "acid",
    "Acetic acid": "acid",
}

# Hand-curated: EC number -> (substrate compound name, product compound name),
# at most one representative fermentation-relevant reaction per enzyme (not full
# pathway completeness). Names must be keys of COMPOUNDS.
ENZYME_REACTIONS: dict[str, tuple[str, str]] = {
    "4.1.1.1": ("Pyruvate", "Acetaldehyde"),
    "1.1.1.1": ("Acetaldehyde", "Ethanol"),
    "1.1.1.27": ("Pyruvate", "L-Lactic acid"),
    "1.2.1.3": ("Acetaldehyde", "Acetic acid"),
}


def parse_kegg_flatfile(text: str) -> dict[str, list[str]]:
    """KEGG 'get' operation flat file -> {field_tag: [content_lines]}.

    Standard KEGG flat-file format: each line's first 12 columns are a field
    tag (blank on continuation lines), the rest is content; entry ends at '///'.
    """
    fields: dict[str, list[str]] = {}
    current_tag: str | None = None
    for line in text.splitlines():
        if line.startswith("///"):
            break
        if not line.strip():
            continue
        tag = line[:12].strip()
        content = line[12:].strip()
        if tag:
            current_tag = tag
            fields.setdefault(current_tag, []).append(content)
        elif current_tag:
            fields[current_tag].append(content)
    return fields


def kegg_entry_name(text: str) -> str:
    """First NAME line of a KEGG 'get' flat file, trailing ';' stripped."""
    fields = parse_kegg_flatfile(text)
    if "NAME" not in fields:
        raise ValueError("KEGG entry has no NAME field")
    return fields["NAME"][0].rstrip(";")


def kegg_find_id(text: str, query: str) -> str:
    """Find a compound ID by exact name match in KEGG 'find' TSV response.

    KEGG 'find' is a keyword search, so first hit may be wrong (e.g., Ethanolamine
    before Ethanol). Parse each TSV line as '[<db>:]<ID>\\t<names>', split names
    on ';', strip whitespace, and return the bare ID of the first line whose
    names contain query exactly (case-insensitive).

    Args:
        text: KEGG find TSV response (one or more lines, format 'C00469\\tName1; Name2')
        query: Exact name to match (case-insensitive)

    Returns:
        Bare compound ID (e.g., 'C00469')

    Raises:
        ValueError: If no exact match found or text is empty
    """
    query_lower = query.lower()
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            raw_id, names_part = line.split("\t", 1)
        except ValueError:
            continue
        names = [n.strip() for n in names_part.split(";")]
        if any(n.lower() == query_lower for n in names):
            return raw_id.split(":")[-1]  # bare ("C00469") or prefixed ("cpd:C00469")
    raise ValueError(f"no exact KEGG match for {query!r}")


def build_snapshot(
    enzyme_names: dict[str, str], compound_lookup: dict[str, tuple[str, str]]
) -> dict[str, Any]:
    """Curated domain data + fetched KEGG identity -> the full snapshot dict.

    enzyme_names: EC number -> canonical name (from KEGG /get/ec:<num>)
    compound_lookup: our COMPOUNDS key -> (kegg_compound_id, kegg canonical name)
    """
    missing_enzymes = set(ENZYME_ORGANISMS) - set(enzyme_names)
    if missing_enzymes:
        raise ValueError(f"missing KEGG enzyme names for: {sorted(missing_enzymes)}")
    missing_compounds = set(COMPOUNDS) - set(compound_lookup)
    if missing_compounds:
        raise ValueError(f"missing KEGG compound lookups for: {sorted(missing_compounds)}")
    unknown_types = set(FERMENTATION_TYPE_ORGANISMS) - KNOWN_FERMENTATION_TYPES
    if unknown_types:
        raise ValueError(f"unknown fermentation_type in curation: {sorted(unknown_types)}")

    return {
        "schema_version": SCHEMA_VERSION,
        "organisms": [{"name": name, "kingdom": kingdom} for name, kingdom in ORGANISMS.items()],
        "enzymes": [{"ec_number": ec, "name": enzyme_names[ec]} for ec in ENZYME_ORGANISMS],
        "compounds": [
            {
                "name": compound_lookup[name][1],
                "kegg_compound_id": compound_lookup[name][0],
                "category": category,
            }
            for name, category in COMPOUNDS.items()
        ],
        "organism_enzymes": [
            {"organism": organism, "ec_number": ec}
            for ec, organisms in ENZYME_ORGANISMS.items()
            for organism in organisms
        ],
        "enzyme_reactions": [
            {
                "ec_number": ec,
                "substrate": compound_lookup[substrate][1],
                "product": compound_lookup[product][1],
            }
            for ec, (substrate, product) in ENZYME_REACTIONS.items()
        ],
        "fermentation_type_organisms": [
            {"fermentation_type": ftype, "organism": organism}
            for ftype, organisms in FERMENTATION_TYPE_ORGANISMS.items()
            for organism in organisms
        ],
    }


def write_snapshot(data: dict[str, Any], path: Path = KEGG_BIOCHEM_V1) -> None:
    payload = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
    with path.open("wb") as f, gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as gz:
        gz.write(payload)


def load_snapshot(path: Path = KEGG_BIOCHEM_V1) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def snapshot_seed_rows(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Snapshot dict -> insert-ready rows per table, UUIDs assigned here."""
    organism_id = {o["name"]: uuid.uuid4() for o in data["organisms"]}
    enzyme_id = {e["ec_number"]: uuid.uuid4() for e in data["enzymes"]}
    compound_id = {c["name"]: uuid.uuid4() for c in data["compounds"]}

    return {
        "organisms": [
            {
                "id": organism_id[o["name"]], "name": o["name"], "kingdom": o["kingdom"],
                "ncbi_taxon_id": None, "kegg_organism_code": None,
                "source_version": data["schema_version"],
            }
            for o in data["organisms"]
        ],
        "enzymes": [
            {
                "id": enzyme_id[e["ec_number"]], "ec_number": e["ec_number"], "name": e["name"],
                "kegg_entry_id": None, "source_version": data["schema_version"],
            }
            for e in data["enzymes"]
        ],
        "compounds": [
            {
                "id": compound_id[c["name"]], "name": c["name"],
                "kegg_compound_id": c["kegg_compound_id"], "category": c["category"],
                "source_version": data["schema_version"],
            }
            for c in data["compounds"]
        ],
        "organism_enzymes": [
            {
                "id": uuid.uuid4(),
                "organism_id": organism_id[oe["organism"]],
                "enzyme_id": enzyme_id[oe["ec_number"]],
            }
            for oe in data["organism_enzymes"]
        ],
        "enzyme_reactions": [
            {
                "id": uuid.uuid4(),
                "enzyme_id": enzyme_id[er["ec_number"]],
                "substrate_id": compound_id[er["substrate"]],
                "product_id": compound_id[er["product"]],
            }
            for er in data["enzyme_reactions"]
        ],
        "fermentation_type_organisms": [
            {
                "id": uuid.uuid4(),
                "fermentation_type": fo["fermentation_type"],
                "organism_id": organism_id[fo["organism"]],
                "is_default": True,
            }
            for fo in data["fermentation_type_organisms"]
        ],
    }
