"""GET /batches/{id}/prediction over HTTP, with the batch's recipe, organisms and readings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from fermenttrack.models import (
    Batch,
    Culture,
    Enzyme,
    FermentationTypeOrganism,
    Ingredient,
    IngredientNutrient,
    Measurement,
    Organism,
    OrganismEnzyme,
)


async def _seed(db_session: AsyncSession) -> Batch:
    lp = Organism(name="Lactobacillus plantarum", kingdom="bacteria", source_version="v1")
    ldh = Enzyme(ec_number="1.1.1.27", name="L-lactate dehydrogenase", source_version="v1")
    cabbage = Ingredient(
        name="Cabbage", default_role="base", fermentation_systems=["lacto_ferment"]
    )
    db_session.add_all([lp, ldh, cabbage])
    await db_session.flush()
    db_session.add(OrganismEnzyme(organism_id=lp.id, enzyme_id=ldh.id))
    db_session.add(FermentationTypeOrganism(fermentation_type="lacto_ferment", organism_id=lp.id))
    for k, v in {"water": 92.2, "sugars_total": 3.2, "glucose": 1.67, "fructose": 1.45}.items():
        db_session.add(
            IngredientNutrient(
                ingredient_id=cabbage.id, nutrient=k, amount_per_100g=v, source="usda_fdc",
                source_food_id="1", source_version="test",
            )
        )  # fmt: skip
    culture = Culture(name="Kraut", type="lacto_ferment")
    db_session.add(culture)
    await db_session.flush()
    started = datetime.now(UTC) - timedelta(hours=30)
    batch = Batch(
        culture_id=culture.id, started_at=started, current_stage="ferment",
        stage_entered_at=started, expected_temperature_c=20.0,
    )  # fmt: skip
    db_session.add(batch)
    await db_session.flush()
    db_session.add_all(
        [
            Measurement(batch_id=batch.id, measured_at=started + timedelta(hours=1), type="pH",
                        value_numeric=6.1),
            Measurement(batch_id=batch.id, measured_at=started + timedelta(hours=26), type="pH",
                        value_numeric=5.3),
            Measurement(batch_id=batch.id, measured_at=started + timedelta(hours=2), type="note",
                        value_text="smells fresh"),
        ]
    )  # fmt: skip
    await db_session.commit()
    return batch


@pytest.mark.asyncio
async def test_prediction_endpoint(client: AsyncClient, db_session: AsyncSession) -> None:
    batch = await _seed(db_session)
    listed = await client.get("/ingredients", params={"substrate": "lacto_ferment"})
    cabbage_id = listed.json()[0]["id"]
    resp = await client.post(
        f"/batches/{batch.id}/ingredients",
        json={"ingredient_id": cabbage_id, "quantity": 1, "unit": "kg"},
    )
    assert resp.status_code == 201

    resp = await client.get(f"/batches/{batch.id}/prediction")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "calibrated"
    assert body["temperature"] == {
        "forecast_c": 20.0, "source": "expected", "type_default_c": 20.0,
        "range_c": [16.0, 24.0], "readings": 0,
    }  # fmt: skip
    assert 29.0 < body["now_h"] < 31.0
    assert body["started_at"].startswith(batch.started_at.isoformat()[:16])
    assert [o["value"] for o in body["observations"]] == [6.1, 5.3]
    (org,) = body["organisms"]
    assert org["name"] == "Lactobacillus plantarum"
    assert org["pathways"][0]["in_reference_graph"] is True
    assert body["initial"]["source"] == "recipe"
    assert any(s["key"] == "lactic_acid" for s in body["series"])

    resp = await client.get(f"/batches/{batch.id}/prediction", params={"temperature_c": 26})
    assert resp.status_code == 200
    assert resp.json()["temperature"]["source"] == "override"


@pytest.mark.asyncio
async def test_prediction_endpoint_errors(client: AsyncClient, db_session: AsyncSession) -> None:
    resp = await client.get("/batches/00000000-0000-0000-0000-000000000000/prediction")
    assert resp.status_code == 404
    batch = await _seed(db_session)
    for params in ({"temperature_c": 80}, {"temperature_c": -10}, {"horizon_h": 0}):
        resp = await client.get(f"/batches/{batch.id}/prediction", params=params)
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_finished_batch_forecasts_from_its_end(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    batch = await _seed(db_session)
    batch.outcome = "success"
    batch.ended_at = batch.started_at + timedelta(hours=12)
    await db_session.commit()
    body = (await client.get(f"/batches/{batch.id}/prediction")).json()
    assert body["now_h"] == pytest.approx(12.0, abs=0.01)
    assert any("marked finished" in w for w in body["warnings"])


@pytest.mark.asyncio
async def test_budget_exhaustion_is_a_503(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fermenttrack.prediction import engine, service

    def fail(*args: object, **kwargs: object) -> None:
        raise engine.SimulationError("over budget")

    monkeypatch.setattr(service, "run_inference", fail)
    batch = await _seed(db_session)
    resp = await client.get(f"/batches/{batch.id}/prediction")
    assert resp.status_code == 503
    assert "budget" in resp.json()["detail"]
