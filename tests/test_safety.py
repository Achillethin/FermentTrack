"""Safety advisory — proves the vendored rule engine is wired correctly by
reproducing the botulism-risk scenario from docs/DEPENDENCIES.md § 1:
low salt (~1.5%), high temp (~25C), lacto-style ferment held anaerobic at
pH > 4.6 -> BOT-001 hard stop.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from fermenttrack.safety.rule_engine import SafetyRuleEngine
from fermenttrack.safety.state import TwinState


@pytest.mark.asyncio
async def test_safety_endpoint_flags_botulism_risk(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "Veg ferment", "type": "lactic"})
    culture_id = resp.json()["id"]
    resp = await client.post("/batches", json={"culture_id": culture_id})
    batch_id = resp.json()["id"]

    # Low salt, high temp, no acidification yet -> pH stays near neutral,
    # anaerobic by TwinState default. Matches BOT-001's condition.
    await client.post(
        f"/batches/{batch_id}/measure", json={"type": "temperature", "value_numeric": 25.0}
    )
    await client.post(f"/batches/{batch_id}/measure", json={"type": "salt_pct", "value_numeric": 1.5})
    await client.post(f"/batches/{batch_id}/measure", json={"type": "pH", "value_numeric": 5.5})

    resp = await client.get(f"/batches/{batch_id}/safety")
    assert resp.status_code == 200
    report = resp.json()

    assert report["safe"] is False
    hard_stop_codes = {h["reason_code"] for h in report["hard_stops"]}
    assert "BOTULISM_RISK_LOW_ACID" in hard_stop_codes


@pytest.mark.asyncio
async def test_safety_endpoint_safe_batch(client: AsyncClient) -> None:
    resp = await client.post("/cultures", json={"name": "Veg ferment", "type": "lactic"})
    culture_id = resp.json()["id"]
    resp = await client.post("/batches", json={"culture_id": culture_id})
    batch_id = resp.json()["id"]

    # Well-acidified, adequately salted -> no hard stops.
    await client.post(f"/batches/{batch_id}/measure", json={"type": "pH", "value_numeric": 3.4})
    await client.post(f"/batches/{batch_id}/measure", json={"type": "salt_pct", "value_numeric": 3.0})
    await client.post(
        f"/batches/{batch_id}/measure", json={"type": "temperature", "value_numeric": 20.0}
    )

    resp = await client.get(f"/batches/{batch_id}/safety")
    assert resp.status_code == 200
    report = resp.json()
    assert report["safe"] is True
    assert report["hard_stops"] == []


@pytest.mark.asyncio
async def test_safety_endpoint_404_for_unknown_batch(client: AsyncClient) -> None:
    resp = await client.get("/batches/00000000-0000-0000-0000-000000000000/safety")
    assert resp.status_code == 404


def test_rule_engine_direct_botulism_scenario() -> None:
    """Unit-level reproduction (no HTTP layer) of the DEPENDENCIES.md smoke test:
    low-salt/high-temp lacto-ferment correctly triggers a botulism hard-stop."""
    state = TwinState(scheme="lactic", temperature_c=25.0, salt_pct=1.5, ph=5.5)
    report = SafetyRuleEngine().evaluate(state.state_vars(), scheme=state.scheme)
    assert report.safe is False
    assert any(v.reason_code == "BOTULISM_RISK_LOW_ACID" for v in report.hard_stops)
    assert any(v.reason_code == "LOW_SALT_VEG_FERMENT" for v in report.warnings)
