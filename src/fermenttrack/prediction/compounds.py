"""Curated reference data for the derived layer (prediction/derived.py): taste thresholds,
relative sweetness, glutamate shares and energy factors. Aroma compounds join in
increment B (docs/superpowers/specs/2026-10-02-flavour-nutrition-design.md § 4-5).

Every number is cited or marked "est.". Taste thresholds are recognition thresholds in
water and their spread is the spread between people (log10 SD across a panel), so
P(above threshold) reads as "share of people who would notice it, in water". In a food,
other tastes mask each other and thresholds are higher.
"""

from __future__ import annotations

from fermenttrack.prediction.priors import Z90, Prior, fixed


def _panel(median: float, sd_log10: float) -> Prior:
    """A log-normal threshold from a panel's median and log10 standard deviation."""
    k = 10.0 ** (Z90 * sd_log10)
    return Prior(median, median / k, median * k, "log")


# Höhl, Schönberger & Busch-Stockfisch 2014, Ernahrungs Umschau 61:130 (70 panelists,
# deionised water; recognition thresholds in log10 µmol/L, mean ± SD): sucrose 3.7 ± 0.5,
# MSG 3.2 ± 0.4, citric acid 2.2 ± 0.1 (ISO/5 series).
SWEET_THRESHOLD = _panel(1.72, 0.5)  # g sucrose / kg (5.01 mmol/L x 342.3 g/mol)
UMAMI_THRESHOLD = _panel(1.58, 0.4)  # mmol glutamate / kg (MSG 1.58 mmol/L)
# Sour: Johanningsmeier, McFeeters & Drake 2005, J Food Sci 70:R44 - sourness follows the
# molar sum of acid species with a protonated carboxyl group plus H+, about equally for
# every organic acid. Citric acid at its recognition threshold (0.16 mmol/L, Höhl 2014)
# gives ~0.29 mmol/L of such species + H+ (pKa1 3.13). The panel SD there (0.1) is
# censored by the lowest dilution, so the spread here is est.
SOUR_THRESHOLD = _panel(0.30, 0.3)  # mmol/kg protonated acid species + H+
# Ethanol: detection ~1.4 % v/v in water, mostly as bitterness (Mattes & DiMeglio 2001,
# Physiol Behav 72:217); spread est.
ALCOHOL_THRESHOLD = Prior(1.4, 0.5, 4.0)  # % ABV

# Sweetness relative to sucrose, by weight. Compiled ranges: fructose 1.17-1.75, glucose
# 0.74-0.8, lactose 0.16-0.4, maltose 0.33-0.45 (DuBois et al. 1991, ACS Symp Ser 450;
# Kemp & Birch 1992; as compiled in the Wikipedia "Sweetness" table). The model lumps
# glucose and fructose ("hexoses"); yeasts eat glucose first, so leftovers lean fructose.
SWEETNESS: dict[str, Prior] = {
    "sucrose": fixed(1.0),
    "hexoses": Prior(1.0, 0.74, 1.5),
    "lactose": Prior(0.25, 0.16, 0.4),
    "maltose": Prior(0.4, 0.33, 0.45),
}

# Free glutamate as a share of the free amino acids, by mass.
GLUTAMATE_SHARE: dict[str, Prior] = {
    # Park et al. 2002, Fish Sci 68:913: a Vietnamese fish sauce, Glu 2.3 of 14.0 g/100 mL
    # free amino acids (0.16); a second batch had half the glutamate.
    "fish": Prior(0.13, 0.08, 0.17),
    # Miso: glutamate is the most abundant free amino acid, 0.4-1.7 g/100 g (share est.).
    "soy": Prior(0.18, 0.10, 0.30),
    "milk": Prior(0.15, 0.08, 0.22),  # est. (casein is ~20 % Glu + Gln)
    "cereal": Prior(0.15, 0.08, 0.25),  # est.
}
GLUTAMATE_MW = 147.13

# Regulation (EU) No 1169/2011, Annex XIV: (kcal, kJ) per g.
ENERGY: dict[str, tuple[float, float]] = {
    "carbohydrate": (4.0, 17.0),
    "protein": (4.0, 17.0),
    "fat": (9.0, 37.0),
    "alcohol": (7.0, 29.0),
    "organic_acid": (3.0, 13.0),
    "fibre": (2.0, 8.0),
}
ETHANOL_G_PER_L_PER_ABV = 7.89  # 1 % v/v = 7.89 g/L (ethanol density 0.789)
SALT_PER_SODIUM = 2.5  # EU labelling: salt = sodium x 2.5
