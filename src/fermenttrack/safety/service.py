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

from fermenttrack.models import Batch, Measurement
from fermenttrack.safety.rule_engine import RuleVerdict, SafetyReport, SafetyRuleEngine
from fermenttrack.safety.state import TwinState

_SCHEME_MAP = {
    "koji": "enzymatic_koji",
}


def _scheme_for(culture_type: str) -> str:
    return _SCHEME_MAP.get(culture_type, "lactic")


def _latest_numeric(measurements: list[Measurement], type_: str) -> float | None:
    matches = [m for m in measurements if m.type == type_ and m.value_numeric is not None]
    if not matches:
        return None
    return max(matches, key=lambda m: m.measured_at).value_numeric


def twin_state_for_batch(batch: Batch) -> TwinState:
    """Build a TwinState from a batch's latest measurements.

    Missing measurements fall back to TwinState defaults (which read as
    "unknown/neutral" to the rule engine, not as an unsafe condition) — the
    caller should treat a report built from sparse data cautiously.
    """
    measurements = list(batch.measurements)
    scheme = _scheme_for(batch.culture.type)

    kwargs: dict[str, float] = {}
    ph = _latest_numeric(measurements, "pH")
    temp = _latest_numeric(measurements, "temperature")
    salt = _latest_numeric(measurements, "salt_pct")
    if ph is not None:
        kwargs["ph"] = ph
    if temp is not None:
        kwargs["temperature_c"] = temp
    if salt is not None:
        kwargs["salt_pct"] = salt

    time_hours = (
        (
            max(m.measured_at for m in measurements) - batch.started_at
        ).total_seconds()
        / 3600.0
        if measurements
        else 0.0
    )

    return TwinState(scheme=scheme, time_hours=max(time_hours, 0.0), **kwargs)


# state variable -> the measurement type that grounds it
_MEASURED = {"ph": "pH", "temperature_c": "temperature", "salt_pct": "salt_pct"}


def get_safety_report(batch: Batch) -> SafetyReport:
    """Evaluate cited food-safety rules against the batch's latest measurements.

    A rule only counts if every measurable variable in its condition was actually
    measured: TwinState fills gaps with defaults (pH 6.5, salt 3 %), and a rule firing on
    those would be an alarm about values nobody observed (e.g. "botulism risk, do not
    consume" on a sourdough levain with no pH reading)."""
    state = twin_state_for_batch(batch)
    engine = SafetyRuleEngine()
    report = engine.evaluate(state.state_vars(), scheme=state.scheme)
    measurements = list(batch.measurements)
    unmeasured = [v for v, t in _MEASURED.items() if _latest_numeric(measurements, t) is None]

    def grounded(v: RuleVerdict) -> bool:
        rule = engine.catalog.get_rule(v.rule_id)
        cond = rule.condition if rule is not None else ""
        return not any(re.search(r"\b" + var + r"\b", cond) for var in unmeasured)

    hard = [v for v in report.hard_stops if grounded(v)]
    warn = [v for v in report.warnings if grounded(v)]
    return SafetyReport(
        safe=not hard, hard_stops=hard, warnings=warn,
        rules_evaluated=report.rules_evaluated, rules_triggered=len(hard) + len(warn),
    )  # fmt: skip
