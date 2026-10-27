"""Safety advisory — proves the vendored rule engine is wired correctly by
reproducing the botulism-risk scenario from docs/DEPENDENCIES.md § 1:
low salt (~1.5%), high temp (~25C), lacto-style ferment held anaerobic at
pH > 4.6 -> BOT-001 hard stop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from fermenttrack.safety.rule_engine import SafetyRuleEngine
from fermenttrack.safety.service import get_safety_report
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


async def test_no_alarm_about_values_nobody_measured(client: AsyncClient) -> None:
    """A levain with only a rise reading: no pH, no salt logged. The botulism rule must not
    fire on TwinState's default pH 6.5 / salt 3 % (it said "do not consume")."""
    culture = await client.post("/cultures", json={"name": "Levain", "type": "sourdough"})
    batch = await client.post("/batches", json={"culture_id": culture.json()["id"]})
    batch_id = batch.json()["id"]
    await client.post(f"/batches/{batch_id}/measure", json={"type": "rise", "value_numeric": 40})
    report = (await client.get(f"/batches/{batch_id}/safety")).json()
    assert report["safe"] is True and report["hard_stops"] == []
    # once pH and salt are measured and unsafe, it still fires
    await client.post(f"/batches/{batch_id}/measure", json={"type": "pH", "value_numeric": 5.5})
    await client.post(f"/batches/{batch_id}/measure", json={"type": "salt_pct", "value_numeric": 1.5})
    await client.post(f"/batches/{batch_id}/measure", json={"type": "temperature", "value_numeric": 25})
    assert (await client.get(f"/batches/{batch_id}/safety")).json()["safe"] is False


# ── what the banner can know (2026-10-26 site critique, fix 1) ──────────

T0 = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)


def _batch(type_: str, *readings: tuple[str, float, float], temp: float | None = 20.0):
    """A batch-like object: (measurement type, value, hours after the start) per reading."""
    ms = [SimpleNamespace(type=k, value_numeric=v, measured_at=T0 + timedelta(hours=h))
          for k, v, h in readings]  # fmt: skip
    return SimpleNamespace(
        culture=SimpleNamespace(type=type_), measurements=ms, started_at=T0,
        expected_temperature_c=temp,
    )  # fmt: skip


def _codes(batch, at_h: float) -> tuple[set[str], set[str]]:  # type: ignore[no-untyped-def]
    r = get_safety_report(batch, now=T0 + timedelta(hours=at_h))
    return {v.reason_code for v in r.hard_stops}, {v.reason_code for v in r.warnings}


def test_no_ph_after_24_h_warns_on_the_acid_safety_types_only() -> None:
    assert _codes(_batch("lacto_ferment"), 120) == (set(), {"MISSING_PH_READING"})
    assert _codes(_batch("lacto_ferment"), 12) == (set(), set())
    assert _codes(_batch("sourdough"), 120) == (set(), set())  # the bake is its barrier


def test_ph_above_4_6_after_48_h_stops_at_the_expected_temperature() -> None:
    """No temperature logged: the batch's expected temperature grounds BOT-002."""
    hard, _ = _codes(_batch("kombucha", ("pH", 5.5, 60)), 60)
    assert hard == {"BOTULISM_RISK_SLOW_ACIDIFICATION"}
    assert _codes(_batch("kombucha", ("pH", 5.5, 60), temp=8.0), 60)[0] == set()
    assert _codes(_batch("kombucha", ("pH", 4.2, 60)), 60) == (set(), set())
    # a salt-barrier type keeps the old behaviour: no expected-temperature fallback
    assert _codes(_batch("miso", ("pH", 5.5, 60)), 60)[0] == set()


def test_salted_vegetables_follow_the_two_step_rule() -> None:
    """Owner decision 2026-10-26 (VEG-001/002 instead of BOT-002): below 5.0 by 48 h, then
    4.6 or lower before eating. Kristek's normal kraut at pH 4.8 on day 3 is not a stop."""
    assert _codes(_batch("lacto_ferment", ("pH", 5.2, 60)), 60) == (
        {"VEG_ACIDIFICATION_FAILED"}, set(),
    )  # fmt: skip
    assert _codes(_batch("lacto_ferment", ("pH", 4.8, 60)), 60) == (set(), {"VEG_NOT_READY"})
    assert _codes(_batch("lacto_ferment", ("pH", 4.5, 60)), 60) == (set(), set())
    assert _codes(_batch("lacto_ferment", ("pH", 5.2, 30)), 30) == (set(), set())  # before 48 h
    assert _codes(_batch("lacto_ferment", ("pH", 5.2, 60), temp=8.0), 60)[0] == set()  # cold
    # other types never see the vegetable rules: kombucha keeps BOT-002
    assert _codes(_batch("kombucha", ("pH", 4.8, 60)), 60) == (
        {"BOTULISM_RISK_SLOW_ACIDIFICATION"}, set(),
    )  # fmt: skip


def test_hot_garum_is_not_a_temp_001_stop() -> None:
    """Owner decision 2026-10-26, as the gate (gate.GARUM_HOT_MIN_C): at or above 57 °C a
    garum is an enzymatic hydrolysis; 45-57 °C stays a stop; other types keep 45 °C."""
    hot = _batch("garum", ("temperature", 60.0, 10), temp=None)
    assert "TEMP_TOO_HIGH_LACTIC" not in _codes(hot, 20)[0]
    warm = _batch("garum", ("temperature", 50.0, 10), temp=None)
    assert "TEMP_TOO_HIGH_LACTIC" in _codes(warm, 20)[0]
    miso = _batch("miso", ("temperature", 60.0, 10), temp=None)
    assert "TEMP_TOO_HIGH_LACTIC" in _codes(miso, 20)[0]


def test_a_stale_reading_is_not_a_verdict() -> None:
    """pH 5.5 at 30 h, viewed at 60 h: unknown now, so no hard stop (Today asks for a
    reading); the rule reads the reading's time, not the clock."""
    assert _codes(_batch("lacto_ferment", ("pH", 5.5, 30)), 60) == (set(), set())
