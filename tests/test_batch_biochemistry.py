from __future__ import annotations

from types import SimpleNamespace

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

UNKNOWN = "00000000-0000-0000-0000-000000000000"


async def _seed(db_session: AsyncSession) -> SimpleNamespace:
    """Kombucha defaults: yeast + acetobacter (both carry ADH). Not a default:
    lactobacillus (carries ADH too, plus LDH/amylase/glucosidase that no default has).

    Names/ids are picked so a wrong sort (case-sensitive, lexicographic EC) or a
    non-merged result would fail an assertion.
    """
    yeast = Organism(name="Saccharomyces cerevisiae", kingdom="yeast", source_version="v1")
    aceto = Organism(name="acetobacter aceti", kingdom="bacteria", source_version="v1")
    lacto = Organism(name="Lactobacillus plantarum", kingdom="bacteria", source_version="v1")
    adh = Enzyme(ec_number="1.1.1.1", name="alcohol dehydrogenase", source_version="v1")
    ldh = Enzyme(ec_number="1.1.1.27", name="L-lactate dehydrogenase", source_version="v1")
    amy = Enzyme(ec_number="3.2.1.3", name="glucan 1,4-alpha-glucosidase", source_version="v1")
    glu = Enzyme(ec_number="3.2.1.20", name="alpha-glucosidase", source_version="v1")
    acetaldehyde = Compound(
        name="Acetaldehyde", category="other", kegg_compound_id="C00084", source_version="v1"
    )
    ethanol = Compound(
        name="Ethanol", category="alcohol", kegg_compound_id="C00469", source_version="v1"
    )
    pyruvate = Compound(
        name="Pyruvate", category="other", kegg_compound_id="C00022", source_version="v1"
    )
    lactate = Compound(
        name="L-Lactate", category="acid", kegg_compound_id="C00186", source_version="v1"
    )
    starch = Compound(name="Starch", category="other", kegg_compound_id=None, source_version="v1")
    maltose = Compound(
        name="Maltose", category="other", kegg_compound_id="C00208", source_version="v1"
    )
    glucose = Compound(
        name="d-Glucose", category="other", kegg_compound_id="C00031", source_version="v1"
    )
    db_session.add_all(
        [yeast, aceto, lacto, adh, ldh, amy, glu]
        + [acetaldehyde, ethanol, pyruvate, lactate, starch, maltose, glucose]
    )
    await db_session.flush()

    for org, enzyme in [
        (yeast, adh), (aceto, adh), (lacto, adh), (lacto, ldh), (lacto, amy), (lacto, glu),
    ]:
        db_session.add(OrganismEnzyme(organism_id=org.id, enzyme_id=enzyme.id))
    for enzyme, sub, prod in [
        (adh, acetaldehyde, ethanol),
        (ldh, pyruvate, lactate),
        (amy, starch, maltose),
        (glu, maltose, glucose),
    ]:
        db_session.add(EnzymeReaction(enzyme_id=enzyme.id, substrate_id=sub.id, product_id=prod.id))
    for org in (yeast, aceto):
        db_session.add(FermentationTypeOrganism(fermentation_type="kombucha", organism_id=org.id))
    ids = SimpleNamespace(
        yeast=str(yeast.id), aceto=str(aceto.id), lacto=str(lacto.id),
        adh=str(adh.id), ldh=str(ldh.id),
    )
    await db_session.commit()
    return ids


async def _batch(client: AsyncClient, db_session: AsyncSession, ctype: str = "kombucha") -> str:
    culture = Culture(name=f"{ctype} culture", type=ctype)
    db_session.add(culture)
    await db_session.commit()
    resp = await client.post("/batches", json={"culture_id": str(culture.id)})
    return resp.json()["id"]


async def _bio(client: AsyncClient, batch_id: str) -> dict:
    resp = await client.get(f"/batches/{batch_id}/biochemistry")
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_biochemistry_defaults_to_fermentation_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    body = await _bio(client, await _batch(client, db_session))

    # organisms by name, case-insensitive: "acetobacter" (lowercase) before "Saccharomyces"
    assert [(o["id"], o["source"], o["notes"]) for o in body["organisms"]] == [
        (s.aceto, "default", None),
        (s.yeast, "default", None),
    ]
    assert [o["kingdom"] for o in body["organisms"]] == ["bacteria", "yeast"]
    # both defaults carry ADH; organism_ids sorted by organism name; nothing from lacto
    assert [(e["ec_number"], e["organism_ids"]) for e in body["enzymes"]] == [
        ("1.1.1.1", [s.aceto, s.yeast])
    ]
    assert [c["name"] for c in body["compounds"]] == ["Ethanol", "Acetaldehyde"]


@pytest.mark.asyncio
async def test_custom_organism_is_merged_with_defaults(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    batch_id = await _batch(client, db_session)

    resp = await client.post(f"/batches/{batch_id}/organisms", json={"organism_id": s.lacto})
    assert resp.status_code == 201
    assert resp.json()["source"] == "custom"

    body = await _bio(client, batch_id)
    assert [(o["id"], o["source"]) for o in body["organisms"]] == [
        (s.aceto, "default"),
        (s.lacto, "custom"),
        (s.yeast, "default"),
    ]
    # EC numeric order: 3.2.1.3 before 3.2.1.20; ADH now has all three carriers, by name
    assert [e["ec_number"] for e in body["enzymes"]] == [
        "1.1.1.1", "1.1.1.27", "3.2.1.3", "3.2.1.20",
    ]
    by_ec = {e["ec_number"]: e["organism_ids"] for e in body["enzymes"]}
    assert by_ec["1.1.1.1"] == [s.aceto, s.lacto, s.yeast]
    assert by_ec["1.1.1.27"] == [s.lacto]
    assert by_ec["3.2.1.3"] == [s.lacto] and by_ec["3.2.1.20"] == [s.lacto]
    # (category, name case-insensitive); custom-only compounds present, defaults' remain
    assert [(c["category"], c["name"]) for c in body["compounds"]] == [
        ("acid", "L-Lactate"),
        ("alcohol", "Ethanol"),
        ("other", "Acetaldehyde"),
        ("other", "d-Glucose"),
        ("other", "Maltose"),
        ("other", "Pyruvate"),
        ("other", "Starch"),
    ]
    assert {c["name"]: c["kegg_compound_id"] for c in body["compounds"]} == {
        "L-Lactate": "C00186", "Ethanol": "C00469", "Acetaldehyde": "C00084",
        "d-Glucose": "C00031", "Maltose": "C00208", "Pyruvate": "C00022", "Starch": None,
    }


@pytest.mark.asyncio
async def test_attaching_a_default_organism_shows_once_as_custom_with_notes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    batch_id = await _batch(client, db_session)
    before = await _bio(client, batch_id)

    resp = await client.post(
        f"/batches/{batch_id}/organisms",
        json={"organism_id": s.yeast, "notes": "Fermentis SafAle US-05"},
    )
    assert resp.status_code == 201

    body = await _bio(client, batch_id)
    assert [(o["id"], o["source"], o["notes"]) for o in body["organisms"]] == [
        (s.aceto, "default", None),
        (s.yeast, "custom", "Fermentis SafAle US-05"),
    ]
    assert body["enzymes"] == before["enzymes"]
    assert body["compounds"] == before["compounds"]


@pytest.mark.asyncio
async def test_delete_only_removes_the_custom_attachment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    batch_id = await _batch(client, db_session)
    before = await _bio(client, batch_id)
    await client.post(
        f"/batches/{batch_id}/organisms", json={"organism_id": s.yeast, "notes": "US-05"}
    )

    resp = await client.delete(f"/batches/{batch_id}/organisms/{s.yeast}")
    assert resp.status_code == 204
    assert resp.content == b""
    # yeast reverts to a pure default: source "default", notes None
    assert await _bio(client, batch_id) == before

    # the attachment is gone, so a second DELETE is a 404 (defaults are never deletable)
    resp = await client.delete(f"/batches/{batch_id}/organisms/{s.yeast}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Organism is not attached to this batch"


@pytest.mark.asyncio
async def test_delete_custom_non_default_removes_it_and_exclusive_enzymes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    batch_id = await _batch(client, db_session)
    await client.post(f"/batches/{batch_id}/organisms", json={"organism_id": s.lacto})
    assert len((await _bio(client, batch_id))["enzymes"]) == 4

    assert (await client.delete(f"/batches/{batch_id}/organisms/{s.lacto}")).status_code == 204

    body = await _bio(client, batch_id)
    assert [o["id"] for o in body["organisms"]] == [s.aceto, s.yeast]
    assert [(e["ec_number"], e["organism_ids"]) for e in body["enzymes"]] == [
        ("1.1.1.1", [s.aceto, s.yeast])  # lacto dropped from ADH, its exclusive enzymes gone
    ]
    assert [c["name"] for c in body["compounds"]] == ["Ethanol", "Acetaldehyde"]


@pytest.mark.asyncio
async def test_delete_is_scoped_to_its_batch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    b1 = await _batch(client, db_session)
    b2 = await _batch(client, db_session)
    for b in (b1, b2):
        await client.post(f"/batches/{b}/organisms", json={"organism_id": s.lacto})
    await client.delete(f"/batches/{b1}/organisms/{s.lacto}")
    assert s.lacto not in [o["id"] for o in (await _bio(client, b1))["organisms"]]
    assert s.lacto in [o["id"] for o in (await _bio(client, b2))["organisms"]]


@pytest.mark.asyncio
async def test_notes_are_trimmed_and_blank_becomes_none(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    cases = [
        ("  US-05  ", "US-05"), ("   ", None), ("", None), (None, None), ("x" * 500, "x" * 500),
    ]
    for sent, stored in cases:
        batch_id = await _batch(client, db_session)
        resp = await client.post(
            f"/batches/{batch_id}/organisms", json={"organism_id": s.yeast, "notes": sent}
        )
        assert resp.status_code == 201, sent
        assert resp.json()["notes"] == stored
        yeast_out = next(
            o for o in (await _bio(client, batch_id))["organisms"] if o["id"] == s.yeast
        )
        assert yeast_out["notes"] == stored


@pytest.mark.asyncio
async def test_notes_over_500_chars_is_422(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    batch_id = await _batch(client, db_session)
    resp = await client.post(
        f"/batches/{batch_id}/organisms", json={"organism_id": s.yeast, "notes": "x" * 501}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_attachment_returns_409(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    batch_id = await _batch(client, db_session)

    for organism_id in (s.lacto, s.yeast):  # a non-default and a default organism
        body = {"organism_id": organism_id}
        assert (await client.post(f"/batches/{batch_id}/organisms", json=body)).status_code == 201
        resp = await client.post(f"/batches/{batch_id}/organisms", json=body)
        assert resp.status_code == 409
        assert "already attached" in resp.json()["detail"]

    ids = [o["id"] for o in (await _bio(client, batch_id))["organisms"]]
    assert ids == [s.aceto, s.lacto, s.yeast]  # no duplicates


@pytest.mark.asyncio
async def test_same_organism_can_attach_to_different_batch(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    for _ in range(2):
        batch_id = await _batch(client, db_session)
        resp = await client.post(f"/batches/{batch_id}/organisms", json={"organism_id": s.yeast})
        assert resp.status_code == 201


@pytest.mark.asyncio
async def test_404s(client: AsyncClient, db_session: AsyncSession) -> None:
    s = await _seed(db_session)
    batch_id = await _batch(client, db_session)

    resp = await client.get(f"/batches/{UNKNOWN}/biochemistry")
    assert resp.status_code == 404

    resp = await client.post(f"/batches/{UNKNOWN}/organisms", json={"organism_id": s.yeast})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Batch not found"

    resp = await client.post(f"/batches/{batch_id}/organisms", json={"organism_id": UNKNOWN})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Organism not found"

    resp = await client.delete(f"/batches/{UNKNOWN}/organisms/{s.yeast}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Batch not found"

    # a type default that was never attached is not deletable; nor is an unknown organism
    for organism_id in (s.yeast, s.lacto, UNKNOWN):
        resp = await client.delete(f"/batches/{batch_id}/organisms/{organism_id}")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Organism is not attached to this batch"
    assert len((await _bio(client, batch_id))["organisms"]) == 2  # defaults untouched


@pytest.mark.asyncio
async def test_biochemistry_empty_when_type_has_no_defaults(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    resp = await client.get(f"/batches/{await _batch(client, db_session)}/biochemistry")
    assert resp.status_code == 200
    assert resp.json() == {"organisms": [], "enzymes": [], "compounds": []}


@pytest.mark.asyncio
async def test_type_without_defaults_plus_one_custom_shows_just_that_organism(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    s = await _seed(db_session)
    batch_id = await _batch(client, db_session, ctype="sourdough")  # no defaults seeded
    await client.post(
        f"/batches/{batch_id}/organisms", json={"organism_id": s.lacto, "notes": "starter"}
    )

    body = await _bio(client, batch_id)
    assert [(o["id"], o["source"], o["notes"]) for o in body["organisms"]] == [
        (s.lacto, "custom", "starter")
    ]
    assert [e["ec_number"] for e in body["enzymes"]] == [
        "1.1.1.1", "1.1.1.27", "3.2.1.3", "3.2.1.20",
    ]
    assert all(e["organism_ids"] == [s.lacto] for e in body["enzymes"])
