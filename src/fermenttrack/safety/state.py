"""TwinState — dataclass holding the full state of a fermentation experiment.

Vendored from fermentation/src/fermentation/twin/state.py
(see docs/DEPENDENCIES.md § 1). No logic changes — only the module path moved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass
class TwinState:
    """Mutable state snapshot of a running fermentation experiment.

    This is the central data structure passed through the model ensemble
    and safety gate on every simulation tick.
    """

    experiment_id: str = field(default_factory=lambda: f"exp_{uuid.uuid4().hex[:8]}")
    scheme: str = "lactic"  # lactic | enzymatic_koji

    # ── time axis ────────────────────────────────────────────────────────
    time_hours: float = 0.0
    dt_hours: float = 1.0  # default step

    # ── measurable state variables ───────────────────────────────────────
    ph: float = 6.5
    temperature_c: float = 22.0
    salt_pct: float = 3.0
    water_activity: float = 0.96
    oxygen_proxy: str = "anaerobic"  # aerobic | anaerobic | micro

    # ── population / biomass (arbitrary units) ───────────────────────────
    biomass: float = 0.01          # starter biomass
    substrate: float = 10.0        # available sugar / starch (g/L equiv.)
    product: float = 0.0           # lactic acid / enzyme product (g/L)

    # ── ingredient context ───────────────────────────────────────────────
    ingredient_ids: list[str] = field(default_factory=list)
    microbe_ids: list[str] = field(default_factory=list)

    # ── model provenance ─────────────────────────────────────────────────
    model_source: str = "baseline"  # baseline | graphml | pinn | ensemble
    safe: bool = True

    # ── history ──────────────────────────────────────────────────────────
    history: list[dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        """Return a serialisable snapshot of current state."""
        return {
            "snapshot_id": f"snap_{uuid.uuid4().hex[:8]}",
            "experiment_id": self.experiment_id,
            "time_hours": self.time_hours,
            "ph": self.ph,
            "temperature_c": self.temperature_c,
            "salt_pct": self.salt_pct,
            "water_activity": self.water_activity,
            "oxygen_proxy": self.oxygen_proxy,
            "biomass": self.biomass,
            "substrate": self.substrate,
            "product": self.product,
            "safe": self.safe,
            "model_source": self.model_source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_snapshot(
        cls,
        snapshot: Mapping[str, Any],
        *,
        scheme: str,
        dt_hours: float,
        ingredient_ids: list[str] | None = None,
        microbe_ids: list[str] | None = None,
    ) -> "TwinState":
        """Reconstruct a runtime state from a serialised snapshot."""
        safe_value = snapshot.get("safe", True)
        safe = (
            safe_value
            if isinstance(safe_value, bool)
            else str(safe_value).strip().lower() in {"true", "1", "yes"}
        )
        return cls(
            experiment_id=str(snapshot.get("experiment_id", f"exp_{uuid.uuid4().hex[:8]}")),
            scheme=scheme,
            time_hours=float(snapshot.get("time_hours", 0.0)),
            dt_hours=dt_hours,
            ph=float(snapshot.get("ph", 6.5)),
            temperature_c=float(snapshot.get("temperature_c", 22.0)),
            salt_pct=float(snapshot.get("salt_pct", 3.0)),
            water_activity=float(snapshot.get("water_activity", 0.96)),
            oxygen_proxy=str(snapshot.get("oxygen_proxy", "anaerobic")),
            biomass=float(snapshot.get("biomass", 0.0)),
            substrate=float(snapshot.get("substrate", 0.0)),
            product=float(snapshot.get("product", 0.0)),
            ingredient_ids=list(ingredient_ids or []),
            microbe_ids=list(microbe_ids or []),
            model_source=str(snapshot.get("model_source", "baseline")),
            safe=safe,
        )

    def record_tick(self) -> None:
        """Append current state to history."""
        self.history.append(self.snapshot())

    def state_vars(self) -> dict[str, Any]:
        """Return dict suitable for safety rule engine evaluation."""
        return {
            "ph": self.ph,
            "temperature_c": self.temperature_c,
            "salt_pct": self.salt_pct,
            "water_activity": self.water_activity,
            "oxygen_proxy": self.oxygen_proxy,
            "time_hours": self.time_hours,
            "biomass": self.biomass,
            "substrate": self.substrate,
            "product": self.product,
        }
