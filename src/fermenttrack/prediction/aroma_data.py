"""Aroma data (increment B): the compound catalogue, template priors and ingredient pools.

Every number is copied from docs/superpowers/specs/2026-10-05-aroma-curation.md (section
in the trailing comment) or marked est.; "# est. (B1)" marks values this increment added,
written back to that spec. Units: thresholds and concentrations in µg/kg; b-terms in mg per
g of substrate fermented (hexose-equivalent engine flux); k_max in 1/d at the organism's
carrying capacity; precursors in µmol/g of fresh ingredient.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from fermenttrack.prediction.priors import Prior


@dataclass(frozen=True)
class AromaCompound:
    key: str
    name: str
    pubchem: str
    chebi: str
    kegg: str
    descriptor: str
    series: tuple[str, ...]
    threshold: Prior | None  # orthonasal detection in water, µg/kg (spec § 3)
    basis: str  # measured | class | est | none
    ph_kind: str  # "acid" | "base" | "" (neutral-fraction correction, D5)
    pka: float | None
    templates: tuple[str, ...]
    status: str  # active | inactive | drop
    conc_only: bool  # no threshold: shown as a concentration, never summed
    p0_pending: bool  # only route is an uncurated ingredient precursor


def _load() -> dict[str, AromaCompound]:
    out = {}
    with (Path(__file__).with_name("aroma_compounds_v1.csv")).open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            thr = (
                Prior(float(r["thr_median"]), float(r["thr_lo"]), float(r["thr_hi"]))
                if r["thr_median"]
                else None
            )
            out[r["key"]] = AromaCompound(
                key=r["key"], name=r["name"], pubchem=r["pubchem"], chebi=r["chebi"],
                kegg=r["kegg"], descriptor=r["descriptor"],
                series=tuple(s for s in r["series"].split(";") if s), threshold=thr,
                basis=r["basis"], ph_kind=r["ph_kind"],
                pka=float(r["pka"]) if r["pka"] else None,
                templates=tuple(s for s in r["templates"].split(";") if s), status=r["status"],
                conc_only=r["conc_only"] == "1", p0_pending=r["p0_pending"] == "1",
            )  # fmt: skip
    return out


COMPOUNDS: dict[str, AromaCompound] = _load()


def _lin(m: float, lo: float, hi: float) -> Prior:
    return Prior(m, lo, hi, "lin")


def _x3(v: float) -> Prior:
    """A value with the spec's x/÷3 spread."""
    return Prior(v, v / 3.0, 3.0 * v)


def _x15(v: float) -> Prior:
    return Prior(v, v / 1.5, 1.5 * v)


PARAMS: dict[str, Prior] = {
    # T1 Ehrlich / fusel (§ 5.1)
    "b_mb_yeast": Prior(0.55, 0.30, 1.0),  # 05:Godillot23, derived
    "share_2mb": _lin(0.20, 0.10, 0.35),  # 02:S3, 04:M2, derived
    "b_mp_yeast": Prior(0.28, 0.18, 0.40),  # 05:Godillot23, derived
    "q10_mp": _lin(2.3, 1.5, 3.0),  # 05:Godillot23, derived; range est.
    "q10_mb": _lin(1.0, 0.8, 1.3),  # 05:Godillot23, derived; range est.
    "mult_nonsacch": Prior(1.0, 0.3, 3.0),  # est. (05:E8, 02:K4)
    "b_pe_yeast": Prior(0.20, 0.05, 0.80),  # 03:S23, 04:M2, derived
    "mult_km_pe": _lin(0.4, 0.3, 0.5),  # 05:Zhang22
    "b_mb_lab": Prior(0.01, 0.002, 0.05),  # 02:S4, derived
    "share_fusel_acid": Prior(0.10, 0.03, 0.30),  # 05:Hazelwood08; range est.
    "share_fusel_ald": Prior(0.01, 0.001, 0.05),  # est.
    "kmax_ald_reduction": Prior(2.0, 0.5, 10.0),  # est.
    "share_met": _lin(0.02, 0.01, 0.04),  # est.
    "share_leu": _lin(0.08, 0.04, 0.12),  # est.
    "share_ile": _lin(0.04, 0.02, 0.07),  # est.
    "share_val": _lin(0.05, 0.03, 0.08),  # est.
    "share_phe": _lin(0.04, 0.02, 0.07),  # est.
    "kmax_at_nonyeast": Prior(0.05, 0.005, 0.5),  # est. (02:J2, 03:S32, 04:G2 route)
    "kmax_met_yeast": Prior(0.05, 0.01, 0.3),  # est. (05:JL26)
    "share_methionol": _lin(0.5, 0.2, 0.9),  # est.
    # T2 esters and medium-chain fatty acids (§ 5.2)
    "ratio_iaac": _lin(0.010, 0.0062, 0.015),  # 05:Godillot23 Table 2
    "ratio_other_acetates": Prior(0.010, 0.003, 0.03),  # est. (05:Rollero17)
    "mult_km_acetates": Prior(1.3, 0.9, 1.9),  # 05:Zhang22
    "b_ea_sc": Prior(0.18, 0.11, 0.32),  # 05:Saerens10, derived
    "b_ea_km": Prior(1.8, 0.5, 24.0),  # 05:Zhang22, 05:Hoffmann21
    "b_ea_lab_hetero": Prior(0.05, 0.005, 0.3),  # est. (02:S4)
    "b_eh": Prior(0.0025, 0.0012, 0.005),  # 05:Godillot23, derived
    "b_eo": Prior(0.0025, 0.0012, 0.005),  # 05:Godillot23, derived
    "b_ed": Prior(0.0005, 0.0001, 0.003),  # est. (05:Saerens10)
    "b_eb": Prior(0.0007, 0.00005, 0.009),  # 05:Saerens10, derived
    "b_e2mb": Prior(0.00003, 0.000005, 0.0002),  # 02:S3, derived (also 2-methylpropanoate)
    "b_eb_lab": Prior(0.001, 0.0001, 0.01),  # 03:S10, derived-est.
    "q10_ethyl_esters": _lin(1.0, 0.7, 1.4),  # § 9.2 conflict
    "b_mcfa": Prior(0.005, 0.0005, 0.05),  # est.
    "excr_c8": _lin(0.60, 0.54, 0.68),  # 05:Saerens10
    "excr_c10": _lin(0.12, 0.08, 0.17),  # 05:Saerens10
    # T3 acetaldehyde (§ 5.3)
    "b_acetaldehyde_yeast": Prior(2.0, 0.4, 42.0),  # 05:LiMira11
    "b_acetaldehyde_km": Prior(2.0, 0.4, 24.0),  # 05:Hoffmann21
    "b_acetaldehyde_lab": Prior(0.5, 0.05, 3.0),  # 03:S20, 03:S23, derived
    "kmax_acetaldehyde_yeast": Prior(1.0, 0.2, 5.0),  # 05:LiMira11; magnitude est.
    # T4, sugar route only (§ 5.4; lacto has no citrate pool, § 6.1)
    "b_acetoin_lab": Prior(2.0, 0.2, 23.0),  # 03:S31: 0.002 g/g sugar
    "kmax_acetoin_bdo": Prior(0.2, 0.02, 1.0),  # est. (03:S19 storage check)
    # T5 chemical esterification and hydrolysis (§ 5.5), k_hyd in 1e-9 /s at pH 3.58, ~21 °C
    "khyd_iaac": _x15(32.6),  # 05:RameyOugh80 Table IV
    "khyd_ibac": _x15(40.0),
    "khyd_peac": _x15(46.6),
    "khyd_eb": _x15(18.2),
    "khyd_eh": _x15(25.8),
    "khyd_eo": _x15(44.5),
    "khyd_other": Prior(20.0, 7.0, 60.0),  # est.
    "khyd_n": _lin(0.8, 0.3, 1.0),  # 05:RameyOugh80, derived
    "khyd_q10": _lin(2.1, 1.8, 2.5),  # 05:RameyOugh80 Table II, derived
    "ester_k": Prior(4.0, 1.0, 16.0),  # 05:RameyOugh80 (Berthelot)
    # T6 glucosinolates (§ 5.6)
    "gsl_release": Prior(0.7, 0.3, 1.5),  # 1/d at 20 °C; est. (05:Palani16, 05:MV09)
    "gsl_volatile_share": Prior(0.05, 0.005, 0.3),  # 05:CiskaPathak04, derived
    "itc_fraction": _lin(0.5, 0.1, 0.9),  # 05:Puc25b, 05:Hanschen24
    "itc_loss": Prior(0.16, 0.08, 0.4),  # 1/d at 15 °C; 03:S10, derived
    # T7 sulfur (§ 5.7)
    "dmds_burst_decay": Prior(1.1, 0.5, 2.5),  # 1/d at 15 °C; 03:S10, derived
    "dmts_burst_decay": Prior(1.5, 0.7, 3.0),  # 1/d at 15 °C; 03:S10, derived
    "b_dmds_lab": Prior(0.002, 0.0002, 0.02),  # 03:S1 Table 5, derived
    "b_dmts_lab": Prior(0.001, 0.0001, 0.01),  # 03:S1 Table 5, derived
    "dms_per_dmds": Prior(0.3, 0.05, 1.0),  # mol/mol; est. (03:S9)
    "mesh_oxidation": Prior(5.0, 1.0, 20.0),  # 1/d; est. (03:S10)
    # T8 vegetables (§ 5.8, § 5.9)
    # 1/d at 30 °C with q10_default (est. (B2)); 05:Engels22, rate est. Median = the 02:K1
    # kombucha check (0.17/d at 30 °C), which with the Q10 also keeps kimchi hexanal within
    # x/÷3 of t0 at 15 °C (test 22) and cucumber hexanal in 4-114 µg/kg (test 24). B1 had
    # 0.06 without a Q10 (the § 10.3 kimchi/kombucha conflict).
    "kmax_lipid_reduction": Prior(0.17, 0.05, 1.5),
    "brine_aldehyde_loss": Prior(0.9, 0.5, 2.0),  # 1/d; 03:S13, derived
    "hexenol_release": Prior(0.3, 0.1, 1.0),  # 1/d; est., shaped to 03:S10
    "hexenol_loss": Prior(0.3, 0.1, 1.0),  # 1/d; est., shaped to 03:S10
    "loss_linalool": Prior(0.05, 0.01, 0.2),  # 1/d at 30 °C; est. (02:K1)
    # T12 volatility (§ 5.12) and shared
    "kaw_eta": _lin(0.35, 0.15, 0.7),  # 05:Godillot23, derived
    "kaw_tfactor": _lin(2.1, 1.9, 2.3),  # per +10 °C; 05:Sander23, derived
    "kaw_standin": Prior(1.0, 0.1, 10.0),  # class stand-in x/÷10, est.; shared per member
    "q10_default": Prior(2.0, 1.5, 3.0),  # est.
    "matrix": Prior(1.0, 0.333, 3.0),  # § 3: shared matrix factor, est.
}

# K_aw (air/water, dimensionless) at 25 °C, neutral form (§ 5.12, 05:Sander23)
KAW: dict[str, float] = {
    "acetaldehyde": 3.1e-3, "ethyl_acetate": 6.2e-3, "isoamyl_acetate": 1.9e-2,
    "ethyl_butanoate": 1.6e-2, "ethyl_hexanoate": 2.1e-2, "ethyl_octanoate": 2.4e-2,
    "ethyl_lactate": 2.4e-5, "diacetyl": 5.5e-4, "methylbutanol_3": 4.9e-4,
    "methylpropanol_2": 4.9e-4, "phenylethanol_2": 2.4e-5, "methylbutanal_3": 1.7e-2,
    "hexanal": 9.0e-3, "e2_nonenal": 7.0e-3, "octen3ol": 2.1e-3, "allyl_itc": 1.9e-2,
    "methanethiol": 0.11, "dms": 7.6e-2, "dmds": 7.0e-2, "dmts": 3.4e-2, "linalool": 2.0e-3,
    "trimethylamine": 4.1e-3, "acetic": 1.0e-5,
}  # fmt: skip

_CLASS_MEMBERS: dict[str, tuple[str, ...]] = {  # § 5.12 class stand-ins (x/÷10)
    "ethyl_hexanoate": (  # esters
        "phenylethyl_acetate", "isobutyl_acetate", "ethyl_decanoate",
        "ethyl_2methylbutanoate", "ethyl_2methylpropanoate", "s_methyl_thioacetate",
    ),
    "methylbutanol_3": (  # alcohols
        "methylbutanol_2", "methionol", "z3_hexenol", "octanol_3", "ethanol", "butanediol_23",
    ),
    "hexanal": (  # aldehydes (and 2-pentylfuran, as hydrophobic)
        "methylbutanal_2", "methylpropanal_2", "phenylacetaldehyde", "methional",
        "z3_hexenal", "nonanal", "z4_heptenal", "pentylfuran_2",
    ),
    "diacetyl": (  # ketones
        "pentanedione_23", "acetoin", "octen3one", "octanone_3", "heptanone_2", "nonanone_2",
    ),
    "acetic": (  # acids
        "methylbutanoic_3", "methylbutanoic_2", "methylpropanoic_2", "hexanoic", "octanoic",
        "decanoic", "butanoic",
    ),
    "linalool": (  # terpenoids
        "geraniol", "citronellol", "methyl_salicylate", "damascenone", "ionone_beta",
        "geranial", "neral", "zingiberene", "carvone", "limonene",
    ),
    "phenylethanol_2": (  # furanones, lactones, phenols, pyrazines, maltol
        "hemf", "furaneol", "norfuraneol", "maltol", "sotolon", "decalactone_delta",
        "dodecalactone_delta", "vinylguaiacol_4", "vinylphenol_4", "ethylguaiacol_4",
        "ethylphenol_4", "dimethylpyrazine_25", "trimethylpyrazine", "acetylpyrroline_2",
    ),
    "allyl_itc": ("butenyl_itc", "allyl_cyanide", "mtb_itc"),  # est. (B1): ITCs, nitriles
    "dmds": ("diallyl_disulfide", "allyl_methyl_disulfide"),  # est. (B1): dropped disulfides
}  # fmt: skip
KAW_CLASS: dict[str, str] = {m: k for k, ms in _CLASS_MEMBERS.items() for m in ms}

MW: dict[str, float] = {  # g/mol
    "methylbutanol_3": 88.15, "methylbutanol_2": 88.15, "methylpropanol_2": 74.12,
    "phenylethanol_2": 122.16, "methionol": 106.19, "methylbutanal_3": 86.13,
    "methylbutanal_2": 86.13, "methylpropanal_2": 72.11, "phenylacetaldehyde": 120.15,
    "methional": 104.17, "methylbutanoic_3": 102.13, "methylbutanoic_2": 102.13,
    "methylpropanoic_2": 88.11, "isoamyl_acetate": 130.19, "isobutyl_acetate": 116.16,
    "phenylethyl_acetate": 164.20, "ethyl_acetate": 88.11, "ethyl_lactate": 118.13,
    "acetic": 60.05, "lactic": 90.08, "ethanol": 46.07, "methionine": 149.21,
    "leucine": 131.17, "isoleucine": 131.17, "valine": 117.15, "phenylalanine": 165.19,
    "acetoin": 88.11, "butanediol_23": 90.12, "allyl_itc": 99.15, "allyl_cyanide": 67.09,
    "butenyl_itc": 113.18, "methanethiol": 48.11, "dms": 62.13, "dmds": 94.20,
    "dmts": 126.26,
}  # fmt: skip

PRECURSOR_LABEL: dict[str, str] = {
    "@sinigrin": "sinigrin (a glucosinolate)",
    "@gluconapin": "gluconapin (a glucosinolate)",
    "@smcso": "S-methylcysteine sulfoxide",
    "@hexenol_residual": "green-leaf volatile precursors",
}

# Ingredient -> initial compound (µg/kg of ingredient) or "@" precursor (µmol/g fresh
# weight; @hexenol_residual in µg/kg). Names as in seed_data; the napa cabbage and the
# cucumber are stand-ins until the catalogue has those ingredients (§ 6.1, § 6.2).
AROMA_INGREDIENTS: dict[str, dict[str, Prior]] = {
    "Cabbage": {  # white cabbage, raw, shredded and dry-salted at t0
        # 03:S10 Table 1, napa raw as stand-in (§ 6.2)
        "hexanal": _x3(11.7), "z3_hexenal": _x3(12.9), "z3_hexenol": _x3(1490.0),
        "dmds": Prior(50.0, 10.0, 300.0), "dmts": Prior(50.0, 10.0, 500.0),  # § 5.7, est.
        "@sinigrin": Prior(1.0, 0.3, 3.0),  # 05:Fabjan26, derived
        # est. (B1): 1.0 (0.2-4.0) µmol/g DM x dry matter 0.09 (0.05-0.17), extremes multiplied
        "@gluconapin": Prior(0.09, 0.01, 0.68),
        "@smcso": Prior(5.7, 3.2, 10.2),  # 05:Friedrich22
    },
    "Napa cabbage (salted)": {  # kimchi t0, after salting (03:S10 Tables 1, 3; semi)
        "hexanal": _x3(1.9), "z3_hexenol": _x3(10.4), "methional": _x3(0.3),
        "phenylacetaldehyde": _x3(6.6), "acetoin": _x3(74.0), "butanediol_23": _x3(3.7),
        "butenyl_itc": _x3(212.0), "dmds": _x3(205.0), "dmts": _x3(425.0),
        # est. (B1): total GSL 12.5 (2.7-57.9) µmol/g DM (05:Kim22) x gluconapin share 0.3
        # (0.1-0.6) x dry matter 0.09 (0.05-0.17), extremes multiplied
        "@gluconapin": Prior(0.34, 0.013, 5.9),
        "@smcso": Prior(5.7, 3.2, 10.2),  # 05:Friedrich22 (napa est. same)
        # est. (B1): raw-cabbage (Z)-3-hexenol that salting removed from the free pool,
        # released at hexenol_release (§ 5.8 "shaped to 03:S10")
        "@hexenol_residual": _x3(1490.0),
    },
    "Cucumber": {  # fresh (03:S13 Table 2; § 4.5)
        "hexanal": _x3(29.0), "linalool": _x3(4.6), "e2_nonenal": Prior(5.0, 1.0, 25.0),
    },
}  # fmt: skip

DEFAULT_INGREDIENTS: dict[str, dict[str, float]] = {
    "lacto_ferment": {"Cabbage": 0.98},  # no recipe logged: a 2 % dry-salted sauerkraut
}

AROMA_TYPES = frozenset({"lacto_ferment"})  # ferment types with aroma templates

# Per-member strain flags (Bernoulli): the chance that the member's strain has the trait
FLAGS: dict[str, float] = {
    "pof_yeast": 0.5,  # Pof+ S. cerevisiae decarboxylates ferulic acid; 05:Coghe04, share est.
    "pad_lp": 0.12,  # padA+ L. plantarum: 6 of 50 kimchi isolates (05:Rosimin15)
}

_CAL, _REP = "calibrated", "reported"
# type -> compound -> (tier, anchor, sources) (§ 4)
EVIDENCE: dict[str, dict[str, tuple[str, str, tuple[str, ...]]]] = {
    "lacto_ferment": {  # § 4.5
        "butenyl_itc": (_CAL, "semi", ("03:S10", "03:S8")),
        "dmds": (_CAL, "semi", ("03:S10", "03:S1")),
        "dmts": (_CAL, "semi", ("03:S10", "03:S11", "03:S1")),
        "ethyl_butanoate": (_CAL, "semi", ("03:S10",)),
        "ethyl_2methylbutanoate": (_CAL, "semi", ("03:S10",)),
        "hexanal": (_CAL, "semi", ("03:S10", "03:S13")),
        "z3_hexenal": (_CAL, "semi", ("03:S10",)),
        "z3_hexenol": (_CAL, "semi", ("03:S10",)),
        "methional": (_CAL, "semi", ("03:S10", "03:S11")),
        "phenylacetaldehyde": (_CAL, "semi", ("03:S10", "03:S11")),
        "e2_nonenal": (_CAL, "shape", ("03:S13",)),
        "linalool": (_CAL, "abs", ("03:S13",)),
        "allyl_itc": (_REP, "abs", ("03:S1", "03:S3")),
        "allyl_cyanide": (_REP, "presence", ("03:S4", "03:S7")),
        "methanethiol": (_REP, "presence", ("03:S2", "03:S9")),
        "dms": (_REP, "presence", ("03:S2", "03:S9")),
        "acetaldehyde": (_REP, "presence", ("03:S2", "03:S8", "03:S9")),
        "ethyl_acetate": (_REP, "presence", ("03:S2", "03:S8", "03:S9")),
        "ethyl_lactate": (_REP, "presence", ("03:S2", "03:S8", "03:S9")),
        "diacetyl": (_REP, "presence", ("03:S10", "03:S11")),
        "acetoin": (_REP, "semi", ("03:S10",)),
        "butanediol_23": (_REP, "semi", ("03:S10",)),
        "methylbutanol_3": (_REP, "presence", ("03:S13",)),
        "methylbutanol_2": (_REP, "presence", ("03:S13",)),
        "nonanal": (_REP, "presence", ("03:S13",)),
        "geraniol": (_REP, "presence", ("03:S13",)),
        "pentanedione_23": ("plausible", "", ()),
        "carvone": ("plausible", "", ()),
        "geranial": ("plausible", "", ()),
        "neral": ("plausible", "", ()),
        "vinylguaiacol_4": ("plausible", "", ()),
        "acetic": ("engine", "abs", ("forecast",)),
        "ethanol": ("engine", "abs", ("forecast",)),
    },
}
