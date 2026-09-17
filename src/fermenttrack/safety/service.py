"""Wires a Batch's latest measurements into the vendored safety rule engine.

Per docs/ARCHITECTURE.md § Safety Advisory Layer. The vendored risk_rules.yaml
only defines rules for the "lactic" and "enzymatic_koji" schemes (see
data/curated/risk_rules.yaml upstream) — culture.type values that aren't one
of those (kombucha, sourdough, cheese, kefir, ...) are evaluated under
"lactic" as the closest food-safety analog (low-acid anaerobic risk applies
to any anaerobic ferment, not just literal lactic-acid ones).
"""

from __future__ import annotations

from fermenttrack.models import Batch, Measurement
from fermenttrack.safety.rule_engine import SafetyReport, SafetyRuleEngine
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


def get_safety_report(batch: Batch) -> SafetyReport:
    """Evaluate cited food-safety rules against the batch's latest measurements."""
    state = twin_state_for_batch(batch)
    return SafetyRuleEngine().evaluate(state.state_vars(), scheme=state.scheme)
