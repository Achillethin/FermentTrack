# Fermentation Biochemistry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a KEGG-sourced reference layer (organisms, enzymes, compounds) keyed by fermentation type, with a per-batch override for custom strains, plus a read endpoint — so a future predictive model can use organism/enzyme/compound presence as features.

**Architecture:** Seven new tables (3 reference: `organisms`/`enzymes`/`compounds`; 3 linking: `organism_enzymes`/`enzyme_reactions`/`fermentation_type_organisms`; 1 per-batch override: `batch_organisms`), loaded from a frozen, offline-built KEGG snapshot — same pattern as the existing `fdc_catalog_v1.csv.gz`. A read endpoint resolves each batch's organisms (override if present, else the fermentation-type default) and the enzymes/compounds reachable from them.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async, `Mapped`/`mapped_column`), Alembic, Pydantic v2, pytest + pytest-asyncio, httpx (already a project dependency, used for both the app's test client and outbound KEGG calls).

**Spec:** `docs/superpowers/specs/2026-09-23-fermentation-biochemistry-design.md`

## Global Constraints

- Reference tables (`organisms`, `enzymes`, `compounds`) carry a `source_version` column recording which frozen snapshot loaded them (e.g. `"kegg_biochem_v1"`) — same discipline as `IngredientNutrient.source_version`.
- The frozen snapshot (`src/fermenttrack/kegg_biochem_v1.json.gz`) is gzip-written with `mtime=0` for byte-reproducibility, exactly like `fdc_catalog_v1.csv.gz`.
- `fermentation_type` stays a free-text column (no new lookup table), validated at build time against `stages.STAGE_MACHINES.keys() | {"kefir", "vinegar"}` — the same 9-type vocabulary `Ingredient.fermentation_systems` already uses.
- The fermentation-type→organism and organism→enzyme mappings are hand-curated domain knowledge (KEGG doesn't expose "which organism ferments kombucha"); KEGG supplies canonical identity only — EC-number validity + name, and compound-ID + name. This is a deliberate narrowing from the spec's original phrasing ("where KEGG's organism-linked ortholog data resolves one") — per-genome KEGG queries for organism↔enzyme linkage are fragile and out of this plan's scope; the linkage is curated by hand instead, same as the fermentation-type↔organism mapping the spec already calls hand-curated.
- No frontend UI in this plan (see spec's "Out of scope").
- Every new async DB test follows `tests/conftest.py`'s `db_session`/`client` fixtures and `pytest.mark.asyncio` — the existing project convention (see `tests/test_ingredients_model.py`).

---

## File Structure

```
src/fermenttrack/
  models.py           MODIFY — add Organism, Enzyme, Compound, OrganismEnzyme,
                       EnzymeReaction, FermentationTypeOrganism, BatchOrganism;
                       add Batch.batch_organisms relationship
  biochem.py           CREATE — curated domain data, KEGG flat-file/TSV parsing,
                       build_snapshot(), write/load_snapshot(), snapshot_seed_rows()
  schemas.py          MODIFY — add Organism/Enzyme/Compound/BatchBiochemistry/
                       BatchOrganism schemas; fix stale BatchPreview comment
  routers/organisms.py CREATE — GET /organisms?q= search
  routers/batches.py  MODIFY — add GET /{id}/biochemistry, POST /{id}/organisms
  main.py             MODIFY — register organisms router
  kegg_biochem_v1.json.gz  CREATE (Task 3, committed binary) — frozen snapshot

scripts/build_kegg_biochem.py  CREATE — offline builder, calls KEGG's public REST API

alembic/versions/0008_fermentation_biochemistry.py  CREATE

tests/
  test_biochemistry_model.py  CREATE — ORM round-trip
  test_biochem_build.py       CREATE — pure build-function tests (no network)
  test_organisms.py           CREATE — search endpoint
  test_batch_biochemistry.py  CREATE — read endpoint + override endpoint

docs/STRATEGY.md                        MODIFY — Direction 3 reversal note
docs/DEPENDENCIES.md                    MODIFY — cross-reference note
docs/specs/fermentgraph-evolution.md    MODIFY — cross-reference note
```

---

### Task 1: ORM models

**Files:**
- Modify: `src/fermenttrack/models.py`
- Test: `tests/test_biochemistry_model.py`

**Interfaces:**
- Produces: `Organism(id, name, kingdom, ncbi_taxon_id, kegg_organism_code, source_version)`, `Enzyme(id, ec_number, name, kegg_entry_id, source_version)`, `Compound(id, kegg_compound_id, name, category, source_version)`, `OrganismEnzyme(id, organism_id, enzyme_id)` with `.enzyme` relationship, `EnzymeReaction(id, enzyme_id, substrate_id, product_id)` with `.substrate`/`.product` relationships, `FermentationTypeOrganism(id, fermentation_type, organism_id, is_default)` with `.organism` relationship, `BatchOrganism(id, batch_id, organism_id, source, notes, created_at)` with `.batch`/`.organism` relationships. `Batch.batch_organisms` (cascade delete).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_biochemistry_model.py
"""Organism/Enzyme/Compound/BatchOrganism model round-trip. No API — see
test_organisms.py and test_batch_biochemistry.py for HTTP-level behavior."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import (
    Batch,
    BatchOrganism,
    Compound,
    Culture,
    Enzyme,
    EnzymeReaction,
    FermentationTypeOrganism,
    Organism,
    OrganismEnzyme,
)


@pytest.mark.asyncio
async def test_organism_enzyme_compound_round_trip(db_session: AsyncSession) -> None:
    yeast = Organism(name="Saccharomyces cerevisiae", kingdom="yeast", source_version="v1")
    adh = Enzyme(ec_number="1.1.1.1", name="alcohol dehydrogenase", source_version="v1")
    acetaldehyde = Compound(name="Acetaldehyde", category="other", source_version="v1")
    ethanol = Compound(name="Ethanol", category="alcohol", source_version="v1")
    db_session.add_all([yeast, adh, acetaldehyde, ethanol])
    await db_session.flush()

    db_session.add(OrganismEnzyme(organism_id=yeast.id, enzyme_id=adh.id))
    db_session.add(
        EnzymeReaction(enzyme_id=adh.id, substrate_id=acetaldehyde.id, product_id=ethanol.id)
    )
    db_session.add(FermentationTypeOrganism(fermentation_type="kombucha", organism_id=yeast.id))
    await db_session.commit()

    result = await db_session.execute(select(Enzyme).where(Enzyme.ec_number == "1.1.1.1"))
    fetched = result.scalar_one()
    assert fetched.name == "alcohol dehydrogenase"


@pytest.mark.asyncio
async def test_organism_enzyme_unique_pair(db_session: AsyncSession) -> None:
    yeast = Organism(name="Saccharomyces cerevisiae", kingdom="yeast", source_version="v1")
    adh = Enzyme(ec_number="1.1.1.1", name="alcohol dehydrogenase", source_version="v1")
    db_session.add_all([yeast, adh])
    await db_session.flush()
    db_session.add(OrganismEnzyme(organism_id=yeast.id, enzyme_id=adh.id))
    await db_session.commit()

    db_session.add(OrganismEnzyme(organism_id=yeast.id, enzyme_id=adh.id))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_batch_organism_override_and_cascade_delete(db_session: AsyncSession) -> None:
    culture = Culture(name="Jun SCOBY", type="kombucha")
    yeast = Organism(name="Saccharomyces cerevisiae", kingdom="yeast", source_version="v1")
    db_session.add_all([culture, yeast])
    await db_session.flush()

    batch = Batch(culture_id=culture.id, current_stage="brew_sweet_tea")
    db_session.add(batch)
    await db_session.flush()

    db_session.add(
        BatchOrganism(
            batch_id=batch.id, organism_id=yeast.id,
            source="custom", notes="Fermentis SafAle US-05",
        )
    )
    await db_session.commit()

    await db_session.delete(batch)
    await db_session.commit()

    result = await db_session.execute(select(BatchOrganism))
    assert result.scalars().all() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_biochemistry_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'Organism' from 'fermenttrack.models'`

- [ ] **Step 3: Add the models**

In `src/fermenttrack/models.py`, after the existing `FdcFoodNutrient` class, add:

```python
class Organism(Base):
    __tablename__ = "organisms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kingdom: Mapped[str] = mapped_column(Text, nullable=False)  # bacteria | yeast | mold
    ncbi_taxon_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    kegg_organism_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_version: Mapped[str] = mapped_column(Text, nullable=False)


class Enzyme(Base):
    __tablename__ = "enzymes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ec_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kegg_entry_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_version: Mapped[str] = mapped_column(Text, nullable=False)


class Compound(Base):
    __tablename__ = "compounds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    kegg_compound_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)  # acid|alcohol|gas|flavor|other
    source_version: Mapped[str] = mapped_column(Text, nullable=False)


class OrganismEnzyme(Base):
    """'This organism expresses this enzyme' — hand-curated, see biochem.py."""

    __tablename__ = "organism_enzymes"
    __table_args__ = (UniqueConstraint("organism_id", "enzyme_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisms.id"), nullable=False
    )
    enzyme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enzymes.id"), nullable=False
    )

    enzyme: Mapped["Enzyme"] = relationship()


class EnzymeReaction(Base):
    """'This enzyme converts substrate to product' (one representative
    reaction per curated enzyme, not full pathway completeness)."""

    __tablename__ = "enzyme_reactions"
    __table_args__ = (UniqueConstraint("enzyme_id", "substrate_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    enzyme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enzymes.id"), nullable=False
    )
    substrate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compounds.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compounds.id"), nullable=False
    )

    substrate: Mapped["Compound"] = relationship(foreign_keys=[substrate_id])
    product: Mapped["Compound"] = relationship(foreign_keys=[product_id])


class FermentationTypeOrganism(Base):
    """Default organisms per fermentation_type (the STAGE_MACHINES vocabulary
    plus kefir/vinegar) — hand-curated, see biochem.py."""

    __tablename__ = "fermentation_type_organisms"
    __table_args__ = (UniqueConstraint("fermentation_type", "organism_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    fermentation_type: Mapped[str] = mapped_column(Text, nullable=False)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisms.id"), nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organism: Mapped["Organism"] = relationship()


class BatchOrganism(Base):
    """A row here overrides/extends its batch's organism set for the
    /biochemistry endpoint; a batch with zero rows uses
    FermentationTypeOrganism defaults for its culture.type instead."""

    __tablename__ = "batch_organisms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False
    )
    organism_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisms.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, default="custom")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)

    batch: Mapped["Batch"] = relationship(back_populates="batch_organisms")
    organism: Mapped["Organism"] = relationship()
```

Then add to the `Batch` class (after the existing `batch_ingredients` relationship):

```python
    batch_organisms: Mapped[list["BatchOrganism"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_biochemistry_model.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fermenttrack/models.py tests/test_biochemistry_model.py
git commit -m "feat: add organism/enzyme/compound/batch_organism models"
```

---

### Task 2: `biochem.py` — curated data + pure KEGG parsing + snapshot build

**Files:**
- Create: `src/fermenttrack/biochem.py`
- Test: `tests/test_biochem_build.py`

**Interfaces:**
- Consumes: `fermenttrack.stages.STAGE_MACHINES` (for `KNOWN_FERMENTATION_TYPES`)
- Produces: `KEGG_BIOCHEM_V1: Path`, `ORGANISMS: dict[str, str]`, `FERMENTATION_TYPE_ORGANISMS: dict[str, list[str]]`, `ENZYME_ORGANISMS: dict[str, list[str]]`, `COMPOUNDS: dict[str, str]`, `ENZYME_REACTIONS: dict[str, tuple[str, str]]`, `parse_kegg_flatfile(text: str) -> dict[str, list[str]]`, `kegg_entry_name(text: str) -> str`, `kegg_find_first_id(text: str) -> str`, `build_snapshot(enzyme_names: dict[str, str], compound_lookup: dict[str, tuple[str, str]]) -> dict`, `write_snapshot(data: dict, path: Path = KEGG_BIOCHEM_V1) -> None`, `load_snapshot(path: Path = KEGG_BIOCHEM_V1) -> dict`, `snapshot_seed_rows(data: dict) -> dict[str, list[dict]]` (used by Task 4's migration and Task 3's script)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_biochem_build.py
"""Pure checks on KEGG flat-file/TSV parsing and snapshot assembly. No network, no DB."""

from __future__ import annotations

from pathlib import Path

import pytest

from fermenttrack.biochem import (
    COMPOUNDS,
    ENZYME_ORGANISMS,
    build_snapshot,
    kegg_entry_name,
    kegg_find_first_id,
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


def test_kegg_find_first_id() -> None:
    assert kegg_find_first_id(FIND_RESPONSE) == "C00469"


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_biochem_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'fermenttrack.biochem'`

- [ ] **Step 3: Write `src/fermenttrack/biochem.py`**

```python
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
}

# Hand-curated: fermentation_type -> default organisms (dominant, not exhaustive).
FERMENTATION_TYPE_ORGANISMS: dict[str, list[str]] = {
    "kombucha": ["Saccharomyces cerevisiae", "Acetobacter aceti"],
    "sourdough": ["Saccharomyces cerevisiae", "Lactobacillus plantarum"],
    "koji": ["Aspergillus oryzae"],
    "cheese": ["Lactococcus lactis"],
    "kefir": ["Saccharomyces cerevisiae", "Lactobacillus plantarum"],
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
    "1.1.1.27": ["Lactobacillus plantarum", "Lactococcus lactis"],  # L-lactate dehydrogenase
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
# one representative fermentation-relevant reaction per enzyme (not full
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
    return fields["NAME"][0].rstrip(";")


def kegg_find_first_id(text: str) -> str:
    """First hit's bare id from a KEGG 'find' TSV response.

    e.g. 'cpd:C00469\\tEthanol; Ethyl alcohol\\n' -> 'C00469'
    """
    first_line = text.splitlines()[0]
    raw_id = first_line.split("\t", 1)[0]
    return raw_id.split(":", 1)[1]


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_biochem_build.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fermenttrack/biochem.py tests/test_biochem_build.py
git commit -m "feat: add curated fermentation biochemistry data and KEGG snapshot builder"
```

---

### Task 3: KEGG fetch script + produce the real frozen snapshot

**Files:**
- Create: `scripts/build_kegg_biochem.py`

**Interfaces:**
- Consumes: `fermenttrack.biochem.{COMPOUNDS, ENZYME_ORGANISMS, KEGG_BIOCHEM_V1, build_snapshot, kegg_entry_name, kegg_find_first_id, write_snapshot}` (Task 2)
- Produces: `src/fermenttrack/kegg_biochem_v1.json.gz` (committed binary, consumed by Task 4's migration)

This task has no unit test of its own (it's a thin CLI wrapper around Task 2's already-tested pure functions, exactly like `scripts/build_fdc_catalog.py` has none) — it's verified by actually running it.

- [ ] **Step 1: Write the script**

```python
# scripts/build_kegg_biochem.py
"""Build the frozen KEGG fermentation-biochemistry snapshot.

    python scripts/build_kegg_biochem.py [--force]

Calls KEGG's public REST API (https://rest.kegg.jp, no key needed) to fetch
canonical enzyme names (by EC number) and compound IDs/names (by search
term). Which organisms/enzymes/compounds are fermentation-relevant, and how
they link together, is hand-curated domain knowledge in
fermenttrack/biochem.py — KEGG supplies identity, not the curation itself.

Writes src/fermenttrack/kegg_biochem_v1.json.gz — FROZEN once migration 0008
has run anywhere: a new snapshot is _v2 + a new migration.
"""

from __future__ import annotations

import argparse

import httpx

from fermenttrack.biochem import (
    COMPOUNDS,
    ENZYME_ORGANISMS,
    KEGG_BIOCHEM_V1,
    build_snapshot,
    kegg_entry_name,
    kegg_find_first_id,
    write_snapshot,
)

KEGG_BASE = "https://rest.kegg.jp"


def fetch_enzyme_names(client: httpx.Client) -> dict[str, str]:
    names = {}
    for ec in ENZYME_ORGANISMS:
        resp = client.get(f"{KEGG_BASE}/get/ec:{ec}")
        resp.raise_for_status()
        names[ec] = kegg_entry_name(resp.text)
    return names


def fetch_compound_lookup(client: httpx.Client) -> dict[str, tuple[str, str]]:
    lookup = {}
    for name in COMPOUNDS:
        found = client.get(f"{KEGG_BASE}/find/compound/{name}")
        found.raise_for_status()
        kegg_id = kegg_find_first_id(found.text)
        entry = client.get(f"{KEGG_BASE}/get/cpd:{kegg_id}")
        entry.raise_for_status()
        lookup[name] = (kegg_id, kegg_entry_name(entry.text))
    return lookup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if KEGG_BIOCHEM_V1.exists() and not args.force:
        raise SystemExit(
            "kegg_biochem_v1.json.gz is frozen; a new snapshot is _v2 + a new "
            "migration (use --force only to regenerate v1 before it has ever "
            "been migrated)"
        )

    with httpx.Client(timeout=30.0) as client:
        enzyme_names = fetch_enzyme_names(client)
        compound_lookup = fetch_compound_lookup(client)

    data = build_snapshot(enzyme_names, compound_lookup)
    write_snapshot(data)
    print(
        f"wrote {len(data['organisms'])} organisms, {len(data['enzymes'])} enzymes, "
        f"{len(data['compounds'])} compounds to {KEGG_BIOCHEM_V1}"
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it against the live KEGG API**

Run: `python scripts/build_kegg_biochem.py`

This makes real HTTP calls (public, no key, no data sent — see spec's "Outbound calls"). If any enzyme/compound name in `biochem.py`'s curated dicts doesn't resolve the way expected (KEGG's `/find/compound/<name>` returns a different top hit, or a flat-file field is shaped differently than `parse_kegg_flatfile` assumes), inspect the actual response (`httpx.get(...).text`) and adjust the curated name or parsing accordingly — this is the one step in the plan that depends on live external data, so treat a mismatch as new information, not a bug to silently work around.

Expected: prints `wrote 6 organisms, 5 enzymes, 5 compounds to .../kegg_biochem_v1.json.gz` and the file exists.

- [ ] **Step 3: Sanity-check the output**

Run: `python -c "from fermenttrack.biochem import load_snapshot; import json; print(json.dumps(load_snapshot(), indent=2))"`

Confirm by eye: every organism/enzyme/compound name looks right, every `enzyme_reactions` substrate/product pair matches `ENZYME_REACTIONS` in `biochem.py`, and no KEGG id looks like an obvious mismatch (e.g. a compound id resolving to an unrelated food additive rather than the intended fermentation metabolite).

- [ ] **Step 4: Commit**

```bash
git add scripts/build_kegg_biochem.py src/fermenttrack/kegg_biochem_v1.json.gz
git commit -m "feat: build frozen KEGG fermentation biochemistry snapshot v1"
```

---

### Task 4: Migration 0008

**Files:**
- Create: `alembic/versions/0008_fermentation_biochemistry.py`

**Interfaces:**
- Consumes: `fermenttrack.biochem.{KEGG_BIOCHEM_V1, load_snapshot, snapshot_seed_rows}` (Tasks 2–3), `src/fermenttrack/kegg_biochem_v1.json.gz` (Task 3)

- [ ] **Step 1: Write the migration**

```python
# alembic/versions/0008_fermentation_biochemistry.py
"""organisms/enzymes/compounds fermentation biochemistry reference data + batch_organisms override

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op
from fermenttrack.biochem import KEGG_BIOCHEM_V1, load_snapshot, snapshot_seed_rows

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    organisms_t = op.create_table(
        "organisms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kingdom", sa.Text(), nullable=False),
        sa.Column("ncbi_taxon_id", sa.Text(), nullable=True),
        sa.Column("kegg_organism_code", sa.Text(), nullable=True),
        sa.Column("source_version", sa.Text(), nullable=False),
    )
    enzymes_t = op.create_table(
        "enzymes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ec_number", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kegg_entry_id", sa.Text(), nullable=True),
        sa.Column("source_version", sa.Text(), nullable=False),
    )
    compounds_t = op.create_table(
        "compounds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kegg_compound_id", sa.Text(), nullable=True, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
    )
    organism_enzymes_t = op.create_table(
        "organism_enzymes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organism_id", UUID(as_uuid=True), sa.ForeignKey("organisms.id"), nullable=False),
        sa.Column("enzyme_id", UUID(as_uuid=True), sa.ForeignKey("enzymes.id"), nullable=False),
        sa.UniqueConstraint("organism_id", "enzyme_id"),
    )
    enzyme_reactions_t = op.create_table(
        "enzyme_reactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("enzyme_id", UUID(as_uuid=True), sa.ForeignKey("enzymes.id"), nullable=False),
        sa.Column("substrate_id", UUID(as_uuid=True), sa.ForeignKey("compounds.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("compounds.id"), nullable=False),
        sa.UniqueConstraint("enzyme_id", "substrate_id", "product_id"),
    )
    fermentation_type_organisms_t = op.create_table(
        "fermentation_type_organisms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fermentation_type", sa.Text(), nullable=False),
        sa.Column("organism_id", UUID(as_uuid=True), sa.ForeignKey("organisms.id"), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("fermentation_type", "organism_id"),
    )
    op.create_table(
        "batch_organisms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("organism_id", UUID(as_uuid=True), sa.ForeignKey("organisms.id"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="custom"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # KEGG_BIOCHEM_V1 is frozen, so this migration stays a faithful record of what it inserted.
    seed = snapshot_seed_rows(load_snapshot(KEGG_BIOCHEM_V1))
    op.bulk_insert(organisms_t, seed["organisms"])
    op.bulk_insert(enzymes_t, seed["enzymes"])
    op.bulk_insert(compounds_t, seed["compounds"])
    op.bulk_insert(organism_enzymes_t, seed["organism_enzymes"])
    op.bulk_insert(enzyme_reactions_t, seed["enzyme_reactions"])
    op.bulk_insert(fermentation_type_organisms_t, seed["fermentation_type_organisms"])


def downgrade() -> None:
    op.drop_table("batch_organisms")
    op.drop_table("fermentation_type_organisms")
    op.drop_table("enzyme_reactions")
    op.drop_table("organism_enzymes")
    op.drop_table("compounds")
    op.drop_table("enzymes")
    op.drop_table("organisms")
```

- [ ] **Step 2: SQLite round-trip**

Run, in order:
```bash
alembic upgrade head
alembic downgrade 0007
alembic upgrade head
```
Expected: all three succeed with no errors (matches the pattern already used for migrations 0006/0007 — no dedicated pytest file for this; it's a manual, documented check).

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/0008_fermentation_biochemistry.py
git commit -m "feat: add migration 0008 for fermentation biochemistry tables"
```

*(A Postgres check through the deployed API after the Render deploy — same pattern as migrations 0006/0007 — happens once this branch ships; Docker remains unavailable locally per existing project notes.)*

---

### Task 5: Pydantic schemas

**Files:**
- Modify: `src/fermenttrack/schemas.py`

**Interfaces:**
- Produces: `OrganismOut`, `EnzymeOut`, `CompoundOut`, `BiochemOrganismOut`, `BatchBiochemistryOut`, `BatchOrganismCreate`, `BatchOrganismOut` (consumed by Tasks 6–7)

- [ ] **Step 1: Add the schemas**

At the end of `src/fermenttrack/schemas.py`, before the final `CultureWithBatches.model_rebuild()` line, add:

```python
# ── Biochemistry ─────────────────────────────────────────────────────────
# Reference data for fermentation organisms/enzymes/compounds, sourced from
# KEGG. See docs/superpowers/specs/2026-09-23-fermentation-biochemistry-
# design.md — this reverses the 2026-09-18 UI deferral for compound/
# microbial data (that deferral was about presenting fermentgraph's
# unvalidated heuristic priors as intelligence; KEGG is a different,
# citable provenance). fermentgraph itself remains a "don't use yet"
# dependency per docs/DEPENDENCIES.md, untouched by this reversal.

class OrganismOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kingdom: str
    ncbi_taxon_id: str | None
    kegg_organism_code: str | None


class EnzymeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ec_number: str
    name: str


class CompoundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str


class BiochemOrganismOut(BaseModel):
    id: uuid.UUID
    name: str
    kingdom: str
    source: str  # "default" | "custom"


class BatchBiochemistryOut(BaseModel):
    organisms: list[BiochemOrganismOut]
    enzymes: list[EnzymeOut]
    compounds: list[CompoundOut]


class BatchOrganismCreate(BaseModel):
    organism_id: uuid.UUID
    notes: str | None = None


class BatchOrganismOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    organism_id: uuid.UUID
    source: str
    notes: str | None
```

Also fix the now-stale comment above `BatchPreview` (it says compound/microbial data is deferred outright — it's now built, just not folded into `preview`). Replace:

```python
# ── Preview ──────────────────────────────────────────────────────────────
# Presentation-shaped for the (future) batch-preview UI page. Scope ceiling:
# owned by that one page's needs — any other consumer uses /timeline and
# /safety directly rather than extending this. No compound/microbial data
# here by design (see docs/superpowers/specs/2026-09-18-experiment-logging-
# design.md § 2 — deferred until FermentGraph's ranker clears its promotion
# bar, to avoid presenting unvalidated heuristics as a current feature).
```

with:

```python
# ── Preview ──────────────────────────────────────────────────────────────
# Presentation-shaped for the (future) batch-preview UI page. Scope ceiling:
# owned by that one page's needs — any other consumer uses /timeline,
# /safety, and /biochemistry directly rather than extending this. No
# organism/enzyme/compound data here: that's GET /batches/{id}/biochemistry
# (docs/superpowers/specs/2026-09-23-fermentation-biochemistry-design.md),
# a separate endpoint, not folded into this one — same scope-ceiling
# reasoning as /timeline and /safety already getting their own endpoints.
```

- [ ] **Step 2: Verify the module still imports cleanly**

Run: `python -c "import fermenttrack.schemas"`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add src/fermenttrack/schemas.py
git commit -m "feat: add biochemistry Pydantic schemas"
```

---

### Task 6: `GET /organisms?q=` search endpoint

**Files:**
- Create: `src/fermenttrack/routers/organisms.py`
- Modify: `src/fermenttrack/main.py`
- Test: `tests/test_organisms.py`

**Interfaces:**
- Consumes: `Organism` (Task 1), `OrganismOut` (Task 5)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_organisms.py
from __future__ import annotations

import pytest
from httpx import AsyncClient

from fermenttrack.models import Organism
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_search_matches_case_insensitive_substring(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            Organism(name="Saccharomyces cerevisiae", kingdom="yeast", source_version="v1"),
            Organism(name="Acetobacter aceti", kingdom="bacteria", source_version="v1"),
        ]
    )
    await db_session.commit()

    resp = await client.get("/organisms", params={"q": "cerevisiae"})
    assert resp.status_code == 200
    names = [o["name"] for o in resp.json()]
    assert names == ["Saccharomyces cerevisiae"]


@pytest.mark.asyncio
async def test_search_requires_min_length(client: AsyncClient) -> None:
    resp = await client.get("/organisms", params={"q": "a"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_organisms.py -v`
Expected: FAIL with 404 (no `/organisms` route registered yet)

- [ ] **Step 3: Write the router and register it**

```python
# src/fermenttrack/routers/organisms.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.database import get_db
from fermenttrack.models import Organism
from fermenttrack.schemas import OrganismOut

router = APIRouter(prefix="/organisms", tags=["organisms"])


@router.get("", response_model=list[OrganismOut])
async def search_organisms(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
) -> list[Organism]:
    stmt = (
        select(Organism)
        .where(func.lower(Organism.name).like(f"%{q.lower()}%"))
        .order_by(func.length(Organism.name), Organism.name)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
```

In `src/fermenttrack/main.py`, change the import line to:

```python
from fermenttrack.routers import batches, cultures, ingredients, organisms, reminders, safety, webhooks
```

and add, alongside the other `include_router` calls:

```python
app.include_router(organisms.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_organisms.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/fermenttrack/routers/organisms.py src/fermenttrack/main.py tests/test_organisms.py
git commit -m "feat: add GET /organisms search endpoint"
```

---

### Task 7: `GET /batches/{id}/biochemistry` and `POST /batches/{id}/organisms`

**Files:**
- Modify: `src/fermenttrack/routers/batches.py`
- Test: `tests/test_batch_biochemistry.py`

**Interfaces:**
- Consumes: `Organism, Enzyme, Compound, OrganismEnzyme, EnzymeReaction, FermentationTypeOrganism, BatchOrganism` (Task 1); `BatchBiochemistryOut, BiochemOrganismOut, EnzymeOut, CompoundOut, BatchOrganismCreate, BatchOrganismOut` (Task 5); `_get_batch` (already in `batches.py`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_batch_biochemistry.py
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import (
    Compound,
    Culture,
    Enzyme,
    EnzymeReaction,
    FermentationTypeOrganism,
    Organism,
    OrganismEnzyme,
)


async def _seed_kombucha_biochem(db_session: AsyncSession) -> Organism:
    yeast = Organism(name="Saccharomyces cerevisiae", kingdom="yeast", source_version="v1")
    acetobacter = Organism(name="Acetobacter aceti", kingdom="bacteria", source_version="v1")
    adh = Enzyme(ec_number="1.1.1.1", name="alcohol dehydrogenase", source_version="v1")
    acetaldehyde = Compound(name="Acetaldehyde", category="other", source_version="v1")
    ethanol = Compound(name="Ethanol", category="alcohol", source_version="v1")
    db_session.add_all([yeast, acetobacter, adh, acetaldehyde, ethanol])
    await db_session.flush()

    db_session.add(OrganismEnzyme(organism_id=yeast.id, enzyme_id=adh.id))
    db_session.add(
        EnzymeReaction(enzyme_id=adh.id, substrate_id=acetaldehyde.id, product_id=ethanol.id)
    )
    db_session.add(FermentationTypeOrganism(fermentation_type="kombucha", organism_id=yeast.id))
    db_session.add(
        FermentationTypeOrganism(fermentation_type="kombucha", organism_id=acetobacter.id)
    )
    await db_session.commit()
    return yeast


@pytest.mark.asyncio
async def test_biochemistry_defaults_to_fermentation_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_kombucha_biochem(db_session)
    culture = Culture(name="Jun SCOBY", type="kombucha")
    db_session.add(culture)
    await db_session.commit()

    resp = await client.post("/batches", json={"culture_id": str(culture.id)})
    batch_id = resp.json()["id"]

    resp = await client.get(f"/batches/{batch_id}/biochemistry")
    assert resp.status_code == 200
    body = resp.json()
    names = {(o["name"], o["source"]) for o in body["organisms"]}
    assert names == {
        ("Saccharomyces cerevisiae", "default"),
        ("Acetobacter aceti", "default"),
    }
    assert {e["ec_number"] for e in body["enzymes"]} == {"1.1.1.1"}
    assert {c["name"] for c in body["compounds"]} == {"Acetaldehyde", "Ethanol"}


@pytest.mark.asyncio
async def test_batch_organism_override_replaces_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    yeast = await _seed_kombucha_biochem(db_session)
    culture = Culture(name="Jun SCOBY", type="kombucha")
    db_session.add(culture)
    await db_session.commit()

    resp = await client.post("/batches", json={"culture_id": str(culture.id)})
    batch_id = resp.json()["id"]

    resp = await client.post(
        f"/batches/{batch_id}/organisms",
        json={"organism_id": str(yeast.id), "notes": "Fermentis SafAle US-05"},
    )
    assert resp.status_code == 201
    assert resp.json()["source"] == "custom"

    resp = await client.get(f"/batches/{batch_id}/biochemistry")
    names = {(o["name"], o["source"]) for o in resp.json()["organisms"]}
    assert names == {("Saccharomyces cerevisiae", "custom")}  # Acetobacter dropped, override wins


@pytest.mark.asyncio
async def test_add_batch_organism_404_for_unknown_organism(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    culture = Culture(name="Jun SCOBY", type="kombucha")
    db_session.add(culture)
    await db_session.commit()
    resp = await client.post("/batches", json={"culture_id": str(culture.id)})
    batch_id = resp.json()["id"]

    resp = await client.post(
        f"/batches/{batch_id}/organisms",
        json={"organism_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_batch_biochemistry.py -v`
Expected: FAIL with 404 (routes don't exist yet)

- [ ] **Step 3: Add the resolution helper and both endpoints**

In `src/fermenttrack/routers/batches.py`, add to the imports:

```python
from fermenttrack.models import (
    Batch,
    BatchIngredient,
    BatchOrganism,
    Compound,
    Culture,
    Enzyme,
    EnzymeReaction,
    FermentationTypeOrganism,
    Ingredient,
    Measurement,
    Organism,
    OrganismEnzyme,
    Reminder,
)
from fermenttrack.schemas import (
    BatchBiochemistryOut,
    BatchCompare,
    BatchCompositionOut,
    BatchCreate,
    BatchIngredientCreate,
    BatchIngredientOut,
    BatchOrganismCreate,
    BatchOrganismOut,
    BatchOut,
    BatchPreview,
    BatchTimeline,
    BiochemOrganismOut,
    CompoundOut,
    CultureOut,
    EnzymeOut,
    MeasurementCreate,
    MeasurementOut,
    NoteCreate,
    NutrientTotalOut,
    RuleVerdictOut,
    SafetyReportOut,
    SaltSuggestionOut,
    StageAdvance,
    TimelineEvent,
)
```

Then add, near the bottom of the file (after `get_batch_composition`):

```python
async def _resolve_batch_organisms(batch: Batch, db: AsyncSession) -> list[tuple[Organism, str]]:
    result = await db.execute(
        select(BatchOrganism)
        .where(BatchOrganism.batch_id == batch.id)
        .options(selectinload(BatchOrganism.organism))
    )
    overrides = list(result.scalars().all())
    if overrides:
        return [(bo.organism, bo.source) for bo in overrides]

    result = await db.execute(
        select(FermentationTypeOrganism)
        .where(
            FermentationTypeOrganism.fermentation_type == batch.culture.type,
            FermentationTypeOrganism.is_default.is_(True),
        )
        .options(selectinload(FermentationTypeOrganism.organism))
    )
    defaults = list(result.scalars().all())
    return [(fo.organism, "default") for fo in defaults]


@router.get("/{batch_id}/biochemistry", response_model=BatchBiochemistryOut)
async def get_batch_biochemistry(
    batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> BatchBiochemistryOut:
    batch = await _get_batch(batch_id, db, with_culture=True)
    organisms = await _resolve_batch_organisms(batch, db)
    organism_ids = [o.id for o, _ in organisms]

    result = await db.execute(
        select(OrganismEnzyme)
        .where(OrganismEnzyme.organism_id.in_(organism_ids))
        .options(selectinload(OrganismEnzyme.enzyme))
    )
    enzymes = {oe.enzyme.id: oe.enzyme for oe in result.scalars().all()}

    compounds: dict[uuid.UUID, Compound] = {}
    if enzymes:
        result = await db.execute(
            select(EnzymeReaction)
            .where(EnzymeReaction.enzyme_id.in_(enzymes))
            .options(
                selectinload(EnzymeReaction.substrate), selectinload(EnzymeReaction.product)
            )
        )
        for er in result.scalars().all():
            compounds[er.substrate.id] = er.substrate
            compounds[er.product.id] = er.product

    return BatchBiochemistryOut(
        organisms=[
            BiochemOrganismOut(id=o.id, name=o.name, kingdom=o.kingdom, source=source)
            for o, source in organisms
        ],
        enzymes=[EnzymeOut.model_validate(e) for e in enzymes.values()],
        compounds=[CompoundOut.model_validate(c) for c in compounds.values()],
    )


@router.post("/{batch_id}/organisms", response_model=BatchOrganismOut, status_code=201)
async def add_batch_organism(
    batch_id: uuid.UUID, payload: BatchOrganismCreate, db: AsyncSession = Depends(get_db)
) -> BatchOrganism:
    batch = await _get_batch(batch_id, db)
    organism = await db.get(Organism, payload.organism_id)
    if organism is None:
        raise HTTPException(status_code=404, detail="Organism not found")

    batch_organism = BatchOrganism(
        batch_id=batch.id, organism_id=organism.id, notes=payload.notes
    )
    db.add(batch_organism)
    await db.commit()
    await db.refresh(batch_organism)
    return batch_organism
```

Note `OrganismEnzyme.enzyme_id.in_(enzymes)` uses the dict `enzymes` directly as the iterable of keys — equivalent to `.in_(enzymes.keys())`, just relying on dict iteration yielding keys.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_batch_biochemistry.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass, including Tasks 1–6's new tests and every pre-existing test (no regressions).

- [ ] **Step 6: Commit**

```bash
git add src/fermenttrack/routers/batches.py tests/test_batch_biochemistry.py
git commit -m "feat: add batch biochemistry read endpoint and organism override"
```

---

### Task 8: Documentation reversal (STRATEGY.md, DEPENDENCIES.md, fermentgraph-evolution.md)

**Files:**
- Modify: `docs/STRATEGY.md`
- Modify: `docs/DEPENDENCIES.md`
- Modify: `docs/specs/fermentgraph-evolution.md`

No test — these are prose edits. Verified by re-reading the changed sections after editing.

- [ ] **Step 1: `docs/STRATEGY.md`**

Find the line (around line 121):
```
## Direction 3: 🧠 Knowledge-Powered Intelligence (The FermentGraph Moat) — DEFERRED, corrected 2026-09-17
```
Change it to:
```
## Direction 3: 🧠 Knowledge-Powered Intelligence (The FermentGraph Moat) — DEFERRED, corrected 2026-09-17; partially superseded 2026-09-23

**2026-09-23 update:** the UI-deferral below no longer blocks a KEGG-sourced organism/enzyme/compound reference layer — see `docs/superpowers/specs/2026-09-23-fermentation-biochemistry-design.md` § "Reversing the Direction 3 deferral". The original objection was about *sourcing* (presenting fermentgraph's unvalidated, null-result heuristic priors as intelligence); KEGG is a different, citable provenance. **The rest of this Direction — anything sourced from `fermentgraph` specifically — stays deferred on its original trigger** (ranker beats popularity baseline by ≥+0.05 Recall@50, `docs/DEPENDENCIES.md`).
```

- [ ] **Step 2: `docs/DEPENDENCIES.md`**

Find the line (around line 36) that starts:
```
## 2. `fermentgraph` — DON'T USE YET
```
Add, immediately after that heading line (before the "**Reality.**" paragraph):
```

**2026-09-23 note:** this verdict is unchanged. A separate reference layer (organisms/enzymes/compounds keyed by fermentation type) was added sourced from KEGG instead of fermentgraph — see `docs/superpowers/specs/2026-09-23-fermentation-biochemistry-design.md`. That spec does not depend on this repo at all; it reverses only `STRATEGY.md` Direction 3's UI-deferral condition, not this dependency verdict.
```

- [ ] **Step 3: `docs/specs/fermentgraph-evolution.md`**

Find the line (around line 8) that starts:
```
## Requirement added 2026-09-18, then DEFERRED same day after review — do not start this yet
```
Add, immediately after that heading line (before the "FermentTrack considered building..." paragraph):
```

**2026-09-23 update:** FermentTrack built a KEGG-sourced organism/enzyme/compound reference layer instead of waiting on this trigger — see `FermentTrack/docs/superpowers/specs/2026-09-23-fermentation-biochemistry-design.md`. This export is still deferred on the trigger below; if it ever fires, its `associated_microbes`/`associated_compounds` could reconcile against FermentTrack's tables via a future `canonical_id`, mirroring how `Ingredient.canonical_id` already works — not required for FermentTrack to have this feature today.
```

- [ ] **Step 4: Re-read all three changed sections to confirm they read correctly and don't contradict each other**

Run: none (manual read)

- [ ] **Step 5: Commit**

```bash
git add docs/STRATEGY.md docs/DEPENDENCIES.md docs/specs/fermentgraph-evolution.md
git commit -m "docs: record Direction 3 reversal for KEGG-sourced biochemistry data"
```

---

## Self-Review Notes

- **Spec coverage:** data model (Task 1), KEGG ingestion (Tasks 2–3), migration (Task 4), read endpoint (Task 7), custom organism override (Tasks 6–7), documentation reversal (Task 8) — every spec section has a task. Frontend UI is explicitly out of scope per the spec and not in this plan.
- **Placeholder scan:** clean — no TBD/TODO markers, no "similar to Task N" references, every code block is complete and runnable as written.
- **Type consistency:** `BatchOrganism.source` default `"custom"` (model, Task 1) matches the router always setting overrides via the POST endpoint (Task 7) and the response tagging defaults as `"default"` at read time (Task 7) — no code path ever writes `source="default"` to the table itself, consistent with the spec's resolution rule.
- **Deviation from spec flagged in Global Constraints:** organism↔enzyme linkage is hand-curated rather than derived from KEGG ortholog data, to avoid a fragile per-genome API pipeline. Data quality and spec intent (KEGG for identity, curation for fermentation-domain linkage) are preserved.
