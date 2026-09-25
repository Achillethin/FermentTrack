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

# V1-V3 are frozen (migrations 0008-0010 and 0013 load them by explicit path); the curated
# dicts below describe V4, the default snapshot.
KEGG_BIOCHEM_V1 = Path(__file__).resolve().parent / "kegg_biochem_v1.json.gz"
KEGG_BIOCHEM_V2 = Path(__file__).resolve().parent / "kegg_biochem_v2.json.gz"
KEGG_BIOCHEM_V3 = Path(__file__).resolve().parent / "kegg_biochem_v3.json.gz"
KEGG_BIOCHEM_V4 = Path(__file__).resolve().parent / "kegg_biochem_v4.json.gz"

SCHEMA_VERSION = "kegg_biochem_v4"

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
    # v2: same convention, widely used pre-reclassification names kept.
    # Current names: Lactiplantibacillus plantarum, Fructilactobacillus
    # sanfranciscensis, Komagataeibacter xylinus, Lentilactobacillus kefiri.
    "Zygosaccharomyces rouxii": "yeast",
    "Leuconostoc mesenteroides": "bacteria",
    "Acetobacter pasteurianus": "bacteria",
    "Lactobacillus kefiri": "bacteria",
    "Lactobacillus kefiranofaciens": "bacteria",
}

# Hand-curated: fermentation_type -> default organisms (dominant, not exhaustive).
FERMENTATION_TYPE_ORGANISMS: dict[str, list[str]] = {
    "kombucha": ["Saccharomyces cerevisiae", "Acetobacter aceti", "Gluconacetobacter xylinus"],
    "sourdough": ["Saccharomyces cerevisiae", "Lactobacillus sanfranciscensis"],
    "koji": ["Aspergillus oryzae"],
    "cheese": ["Lactococcus lactis"],
    "kefir": [
        "Lactococcus lactis",
        "Kluyveromyces marxianus",
        "Lactobacillus kefiri",
        "Lactobacillus kefiranofaciens",
    ],
    "miso": ["Aspergillus oryzae", "Tetragenococcus halophilus", "Zygosaccharomyces rouxii"],
    # v3: modern koji-based fish sauce ("koji garum") uses A. oryzae for its proteases,
    # amylase and glutaminase. Traditional garum relies on fish digestive enzymes and
    # halophilic bacteria and has no koji. A batch can ADD organisms through batch_organisms
    # but cannot remove a type default, so a traditional non-koji garum batch will still
    # list Aspergillus oryzae (and its enzymes). Accepted trade-off of add-only attachments.
    "garum": ["Tetragenococcus halophilus", "Aspergillus oryzae"],
    "vinegar": ["Acetobacter aceti", "Acetobacter pasteurianus"],
    "lacto_ferment": ["Lactobacillus plantarum", "Leuconostoc mesenteroides"],
}

# Hand-curated: EC number -> organisms known to express it. Names are fetched
# from KEGG (/get/ec:<num>), not hardcoded here.
ENZYME_ORGANISMS: dict[str, list[str]] = {
    "1.1.1.1": [  # alcohol dehydrogenase
        "Saccharomyces cerevisiae",
        "Zygosaccharomyces rouxii",
        "Kluyveromyces marxianus",
    ],
    "4.1.1.1": [  # pyruvate decarboxylase
        "Saccharomyces cerevisiae",
        "Zygosaccharomyces rouxii",
        "Kluyveromyces marxianus",
    ],
    "1.1.1.27": [  # L-lactate dehydrogenase (Lactococcus, Tetragenococcus: L only)
        "Lactobacillus plantarum",
        "Lactococcus lactis",
        "Lactobacillus sanfranciscensis",
        "Tetragenococcus halophilus",
        "Lactobacillus kefiranofaciens",  # v4 (KEGG lke: WANG_0270, _0755, _1884)
    ],
    "1.1.1.28": [  # D-lactate dehydrogenase (Leuconostoc: D only; the two lactobacilli: DL)
        "Lactobacillus plantarum",
        "Lactobacillus sanfranciscensis",
        "Leuconostoc mesenteroides",
    ],
    "3.2.1.1": ["Aspergillus oryzae"],  # alpha-amylase
    "3.2.1.3": ["Aspergillus oryzae"],  # glucan 1,4-alpha-glucosidase (glucoamylase)
    "3.2.1.20": ["Aspergillus oryzae"],  # alpha-glucosidase
    "3.4.21.63": ["Aspergillus oryzae"],  # oryzin
    "3.4.24.39": ["Aspergillus oryzae"],  # deuterolysin
    "3.4.23.18": ["Aspergillus oryzae"],  # aspergillopepsin I
    "3.4.16.5": ["Aspergillus oryzae"],  # carboxypeptidase C
    "3.5.1.2": ["Aspergillus oryzae"],  # glutaminase
    # beta-galactosidase. Deliberately NOT on Lactococcus lactis: it uses
    # phospho-beta-galactosidase (EC 3.2.1.85), a different enzyme.
    "3.2.1.23": [
        "Kluyveromyces marxianus",
        # v4: the kefir lactobacilli (KEGG lke: WANG_0292-0296; lkf: DNL43_02260/02265)
        "Lactobacillus kefiranofaciens",
        "Lactobacillus kefiri",
    ],
    # ADH (quinone); v4 adds the SCOBY's cellulose former (KEGG gxl: H845_603/604/1126)
    "1.1.5.5": ["Acetobacter aceti", "Acetobacter pasteurianus", "Gluconacetobacter xylinus"],
    # aldehyde dehydrogenase (NAD+); v4 adds K. xylinus (KEGG gxl: H845_1157)
    "1.2.1.3": ["Acetobacter aceti", "Gluconacetobacter xylinus"],
    "1.2.5.2": ["Acetobacter aceti", "Acetobacter pasteurianus"],  # ALDH (quinone)
    # v4 (2026-09-25): the pathway steps the fermentation forecast relies on. Every link
    # is backed by a KEGG gene annotation in that organism's reference genome
    # (/link/<org>/ec:<num>, checked 2026-09-25; genes listed in
    # docs/superpowers/specs/2026-09-25-biochemistry-v4-curation.md). KEGG has more
    # annotations than listed here; only the fermentation-relevant ones are curated.
    "3.2.1.26": [  # beta-fructofuranosidase (invertase): sucrose -> glucose + fructose
        "Saccharomyces cerevisiae",  # SUC2, YIL162W: kombucha/sourdough sucrose split
        "Lactobacillus plantarum",
        "Leuconostoc mesenteroides",
        "Tetragenococcus halophilus",
    ],
    # phosphoketolase: the defining step of heterolactic fermentation. Only on obligately
    # heterofermentative LAB; KEGG also annotates it in homofermenters (pentose use).
    "4.1.2.9": [
        "Leuconostoc mesenteroides",
        "Lactobacillus sanfranciscensis",
        "Lactobacillus kefiri",
    ],
    # glucose 1-dehydrogenase (PQQ): glucose -> gluconolactone -> gluconic acid (kombucha)
    "1.1.5.2": ["Gluconacetobacter xylinus", "Acetobacter aceti", "Acetobacter pasteurianus"],
    # maltose phosphorylase: sourdough LAB split maltose without ATP
    "2.4.1.8": [
        "Lactobacillus sanfranciscensis",
        "Lactobacillus plantarum",
        "Tetragenococcus halophilus",
    ],
    # 6-phospho-beta-galactosidase (lacG): lactose use via the PTS. Plasmid-borne in dairy
    # strains (KEGG: absent from plasmid-free Il1403/MG1363, present in dairy SK11 and
    # KLDS 4.0325), which are the ones in cheese and kefir.
    "3.2.1.85": ["Lactococcus lactis"],
    # cellulose synthase (UDP-forming): the SCOBY pellicle
    "2.4.1.12": ["Gluconacetobacter xylinus"],
    # oligo-1,6-glucosidase: KEGG files the yeast maltase MAL32 (YBR299W) here (orthology
    # K01182), the maltose step of sourdough yeast. No reaction row: this EC's reference
    # reaction is isomaltose hydrolysis, not the maltose split MAL32 performs.
    "3.2.1.10": ["Saccharomyces cerevisiae"],
}

# Hand-curated: our search name -> category. KEGG compound id + canonical
# name are resolved at build time (/find/compound/<name>, /get/cpd:<id>); the
# stored name is KEGG's canonical one (e.g. "Carbon dioxide" -> "CO2").
COMPOUNDS: dict[str, str] = {
    "Ethanol": "alcohol",
    "Acetaldehyde": "other",
    "Pyruvate": "other",
    "L-Lactic acid": "acid",
    "Acetic acid": "acid",
    "Maltose": "other",
    "D-Glucose": "other",
    "L-Glutamine": "other",
    "L-Glutamate": "other",
    "Carbon dioxide": "gas",
    "Lactose": "other",
    "D-Galactose": "other",
    "D-Lactic acid": "acid",
    # v4
    "Sucrose": "other",
    "D-Fructose": "other",
    "D-Xylulose 5-phosphate": "other",
    "Acetyl phosphate": "other",
    # searched by synonym: the comma in "D-Glucono-1,5-lactone" breaks KEGG /find
    "Gluconolactone": "other",  # hydrolyses to gluconic acid; a lactone, not an acid
    "beta-D-Glucose 1-phosphate": "other",
    "Lactose 6'-phosphate": "other",
    "D-Galactose 6-phosphate": "other",
    "UDP-glucose": "other",
    "Cellulose": "other",
}

# Hand-curated: EC number -> [(substrate compound name, product compound name)],
# representative fermentation-relevant reactions (not full pathway completeness).
# Names must be keys of COMPOUNDS. Enzymes with no entry (proteases, amylases)
# act on protein/starch, which are not KEGG compounds.
ENZYME_REACTIONS: dict[str, list[tuple[str, str]]] = {
    "4.1.1.1": [("Pyruvate", "Acetaldehyde"), ("Pyruvate", "Carbon dioxide")],
    "1.1.1.1": [("Acetaldehyde", "Ethanol")],
    "1.1.1.27": [("Pyruvate", "L-Lactic acid")],
    "1.1.1.28": [("Pyruvate", "D-Lactic acid")],
    "1.2.1.3": [("Acetaldehyde", "Acetic acid")],
    "1.1.5.5": [("Ethanol", "Acetaldehyde")],
    "1.2.5.2": [("Acetaldehyde", "Acetic acid")],
    "3.5.1.2": [("L-Glutamine", "L-Glutamate")],
    "3.2.1.20": [("Maltose", "D-Glucose")],
    "3.2.1.23": [("Lactose", "D-Glucose"), ("Lactose", "D-Galactose")],
    # v4
    "3.2.1.26": [("Sucrose", "D-Glucose"), ("Sucrose", "D-Fructose")],
    "4.1.2.9": [("D-Xylulose 5-phosphate", "Acetyl phosphate")],
    "1.1.5.2": [("D-Glucose", "Gluconolactone")],
    "2.4.1.8": [("Maltose", "D-Glucose"), ("Maltose", "beta-D-Glucose 1-phosphate")],
    "3.2.1.85": [("Lactose 6'-phosphate", "D-Galactose 6-phosphate")],
    "2.4.1.12": [("UDP-glucose", "Cellulose")],
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
            for ec, pairs in ENZYME_REACTIONS.items()
            for substrate, product in pairs
        ],
        "fermentation_type_organisms": [
            {"fermentation_type": ftype, "organism": organism}
            for ftype, organisms in FERMENTATION_TYPE_ORGANISMS.items()
            for organism in organisms
        ],
    }


def write_snapshot(data: dict[str, Any], path: Path = KEGG_BIOCHEM_V4) -> None:
    payload = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
    with path.open("wb") as f, gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0) as gz:
        gz.write(payload)


def load_snapshot(path: Path = KEGG_BIOCHEM_V4) -> dict[str, Any]:
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


def snapshot_delta(v1: dict[str, Any], v2: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Rows v2 adds over v1, by natural key; ValueError if v2 drops any v1 row.

    Natural keys: organisms by name, enzymes by ec_number, compounds by
    kegg_compound_id (canonical names may differ across snapshots),
    organism_enzymes by (organism, ec_number), fermentation_type_organisms by
    (fermentation_type, organism), enzyme_reactions by (ec_number, substrate,
    product) compared via KEGG compound ids. Reaction rows in the result also
    carry substrate_kegg_id / product_kegg_id so callers can resolve DB ids.

    Migrations 0009 and 0010 consume this output contract (table names, row keys
    incl. substrate_kegg_id / product_kegg_id, and the fermentation_type_organisms
    "organism" key): changing it changes what they do on a fresh database.
    """

    def reactions(snap: dict[str, Any]) -> list[dict[str, Any]]:
        cid = {c["name"]: c["kegg_compound_id"] for c in snap["compounds"]}
        return [
            {**r, "substrate_kegg_id": cid[r["substrate"]], "product_kegg_id": cid[r["product"]]}
            for r in snap["enzyme_reactions"]
        ]

    specs = {
        "organisms": (lambda r: r["name"], v1["organisms"], v2["organisms"]),
        "enzymes": (lambda r: r["ec_number"], v1["enzymes"], v2["enzymes"]),
        "compounds": (lambda r: r["kegg_compound_id"], v1["compounds"], v2["compounds"]),
        "organism_enzymes": (
            lambda r: (r["organism"], r["ec_number"]),
            v1["organism_enzymes"],
            v2["organism_enzymes"],
        ),
        "enzyme_reactions": (
            lambda r: (r["ec_number"], r["substrate_kegg_id"], r["product_kegg_id"]),
            reactions(v1),
            reactions(v2),
        ),
        "fermentation_type_organisms": (
            lambda r: (r["fermentation_type"], r["organism"]),
            v1["fermentation_type_organisms"],
            v2["fermentation_type_organisms"],
        ),
    }
    delta: dict[str, list[dict[str, Any]]] = {}
    for table, (key, rows1, rows2) in specs.items():
        keys1 = {key(r) for r in rows1}
        lost = keys1 - {key(r) for r in rows2}
        if lost:
            raise ValueError(f"v2 is not additive: {table} lost {sorted(map(str, lost))}")
        delta[table] = [r for r in rows2 if key(r) not in keys1]
    return delta
