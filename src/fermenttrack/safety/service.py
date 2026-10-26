"""Wires a Batch's latest measurements into the vendored safety rule engine.

Per docs/ARCHITECTURE.md § Safety Advisory Layer. The vendored risk_rules.yaml
only defines rules for the "lactic" and "enzymatic_koji" schemes (see
data/curated/risk_rules.yaml upstream) — culture.type values that aren't one
of those (kombucha, sourdough, cheese, kefir, ...) are evaluated under
"lactic" as the closest food-safety analog (low-acid anaerobic risk applies
to any anaerobic ferment, not just literal lactic-acid ones).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fermenttrack.models import Batch, Measurement
from fermenttrack.recommender.gate import ACID_SAFETY_TYPES
from fermenttrack.reminders import now_utc
from fermenttrack.safety.rule_engine import RuleVerdict, SafetyReport, SafetyRuleEngine
from fermenttrack.safety.state import TwinState

_SCHEME_MAP = {
    "koji": "enzymatic_koji",
}


def _scheme_for(culture_type: str) -> str:
    return _SCHEME_MAP.get(culture_type, "lactic")


def _latest(measurements: list[Measurement], type_: str) -> Measurement | None:
    matches = [m for m in measurements if m.type == type_ and m.value_numeric is not None]
    return max(matches, key=lambda m: m.measured_at, default=None)


def _utc(dt: datetime) -> datetime:
    # SQLite (tests, local dev) drops tz-awareness; app timestamps are UTC by convention.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# state variable -> the measurement type that grounds it
_MEASURED = {"ph": "pH", "temperature_c": "temperature", "salt_pct": "salt_pct"}


def _observed(batch: Batch, now: datetime | None = None) -> tuple[dict[str, float], float]:
    """The state variables the batch grounds, and the hours the time rules read.

    The time rules (BOT-002, GEN-001) are about pH, so the time is the latest pH reading's:
    a reading of 5.5 taken at 30 h, viewed at 60 h, says "measure again", not "botulism".
    With no pH reading it is the time since the start. The acid-safety types (the cards
    with the pH line, gate.ACID_SAFETY_TYPES) fall back to the batch's expected temperature
    when none was logged, so BOT-002 can fire on the temperature the user said they keep."""
    measurements = list(batch.measurements)
    observed = {v: m.value_numeric for v, t in _MEASURED.items() if (m := _latest(measurements, t))}
    if (
        "temperature_c" not in observed
        and batch.culture.type in ACID_SAFETY_TYPES
        and batch.expected_temperature_c is not None
    ):
        observed["temperature_c"] = batch.expected_temperature_c
    ph = _latest(measurements, "pH")
    at = ph.measured_at if ph is not None else (now or now_utc())
    hours = (_utc(at) - _utc(batch.started_at)).total_seconds() / 3600.0
    return observed, max(hours, 0.0)


def twin_state_for_batch(batch: Batch, now: datetime | None = None) -> TwinState:
    """Build a TwinState from a batch's latest measurements.

    Missing measurements fall back to TwinState defaults (which read as
    "unknown/neutral" to the rule engine, not as an unsafe condition) — the
    caller should treat a report built from sparse data cautiously.
    """
    observed, hours = _observed(batch, now)
    return TwinState(scheme=_scheme_for(batch.culture.type), time_hours=hours, **observed)


def get_safety_report(batch: Batch, now: datetime | None = None) -> SafetyReport:
    """Evaluate cited food-safety rules against the batch's latest measurements.

    A rule only counts if every measurable variable in its condition was actually
    measured: TwinState fills gaps with defaults (pH 6.5, salt 3 %), and a rule firing on
    those would be an alarm about values nobody observed (e.g. "botulism risk, do not
    consume" on a sourdough levain with no pH reading). GEN-001 ("no pH reading after
    24 h") is the exception: it is about the missing pH, so it is evaluated with pH None,
    for the acid-safety types only (a levain's safety is the bake, not its pH)."""
    observed, hours = _observed(batch, now)
    state = TwinState(scheme=_scheme_for(batch.culture.type), time_hours=hours, **observed)
    engine = SafetyRuleEngine()
    report = engine.evaluate(state.state_vars(), scheme=state.scheme)
    unmeasured = [v for v in _MEASURED if v not in observed]

    def grounded(v: RuleVerdict) -> bool:
        rule = engine.catalog.get_rule(v.rule_id)
        cond = rule.condition if rule is not None else ""
        return not any(re.search(r"\b" + var + r"\b", cond) for var in unmeasured)

    hard = [v for v in report.hard_stops if grounded(v)]
    warn = [v for v in report.warnings if grounded(v)]
    if "ph" in unmeasured and batch.culture.type in ACID_SAFETY_TYPES:
        missing = engine.evaluate_single("GEN-001", {**state.state_vars(), "ph": None})
        if missing is not None and missing.triggered:
            warn.append(missing)
    return SafetyReport(
        safe=not hard, hard_stops=hard, warnings=warn,
        rules_evaluated=report.rules_evaluated, rules_triggered=len(hard) + len(warn),
    )  # fmt: skip
