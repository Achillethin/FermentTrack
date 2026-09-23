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


@pytest.mark.asyncio
async def test_biochemistry_404_for_unknown_batch(client: AsyncClient) -> None:
    resp = await client.get("/batches/00000000-0000-0000-0000-000000000000/biochemistry")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_biochemistry_empty_when_type_has_no_defaults(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    culture = Culture(name="Jun SCOBY", type="kombucha")
    db_session.add(culture)
    await db_session.commit()
    resp = await client.post("/batches", json={"culture_id": str(culture.id)})
    batch_id = resp.json()["id"]

    resp = await client.get(f"/batches/{batch_id}/biochemistry")
    assert resp.status_code == 200
    assert resp.json() == {"organisms": [], "enzymes": [], "compounds": []}


@pytest.mark.asyncio
async def test_add_batch_organism_duplicate_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    yeast = await _seed_kombucha_biochem(db_session)
    culture = Culture(name="Jun SCOBY", type="kombucha")
    db_session.add(culture)
    await db_session.commit()
    batch_id = (await client.post("/batches", json={"culture_id": str(culture.id)})).json()["id"]

    body = {"organism_id": str(yeast.id)}
    assert (await client.post(f"/batches/{batch_id}/organisms", json=body)).status_code == 201
    resp = await client.post(f"/batches/{batch_id}/organisms", json=body)
    assert resp.status_code == 409

    resp = await client.get(f"/batches/{batch_id}/biochemistry")
    assert [o["id"] for o in resp.json()["organisms"]] == [str(yeast.id)]


@pytest.mark.asyncio
async def test_same_organism_can_attach_to_different_batch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    yeast = await _seed_kombucha_biochem(db_session)
    culture = Culture(name="Jun SCOBY", type="kombucha")
    db_session.add(culture)
    await db_session.commit()
    body = {"organism_id": str(yeast.id)}
    for _ in range(2):
        batch_id = (await client.post("/batches", json={"culture_id": str(culture.id)})).json()[
            "id"
        ]
        resp = await client.post(f"/batches/{batch_id}/organisms", json=body)
        assert resp.status_code == 201


@pytest.mark.asyncio
async def test_add_batch_organism_404_for_unknown_batch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    yeast = await _seed_kombucha_biochem(db_session)
    resp = await client.post(
        "/batches/00000000-0000-0000-0000-000000000000/organisms",
        json={"organism_id": str(yeast.id)},
    )
    assert resp.status_code == 404
