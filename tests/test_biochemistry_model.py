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


@pytest.mark.asyncio
async def test_organism_name_is_unique(db_session: AsyncSession) -> None:
    db_session.add(Organism(name="Aspergillus oryzae", kingdom="mold", source_version="v1"))
    await db_session.commit()
    db_session.add(Organism(name="Aspergillus oryzae", kingdom="mold", source_version="v1"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
