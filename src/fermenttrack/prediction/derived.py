"""Derived readouts of a forecast ensemble: nutrition per 100 g and taste over time.

Pure numpy, no DB. Computed per ensemble member from the trajectories after the kinetic
solve (the solve is unchanged), so the posterior your readings shaped carries over and a
what-if temperature moves these curves too. Aroma joins in increment B.
Design: docs/superpowers/specs/2026-10-02-flavour-nutrition-design.md § 2, 3, 7, 8.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fermenttrack.prediction import compounds as C
from fermenttrack.prediction.engine import PI
from fermenttrack.prediction.priors import FloatArray

SUGARS = ("sucrose", "hexoses", "lactose", "maltose")

# Nutrition-label rows in declaration order (Regulation (EU) 1169/2011): key, label, unit.
LABEL_ROWS: tuple[tuple[str, str, str], ...] = (
    ("energy_kj", "Energy", "kJ"),
    ("energy_kcal", "Energy", "kcal"),
    ("fat", "Fat", "g"),
    ("carbohydrate", "Carbohydrate", "g"),
    ("sugars", "of which sugars", "g"),
    ("lactose", "of which lactose", "g"),
    ("fibre", "Fibre", "g"),
    ("protein", "Protein", "g"),
    ("free_amino_acids", "of which free amino acids", "g"),
    ("salt", "Salt", "g"),
    ("alcohol", "Alcohol", "% ABV"),
    ("organic_acids", "Organic acids", "g"),
)


@dataclass(frozen=True)
class Carried:
    """Recipe nutrients the ferment does not change, g per kg of starting batch. None = no
    ingredient reports it (unknown, never zero); `lower` = label rows that are lower bounds
    (an ingredient without data, or one that does not report that nutrient)."""

    fat: float | None = None
    fibre: float | None = None
    sodium: float | None = None
    other_carbohydrate: float | None = None  # carbohydrate the model does not track
    lower: frozenset[str] = frozenset()


UNKNOWN = Carried()


def mass_left(pools: FloatArray, co2_escapes: bool) -> FloatArray:
    """(N, T) share of the starting mass still in the jar: the CO2 that escapes leaves."""
    co2 = pools[:, :, PI["co2"]]
    if not co2_escapes:
        return np.ones_like(co2)
    return np.asarray(1.0 - np.clip(co2, 0.0, 500.0) / 1000.0)


def nutrition(
    pools: FloatArray, carried: Carried, co2_escapes: bool
) -> tuple[dict[str, FloatArray], frozenset[str]]:
    """Label rows per 100 g of what remains, (N, T) each; unknown rows are absent."""
    left = mass_left(pools, co2_escapes)

    def p(k: str) -> FloatArray:
        return np.asarray(pools[:, :, PI[k]])

    def per100(g_per_kg: FloatArray) -> FloatArray:
        return np.asarray(g_per_kg / (10.0 * left))

    sugars = p("sucrose") + p("hexoses") + p("lactose") + p("maltose")
    ethanol = per100(p("ethanol"))
    rows: dict[str, FloatArray] = {
        "carbohydrate": per100(sugars + p("starch") + (carried.other_carbohydrate or 0.0)),
        "sugars": per100(sugars),
        "lactose": per100(p("lactose")),
        "protein": per100(p("protein") + p("peptides") + p("amino_acids")),
        "free_amino_acids": per100(p("amino_acids")),
        "organic_acids": per100(p("lactic_acid") + p("acetic_acid") + p("gluconic_acid")),
        "alcohol": np.asarray(ethanol * 10.0 / C.ETHANOL_G_PER_L_PER_ABV),
    }
    if carried.fat is not None:
        rows["fat"] = per100(np.full_like(left, carried.fat))
    if carried.fibre is not None:
        rows["fibre"] = per100(np.full_like(left, carried.fibre))
    if carried.sodium is not None:
        rows["salt"] = per100(np.full_like(left, carried.sodium * C.SALT_PER_SODIUM))
    zero = np.zeros_like(left)
    parts = {
        "carbohydrate": rows["carbohydrate"],
        "protein": rows["protein"],
        "fat": rows.get("fat", zero),
        "alcohol": ethanol,
        "organic_acid": rows["organic_acids"],
        "fibre": rows.get("fibre", zero),
    }
    rows["energy_kcal"] = np.asarray(sum(C.ENERGY[k][0] * v for k, v in parts.items()))
    rows["energy_kj"] = np.asarray(sum(C.ENERGY[k][1] * v for k, v in parts.items()))
    lower = set(carried.lower)
    if carried.other_carbohydrate is None:
        lower.add("carbohydrate")
    if carried.fat is None or carried.fibre is None or lower & {"fat", "fibre", "carbohydrate"}:
        lower |= {"energy_kcal", "energy_kj"}
    return rows, frozenset(lower & rows.keys())
