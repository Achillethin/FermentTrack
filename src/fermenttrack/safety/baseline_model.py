"""Baseline Monod ODE model for lactic fermentation kinetics.

Vendored from fermentation/src/fermentation/twin/baseline_model.py
(see docs/DEPENDENCIES.md § 1). No logic changes — only the module path moved
(fermentation.twin.state -> fermenttrack.safety.state).

   dX/dt = μ_max · S/(K_s + S) · (1 - P/P_max) · X
   dS/dt = -(1/Y_xs) · dX/dt
   dP/dt = Y_px · dX/dt

Where:
   X = biomass, S = substrate, P = product (lactic acid)
   μ_max = maximum specific growth rate
   K_s = half-saturation constant
   Y_xs = biomass/substrate yield
   Y_px = product/biomass yield
   P_max = product concentration at full inhibition
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from scipy.integrate import solve_ivp

from fermenttrack.safety.state import TwinState

logger = logging.getLogger(__name__)


def _validated_step_count(total_hours: float, dt_hours: float) -> int:
    if not math.isfinite(total_hours) or not math.isfinite(dt_hours):
        raise ValueError("total_hours and dt_hours must be finite")
    if dt_hours <= 0:
        raise ValueError("dt_hours must be > 0")
    if total_hours < 0:
        raise ValueError("total_hours must be >= 0")
    ratio = total_hours / dt_hours
    if not math.isclose(ratio, round(ratio), abs_tol=1e-9):
        raise ValueError("total_hours must be an exact multiple of dt_hours")
    return round(ratio)


@dataclass
class MonodParams:
    """Kinetic parameters for the Monod model.

    Defaults tuned for Lactobacillus plantarum on vegetable substrate
    at ~22°C, 3% NaCl.
    """

    mu_max: float = 0.35          # h⁻¹ — max specific growth rate
    K_s: float = 0.5              # g/L — half-saturation constant
    Y_xs: float = 0.4             # g biomass / g substrate
    Y_px: float = 2.0             # g product / g biomass
    P_max: float = 25.0           # g/L — full product inhibition

    # Temperature correction (Ratkowsky-style)
    T_min: float = 5.0            # °C — min growth temp
    T_opt: float = 30.0           # °C — optimal growth temp
    T_max: float = 45.0           # °C — max growth temp
    b_T: float = 0.055            # Ratkowsky slope (tuned for LAB at 20-25°C)

    # Salt inhibition
    salt_max_pct: float = 12.0    # % — salt at full inhibition

    def temperature_factor(self, temp_c: float) -> float:
        """Ratkowsky-style temperature correction factor [0, 1]."""
        if temp_c <= self.T_min or temp_c >= self.T_max:
            return 0.0
        f = (self.b_T * (temp_c - self.T_min)) ** 2
        return min(f, 1.0)

    def salt_factor(self, salt_pct: float) -> float:
        """Linear salt inhibition factor [0, 1]."""
        if salt_pct >= self.salt_max_pct:
            return 0.0
        return max(0.0, 1.0 - salt_pct / self.salt_max_pct)


class BaselineMonodModel:
    """Monod ODE trajectory model for lactic fermentation."""

    def __init__(self, params: MonodParams | None = None):
        self.params = params or MonodParams()

    def step(self, state: TwinState) -> TwinState:
        """Advance state by one dt_hours step using Monod ODE.

        Modifies state in-place and returns it.
        """
        p = self.params

        # environmental corrections
        f_T = p.temperature_factor(state.temperature_c)
        f_salt = p.salt_factor(state.salt_pct)
        mu_eff = p.mu_max * f_T * f_salt

        y0 = [state.biomass, state.substrate, state.product]
        t_span = (0.0, state.dt_hours)
        pre_product = state.product

        def odes(t: float, y: list[float]) -> list[float]:
            X, S, P = y
            X = max(X, 0.0)
            S = max(S, 0.0)
            P = max(P, 0.0)

            # Monod with product inhibition
            growth = mu_eff * (S / (p.K_s + S)) * (1 - P / p.P_max) * X
            growth = max(growth, 0.0)

            dX = growth
            dS = -(1 / p.Y_xs) * growth
            dP = p.Y_px * growth

            return [dX, dS, dP]

        sol = solve_ivp(odes, t_span, y0, method="RK45", max_step=0.1)

        if sol.success and len(sol.y[0]) > 0:
            state.biomass = float(max(sol.y[0][-1], 0.0))
            state.substrate = float(max(sol.y[1][-1], 0.0))
            state.product = float(max(sol.y[2][-1], 0.0))
        else:
            logger.warning("ODE integration failed: %s", sol.message)

        # pH model: approximate pH drop from lactic acid accumulation
        # pH drops proportionally to the new product formed this step
        delta_product = state.product - pre_product
        state.ph = max(3.0, state.ph - 0.15 * delta_product)

        state.time_hours += state.dt_hours
        state.model_source = "baseline"

        return state

    def simulate(
        self,
        state: TwinState,
        total_hours: float = 72.0,
        record: bool = True,
    ) -> TwinState:
        """Run the model for total_hours, recording snapshots."""
        steps = _validated_step_count(total_hours, state.dt_hours)
        for _ in range(steps):
            self.step(state)
            if record:
                state.record_tick()
        return state

    def predict_trajectory(
        self,
        state: TwinState,
        total_hours: float = 72.0,
    ) -> dict[str, list[float]]:
        """Return time-series arrays for plotting."""
        times, phs, biomasses, substrates, products = [], [], [], [], []

        steps = _validated_step_count(total_hours, state.dt_hours)
        for _ in range(steps):
            self.step(state)
            times.append(state.time_hours)
            phs.append(state.ph)
            biomasses.append(state.biomass)
            substrates.append(state.substrate)
            products.append(state.product)

        return {
            "time_hours": times,
            "ph": phs,
            "biomass": biomasses,
            "substrate": substrates,
            "product": products,
        }
