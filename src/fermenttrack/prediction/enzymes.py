"""Enzyme classes for starch and protein breakdown (koji, miso, garum, sourdough flour).

Each class has its own catalysis temperature response, heat inactivation and salt
response; one shared curve cannot describe them (A. oryzae amylases, endo-proteases and
peptidases differ ~10x in heat stability and salt tolerance). Scientific review record:
docs/superpowers/specs/2026-09-25-koji-miso-garum-enzymes-review.md.

Per class c, with activity E_c on a 0-1 "fully grown koji" scale (fish enzymes: 1 = fresh
fish with viscera):

    rate_c  = k_c * E_c * A_c(T) * f_salt,c * access * substrate          (first order)
    A_c(T)  = exp[-Ea_c / R * (1/T - 1/323.15)]                         (catalysis, 50 °C = 1)
    dE_c/dt = production - kd_c(T) * E_c
    kd_c(T) = ln2 / t_half_c * exp[Ed_c / R * (1/T_ref,c - 1/T)]   (heat denaturation)
              + floor_c * 2^((T - 25) / 10)                         (slow loss at 20-35 °C)
    f_salt  = r + (1 - r) / (1 + (s / s50)^2),  s = water-phase NaCl %

The apparent temperature optimum then emerges from catalysis x inactivation over the
process time, which is what saccharification and hydrolysis studies measure (the
earlier model used such a measured optimum curve as if it were instantaneous activity).
Protein breaks down in two steps: endo-proteases solubilise it into peptides, peptidases
release free amino acids.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from fermenttrack.prediction.priors import FloatArray, Prior

R_GAS = 8.314
T_REF_K = 323.15  # 50 °C: rate constants are given at this temperature


def _r(lo: float, med: float, hi: float) -> Prior:
    return Prior(med, lo, hi, "log")


@dataclass(frozen=True)
class EnzymeClass:
    key: str
    label: str
    k: Prior  # 1/h per unit activity at 50 °C, first order in substrate
    ea_kj: Prior  # catalysis activation energy, kJ/mol
    t_half_h: Prior  # heat-denaturation half-life at t_ref_c, hours
    t_ref_c: float
    ed_kj: Prior  # denaturation activation energy, kJ/mol
    floor_25: Prior  # 1/h slow loss at 25 °C (proteolysis, partial unfolding), Q10 2
    salt_s50: Prior  # water-phase NaCl % that halves the salt-sensitive part
    salt_floor: float  # activity retained at any salt
    sources: tuple[str, ...]


AMYLASE = EnzymeClass(
    key="amylase",
    label="α-amylase + glucoamylase: starch → glucose (90 %) and maltose",
    # calibrated: rice koji saccharification ~60 % in 24 h at 50 °C, ~10 % at 15 °C
    # (koji:water 1:2, Akamatsu et al. 2024); 8 h yields at 40/50/60 °C 66/100/92 %
    # (Oguro et al. 2019; the model gives ~64/100/98, and under-predicts 70 °C: 44 vs 77)
    k=_r(0.08, 0.18, 0.4),
    ea_kj=_r(40.0, 55.0, 70.0),
    t_half_h=_r(1.0, 3.0, 10.0),  # at 60 °C, unsalted mash (~18 h at 50 °C, ~10 d at 32 °C)
    t_ref_c=60.0,
    ed_kj=_r(110.0, 160.0, 230.0),
    floor_25=_r(3e-4, 1e-3, 3e-3),
    salt_s50=_r(25.0, 40.0, 80.0),  # weak: 13 % vs 7 % salt barely differ
    salt_floor=0.0,
    sources=(
        "Oguro et al. 2019 J Biosci Bioeng 127:570",
        "Akamatsu et al. 2024 Heliyon 10:e33664",
        "Hasegawa & Funakoshi 2016 Aichi Center Res Rep 5:108",
    ),
)

PROTEASE = EnzymeClass(
    key="protease",
    label="endo-proteases (alkaline, neutral, acid): protein → soluble peptides",
    k=_r(0.03, 0.08, 0.2),  # calibrated with PEPTIDASE on Ohnishi 1982 miso and Su et al. 2005
    ea_kj=_r(35.0, 50.0, 65.0),
    # at 55 °C in mash (extract without substrate: 20 % left after 4 h, Su et al. 2005;
    # substrate stabilises, Bombara et al. 1994); calibrated so a 48 h hydrolysis at
    # 45 °C beats 55 °C (Su et al. 2005)
    t_half_h=_r(3.0, 12.0, 60.0),
    t_ref_c=55.0,
    ed_kj=_r(150.0, 200.0, 300.0),
    floor_25=_r(1e-4, 2e-4, 5e-4),
    salt_s50=_r(8.0, 12.0, 20.0),  # strong: ~3 % left at 18 % NaCl in extract (Su 2005)
    salt_floor=0.0,
    sources=(
        "Su et al. 2005 J Agric Food Chem 53:1521",
        "Hasegawa & Funakoshi 2016 Aichi Center Res Rep 5:108",
        "Ito & Matsuyama 2021 J Fungi 7:658",
    ),
)
# Share of protease activity that does not heat-denature (neutral protease II /
# deuterolysin, stable to 99 °C for 10 min): keeps hot koji garum going. est.
PROTEASE_THERMOSTABLE = _r(0.03, 0.1, 0.25)
# Alkaline protease keeps rising after growth stops (Chancharoonpong et al. 2012): extra
# production per hour per unit of grown mycelium. est.
PROTEASE_LATE_PRODUCTION = _r(0.002, 0.005, 0.012)

PEPTIDASE = EnzymeClass(
    key="peptidase",
    label="amino- and carboxypeptidases: peptides → free amino acids",
    # calibrated with PROTEASE: 48 h at 45 °C, 5 % NaCl gives amino N / soluble N ~0.43
    # (Su et al. 2005); miso at 90 d ~20 % free amino N (Ohnishi 1982)
    k=_r(0.03, 0.08, 0.2),
    ea_kj=_r(35.0, 50.0, 65.0),
    t_half_h=_r(6.0, 24.0, 100.0),  # at 60 °C; stable to ~50 °C
    t_ref_c=60.0,
    ed_kj=_r(150.0, 200.0, 300.0),
    # Slow loss in the mash matters here: without it free amino acids keep rising for a
    # year, while miso formol N plateaus near 20-30 % of total N; exopeptidase activity
    # fades within months (LAP detectable only in month 1 of fish sauce, Siringan et al.
    # 2006). Calibrated: miso ~20 % free amino N at 90 d (Ohnishi 1982). est.
    floor_25=_r(2e-4, 5e-4, 1.2e-3),
    # Moderate overall (AAP ~30 % left in 20 % NaCl, Watanabe et al. 2007), although some
    # are salt-activated (Matsushita-Morita). s50 13 is what fits both Su 2005 (5 % salt)
    # and Ohnishi 1982 (21.7 %) together.
    salt_s50=_r(9.0, 13.0, 20.0),
    salt_floor=0.0,
    sources=(
        "Matsushita-Morita et al. 2010, 2013 (A. oryzae peptidases, NaCl)",
        "Gao et al. 2018 (A. oryzae aminopeptidase in 3 M NaCl)",
        "Watanabe et al. 2007",
    ),
)

FISH = EnzymeClass(
    key="fish_enzyme",
    label="fish trypsin/chymotrypsin/cathepsins: protein → peptides (autolysis)",
    # calibrated: traditional fish sauce (25 % salt, 30-35 °C) mostly solubilised by 6
    # months (Udomsil et al. 2011, 2022); 50 °C faster than 35 °C (Lopetcharat & Park 2002)
    k=_r(0.002, 0.005, 0.012),
    ea_kj=_r(35.0, 50.0, 65.0),
    t_half_h=_r(24.0, 120.0, 480.0),  # at 60 °C; autolysis maximal at 60 °C
    t_ref_c=60.0,
    ed_kj=_r(120.0, 160.0, 220.0),
    floor_25=_r(1e-5, 3e-5, 1e-4),  # persists 12 months at 25-30 % salt
    salt_s50=_r(20.0, 25.0, 35.0),  # tolerant: 52 % autolysis left at 25 % NaCl
    salt_floor=0.0,
    sources=(
        "Siringan et al. 2006 Food Chem; Siringan et al. 2006 J Sci Food Agric",
        "Lopetcharat & Park 2002 J Food Sci 67:511",
        "Udomsil et al. 2011 J Agric Food Chem 59:8401",
    ),
)
# Fish peptidases (and halophilic bacteria) releasing amino acids from the peptides, per
# unit of fish enzyme activity. est., calibrated to amino N / total N ~0.5-0.6 at 6 months
# at 30-35 °C (Udomsil et al. 2011, 2022).
FISH_PEPTIDASE_K = _r(0.0015, 0.004, 0.012)

CLASSES = (AMYLASE, PROTEASE, PEPTIDASE, FISH)

# Enzyme production while koji grows, by bed temperature (CTMI cardinal values, est.):
# protease is favoured cool, amylase warm. Narahara et al. 1982 (protease higher at
# 30 °C than 38 °C although growth is faster at 38 °C); Kitano et al. 2002 (pepA
# suppressed above 38 °C, amyB not); Kusumoto et al. 2021 (<=30 °C for salty-miso koji,
# 35-40 °C for sweet-miso koji; "protease cannot be enhanced above 40 °C").
AMYLASE_PRODUCTION_T = (15.0, 37.0, 46.0)
PROTEASE_PRODUCTION_T = (15.0, 30.0, 42.0)

GLUCOSE_SHARE = 0.9  # koji amylolysis of rice starch ends mostly as glucose
# Share of protein that becomes soluble (peptides + amino acids); miso reaches 55-60 %
# soluble N at ~90 days (Ohnishi 1982), fish sauce most of the fish N.
SOLUBLE_CEILING = 0.85


def salt_factor(salt_pct: float, s50: FloatArray, floor: float) -> FloatArray:
    """Share of activity left at this water-phase NaCl %: r + (1 - r) / (1 + (s / s50)^2)."""
    return np.asarray(floor + (1.0 - floor) / (1.0 + (salt_pct / s50) ** 2))
