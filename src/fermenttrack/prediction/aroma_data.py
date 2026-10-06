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
    # T4 sugar route through α-acetolactate (§ 5.4, D3)
    "al_decay": Prior(0.10, 0.05, 0.20),  # 1/h at 30 °C; 03:S30 Fig. 1, derived
    "al_q10": Prior(2.0, 1.5, 3.0),  # est. (05:E3)
    "share_al_ox": _lin(0.05, 0.02, 0.20),  # 03:S30, derived lower bound; hi est.
    "pd_per_diacetyl": Prior(0.3, 0.05, 1.0),  # mol/mol; est. (02:J2)
    # 1/d; yeast and Leuconostoc (03:S27, 03:S19; rate est.), lactobacilli alike: est. (B2)
    "kmax_diacetyl_red": Prior(2.0, 0.5, 10.0),
    "kmax_diacetyl_red_lc": Prior(0.05, 0.005, 0.3),  # 1/d, Lactococcus; est. (03:S30)
    # T4 citrate (§ 5.4, D3, D4)
    "share_cit_lc": _lin(0.5, 0.1, 1.0),  # citrate-active share of Lactococcus; est.
    "kmax_citrate": Prior(12.0, 5.0, 36.0),  # 1/d at 30 °C, cit+ LAB; 03:S30, derived order
    "share_c4_lc": _lin(0.4, 0.3, 0.5),  # C4 share of citrate pyruvate, Lactococcus; 05:Verhue91
    "share_c4_leuc": _lin(0.7, 0.3, 1.0),  # same, Leuconostoc; 05:Cogan81 (hi); median est.
    # Milk fat lactones (§ 5.8): fat-bound precursor = x times the free lactone, released
    "lactone_precursor_x": Prior(5.0, 1.0, 20.0),  # est. (03:S23 shape)
    # 1/d; est. (03:S23 shape). Calibrated 2026-10-06 (0.7 -> 0.3): curation tests 30
    # (kefir δ-dodecalactone 48 h / 24 h >= 1.3) and 37 (cheese lactones within x/÷3 of milk)
    "lactone_release": Prior(0.3, 0.1, 2.4),
    # T9 tea terpenoids (§ 5.9): bound glycosides released by yeast and acid; losses at 30 °C
    # (q10_default)
    "kmax_bound_release": Prior(0.1, 0.02, 0.5),  # 1/d, yeast beta-glucosidase; est. (02:K2, K4)
    "acid_bound_release": Prior(0.002, 0.0005, 0.01),  # 1/d; est. (05:Yan24)
    "split_linalool": _lin(0.4, 0.2, 0.6),  # of the released terpenes; est. (05:Zhou26tea)
    "split_geraniol": _lin(0.3, 0.1, 0.5),  # est.; methyl salicylate takes the rest
    "loss_geraniol": Prior(0.03, 0.01, 0.1),  # 02:K1, derived
    "loss_limonene": Prior(0.15, 0.07, 0.5),  # 02:K1, derived
    "loss_msal_ionone": Prior(0.3, 0.15, 1.0),  # methyl salicylate, beta-ionone; 02:K1, derived
    "loss_damascenone_citronellol": Prior(0.05, 0.01, 0.3),  # est.
    # T10 hydroxycinnamic acids (§ 5.10, § 6.1)
    # free share of flour ferulic acid: 05:Boudaoud21 § 3.2.2 (PMC8116856), free = 0.5 % of
    # total in wheat bran, "does not exceed 0.5-1 % in cereals"; range est. (B2). § 6.1's
    # 0.03 divided bran free acid by sourdough total acid (two matrices).
    "share_ferulic_free": Prior(0.005, 0.003, 0.01),
    "kmax_ferulic_release": Prior(0.5, 0.1, 2.0),  # 1/d, yeast; rate est. (05:Coghe04)
    "kmax_ferulic_decarb": Prior(1.0, 0.2, 5.0),  # 1/d; 05:Coghe04, 05:Rosimin15, rate est.
    "share_vinyl": _lin(0.3, 0.05, 0.8),  # of L. plantarum's conversion; 05:Rogozinska21
    "loss_4vg": Prior(0.01, 0.002, 0.05),  # 1/d; est.
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
    # T11 slow chemistry (§ 5.11)
    "strecker_rate": Prior(0.5, 0.05, 5.0),  # µg aldehyde / g free amino acid / d, 25 °C; est.
    "q10_strecker": Prior(2.5, 1.5, 4.0),  # est. (05:E18)
    "strecker_oxidation": Prior(0.002, 0.0005, 0.01),  # 1/d aldehyde -> acid; 04:G1, derived-est.
    # HEMF precursor formation at the start of the mash (HEMF-eq µg/kg/d), then following the
    # koji amylase activity: est. (B4). Median set on the 04:M9 base case (curation test 38,
    # run with T. halophilus for the pH drop): a 17 000 µg/kg peak at 30 °C; range x/÷10 est.
    "hemf_formation": Prior(7300.0, 730.0, 73000.0),
    "hemf_precursor_decay": Prior(0.05, 0.02, 0.15),  # 1/d at 30 °C; est. (04:M9, 04:M1)
    "kmax_hemf_conversion": Prior(0.1, 0.03, 0.3),  # 1/d, Z. rouxii; est. (04:M9, 04:M10)
    "hemf_loss": Prior(0.031, 0.02, 0.045),  # 1/d at 30 °C; 04:M9 Table 3, derived
    "q10_hemf": Prior(3.9, 2.5, 6.0),  # 04:M9 Table 3, derived
    "furaneol_formation": Prior(50.0, 15.0, 150.0),  # µg/kg/d at 30 °C, barley; 04:M1, derived
    "q10_furaneol": Prior(2.4, 2.0, 4.0),  # 04:M1 Table 3, derived
    "kmax_norfuraneol_uptake": Prior(0.2, 0.1, 0.5),  # 1/d, Z. rouxii; 04:M1 Fig. 4, derived
    "maltol_loss": Prior(0.015, 0.007, 0.03),  # 1/d; 04:M2 Table 2, derived (app.)
    # Fish lipid oxidation (§ 5.8, garum): zero-order sources per kg of fish (est. (B4)) at
    # 25 °C with q10_default, and a slow loss; est. (no fish-lipid pool curated)
    **{f"fish_lipid:{k}": Prior(1.0, 0.1, 10.0) for k in (
        "hexanal", "nonanal", "pentylfuran_2", "z4_heptenal", "octen3ol",
    )},  # fmt: skip
    "fish_lipid_loss": Prior(0.005, 0.001, 0.02),  # 1/d; est.
    # A. oryzae a-terms (§ 5.8, § 5.2), a in mg per g mycelium made
    "a_octenol": Prior(0.02, 0.002, 0.2),  # 1-octen-3-ol; est. (05:Guneser17 order)
    "split_octanone": Prior(0.4, 0.1, 1.0),  # mol/mol of 1-octen-3-ol; est. (05:Miyamoto14)
    "split_octanol": Prior(0.2, 0.05, 0.6),  # est.
    "split_octenone": Prior(0.05, 0.01, 0.2),  # est.
    "a_methylketone": Prior(0.005, 0.0005, 0.05),  # each of 2-heptanone, 2-nonanone; est.
    "a_mould_acetates": Prior(0.01, 0.001, 0.1),  # ethyl, isoamyl acetate; est. (02:J1)
    "kmax_fungal_esterase": Prior(0.5, 0.1, 2.0),  # 1/d, as growth stops; est.
    # Acetic acid bacteria (§ 5.1, § 5.3, § 5.4, D11), k_max 1/d
    "kmax_aab_fusel": Prior(0.1, 0.02, 0.5),  # 02:K2, 02:V3, derived (with the fusel acid)
    "kmax_aab_pe": _lin(0.005, 0.0, 0.02),  # 2-phenylethanol, a poor substrate; 02:V1, V3, V4
    "kmax_aab_acetaldehyde": Prior(5.0, 1.0, 20.0),  # est. (02:V1, 02:V4)
    "kmax_aab_bdo": Prior(0.5, 0.1, 2.0),  # 2,3-butanediol -> acetoin; est. (02:V1, 02:V12)
    # T12 open surface (§ 5.12): k0 = k_surf x K_aw, 1/d
    "k_surf_vinegar": Prior(20.0, 5.0, 80.0),  # surface culture; 02:V3, derived
    "k_surf_koji": Prior(50.0, 10.0, 200.0),  # koji bed; est. (05:E19)
    "k_surf_kombucha": Prior(10.0, 2.0, 50.0),  # est. (05:E19)
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
    "dmts": 126.26, "diacetyl": 86.09, "pentanedione_23": 100.12, "vinylguaiacol_4": 150.17,
    "ferulic": 194.18, "octen3ol": 128.21, "octanone_3": 128.21, "octanol_3": 130.23,
    "octen3one": 126.20, "heptanone_2": 114.19, "nonanone_2": 142.24, "hemf": 142.15,
    "furaneol": 128.13, "norfuraneol": 114.10, "maltol": 126.11,
}  # fmt: skip

PRECURSOR_LABEL: dict[str, str] = {
    "@sinigrin": "sinigrin (a glucosinolate)",
    "@gluconapin": "gluconapin (a glucosinolate)",
    "@smcso": "S-methylcysteine sulfoxide",
    "@hexenol_residual": "green-leaf volatile precursors",
    "@ferulic": "ferulic acid",
    "@citrate": "citrate",
    "@tea_bound": "bound terpenes (glycosides)",
}
# precursors held as µg/kg (mass) rather than µmol/g of fresh ingredient
MASS_PRECURSORS = frozenset({"@hexenol_residual", "@tea_bound"})

# Ingredient -> initial compound (µg/kg of ingredient) or "@" precursor (µmol/g fresh
# weight; @hexenol_residual in µg/kg). Names as in seed_data; the napa cabbage and the
# cucumber are stand-ins until the catalogue has those ingredients (§ 6.1, § 6.2).
# Wine/cider base -> vinegar (§ 6.2, D11), µg per kg of a 94 g/kg-ethanol base: 05:Saerens10
# Table 2 (esters; medians at geometric midpoints), 05:Godillot23 (fusel alcohols),
# 05:LiMira17 (acetaldehyde), 2-phenylethanol = T1 b x 200 g/L (derived), 2,3-butanediol est.
# The 3- + 2-methylbutanol sum 110 000 (85 000-145 000) is split with § 5.1's 2-methylbutanol
# share 0.20 (0.10-0.35), extremes multiplied: derived (B3).
_WINE: dict[str, Prior] = {
    "ethyl_acetate": Prior(40_000.0, 22_500.0, 63_500.0),
    "isoamyl_acetate": Prior(600.0, 100.0, 3_400.0),
    "isobutyl_acetate": Prior(100.0, 10.0, 1_600.0),
    "phenylethyl_acetate": Prior(300.0, 50.0, 18_500.0),
    "ethyl_butanoate": Prior(130.0, 10.0, 1_800.0),
    "ethyl_hexanoate": Prior(300.0, 30.0, 3_400.0),
    "ethyl_octanoate": Prior(400.0, 50.0, 3_800.0),
    "ethyl_decanoate": Prior(100.0, 10.0, 2_100.0),
    "methylbutanol_3": Prior(88_000.0, 55_250.0, 130_500.0),
    "methylbutanol_2": Prior(22_000.0, 8_500.0, 50_750.0),
    "methylpropanol_2": Prior(55_000.0, 35_000.0, 80_000.0),
    "acetaldehyde": Prior(24_000.0, 14_000.0, 34_000.0),
    "phenylethanol_2": Prior(40_000.0, 10_000.0, 160_000.0),
    "butanediol_23": Prior(500_000.0, 100_000.0, 1_500_000.0),
}
BASE_ETHANOL = 94.0  # g/kg ethanol of the base the § 6.2 pools describe (200 g/L x 0.47)
# Alcoholic bases: pools scale with the batch's starting ethanol (/ BASE_ETHANOL), shared by
# mass between the logged bases (§ 6.2: "scale every value by ethanol0 / 94")
ALCOHOL_BASES = frozenset({"Red wine", "White wine", "Hard cider"})

# Flour (§ 6.2), re-derived (B2) with the 2026-10-06 threshold medians: the spec's priors
# were OAV > 100 in rye flour (02:S2) x the old medians (hexanal 3.4, (E)-2-nonenal 0.22,
# methional 0.29); each prior is scaled by new/old median (2.4/3.4, 0.69/0.22, 0.43/0.29).
# Ferulic acid: 0.30 (0.18-0.52) mg/g DM (05:Boudaoud21 Table 3) x flour dry matter 0.87
# (sourdough.FLOURS, 13 % water) / 194.18 g/mol, in µmol/g flour: derived (B2). One pool
# for every flour: no opened source separates white, whole-wheat and rye flour (est.).
_FLOUR: dict[str, Prior] = {
    "hexanal": Prior(353.0, 106.0, 1412.0),
    "e2_nonenal": Prior(125.0, 63.0, 470.0),
    "methional": Prior(74.0, 43.0, 445.0),
    "@ferulic": Prior(1.34, 0.81, 2.33),
}

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
    "White wheat flour": _FLOUR, "Whole wheat flour": _FLOUR, "Rye flour": _FLOUR,
    "Red wine": _WINE, "White wine": _WINE, "Hard cider": _WINE,
    # cooked rice, per kg of logged rice (assumed steamed; est. (B3)): hexanal 53.2-71.6 µg/kg
    # (Lai 2026 Foods 15:356 Table 1, PMC12840958; IS semi), geometric mid, x/÷3 for semi
    "White rice": {"hexanal": Prior(62.0, 21.0, 190.0)},
    # Cooked substrates of miso (§ 6.2), per kg of the logged ingredient. App. values are
    # lower bounds (porous-polymer traps, 04:M9 p. 162): hi allows x10 for recovery, est. (B4)
    "Soybeans": {
        "maltol": Prior(2_980.0, 990.0, 30_000.0),  # 04:M2 Table 2 (cooked soybean, app.)
        "furaneol": Prior(30.0, 10.0, 300.0),  # 04:M2 (app.)
        # derived (B4): 8 000-15 000 per kg barley-miso mash at the end of mashing (04:M1
        # Fig. 4) / the soybean share 0.45, widened x/÷1.5 for that share
        "norfuraneol": Prior(24_400.0, 11_900.0, 50_000.0),
    },
    "Pearl barley": {
        # derived (B4): barley-miso mash 28 000 (3 400-59 000) (04:M1) / barley share 0.44
        "maltol": Prior(64_000.0, 7_700.0, 134_000.0),
        # est. (B4): 14-22 (app.) per kg barley/soybean miso (04:M10) / 0.44, hi x10
        "dimethylpyrazine_25": Prior(40.0, 13.0, 400.0),
        "trimethylpyrazine": Prior(40.0, 13.0, 400.0),
    },
    # tea leaves (§ 6.2), per kg of leaves: derived (B5) from the per-batch values at the
    # default 5 g/kg (x200). Free: linalool 10 (3-30) µg/kg batch (02:K4 anchor); the others as
    # 02:K1's ratios to linalool, each x/÷4. Bound glycosides 105-366 µg/g (05:Zhou26tea).
    **{tea: {
        "linalool": Prior(2_000.0, 600.0, 6_000.0),
        "geraniol": Prior(500.0, 125.0, 2_000.0),
        "methyl_salicylate": Prior(480.0, 120.0, 1_920.0),
        "ionone_beta": Prior(80.0, 20.0, 320.0),
        "limonene": Prior(540.0, 135.0, 2_160.0),
        "hexanal": Prior(90.0, 22.5, 360.0),
        "nonanal": Prior(320.0, 80.0, 1_280.0),
        "@tea_bound": Prior(196_000.0, 105_000.0, 366_000.0),
    } for tea in ("Black tea leaves", "Green tea leaves", "Black/green tea")},
    # whole milk, pasteurised (§ 6.2; 03:S34 Table 2, external standard; each x/÷2) and its
    # citrate (D4: 9.0 (6.3-11.7) mmol/kg, 05:Grelet16, 05:Chen24)
    "Milk": {
        "hexanal": Prior(51.3, 25.65, 102.6), "diacetyl": Prior(9.7, 4.85, 19.4),
        "butanoic": Prior(1_094.0, 547.0, 2_188.0), "octanoic": Prior(1_037.0, 518.5, 2_074.0),
        "decanoic": Prior(380.0, 190.0, 760.0),
        "decalactone_delta": Prior(138.0, 69.0, 276.0),
        "dodecalactone_delta": Prior(844.0, 422.0, 1_688.0),
        "@citrate": Prior(9.0, 6.3, 11.7, "lin"),
    },
    # fish: no initial pools curated; its lipids oxidise (FISH_LIPID sources, § 5.8)
    "Anchovies": {}, "Mackerel": {}, "Fish": {},
}  # fmt: skip
# Miso (§ 5.11): HEMF needs soybean; furaneol forms in barley mashes. The default mash
# (koji ratio 10: equal soybean and koji grain, 11 % salt) is the reference: est. (B4)
FISH = frozenset({"Anchovies", "Mackerel", "Fish"})
FISH_LIPID = ("hexanal", "nonanal", "pentylfuran_2", "z4_heptenal", "octen3ol")
SOY = frozenset({"Soybeans"})
SOY_REF = 0.45
BARLEY_REF = 0.44
HEMF_PH = 5.6  # Z. rouxii converts the precursor only below this pH (04:M10)
# Citrate uptake (§ 5.4): cardinal pH (optimum 5.5-6.0, 05:Starrenburg91; ends est. (B5)), and
# Leuconostoc takes up citrate only once the hexoses fall below 10 mM (05:Cogan81)
CITRATE_PH = (4.0, 5.75, 8.0)
LEUC_SUGAR_GATE = 1.8  # g/kg hexoses
# Compounds the koji carries into a mash, per kg (route: ingredient "Koji"):
# 04:M10 20-76 µg/kg (app.), geometric midpoint, x/÷3 below, x3 above the max: est. (B4)
KOJI_CARRY: dict[str, dict[str, Prior]] = {"miso": {"octen3ol": Prior(40.0, 13.0, 230.0)}}

DEFAULT_INGREDIENTS: dict[str, dict[str, float]] = {
    "lacto_ferment": {"Cabbage": 0.98},  # no recipe logged: a 2 % dry-salted sauerkraut
    # derived (B2): the profile's typical levain has 370 g/kg starch = 536 g T65 flour (69 %)
    "sourdough": {"White wheat flour": 0.54},
    # derived (B3): 55 g/kg ethanol / 103 g/kg in white wine (FDC); only the ethanol counts
    "vinegar": {"White wine": 0.53},
    "koji": {"White rice": 1.0},  # steamed rice is the whole bed
    "miso": {"Soybeans": 0.45, "White rice": 0.44},  # est. (B4): koji ratio 10, 11 % salt
    # derived (B4): typical recipe 140 g/kg protein / 20.4 % anchovy protein (FDC)
    "garum": {"Anchovies": 0.69},
    "kefir": {"Milk": 0.97},  # 3 % grains (profile note: 2-5 %); est. (B5)
    "kombucha": {"Black tea leaves": 0.005},  # § 6.1: 5 g/kg tea (est.)
    "cheese": {"Milk": 1.0},
}

AROMA_TYPES = frozenset({
    "lacto_ferment", "sourdough", "vinegar", "koji", "miso", "garum", "kefir", "cheese",
    "kombucha",
})  # fmt: skip
# Open vessels: ferment type -> its surface-loss parameter (§ 5.12); closed jars and dough: 0
K_SURF: dict[str, str] = {
    "vinegar": "k_surf_vinegar", "koji": "k_surf_koji", "kombucha": "k_surf_kombucha",
}

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
    "sourdough": {  # § 4.3 (dough before baking)
        "methylbutanal_3": (_CAL, "shape", ("02:S1", "02:S2")),
        "methylbutanal_2": (_CAL, "shape", ("02:S2",)),
        "methylbutanol_3": (_CAL, "abs", ("02:S2", "02:S3")),
        "diacetyl": (_CAL, "shape", ("02:S2",)),
        "hexanal": (_CAL, "abs", ("02:S1", "02:S3")),
        "e2_nonenal": (_CAL, "shape", ("02:S1",)),
        "methional": (_REP, "abs", ("02:S2",)),
        "methylbutanol_2": (_REP, "abs", ("02:S3",)),
        "methylpropanol_2": (_REP, "abs", ("02:S3", "02:S4")),
        "phenylethanol_2": (_REP, "abs", ("02:S3",)),
        "ethyl_acetate": (_REP, "abs", ("02:S3", "02:S4", "02:S6", "02:S9")),
        "isoamyl_acetate": (_REP, "abs", ("02:S3",)),
        "ethyl_butanoate": (_REP, "abs", ("02:S3",)),
        "ethyl_decanoate": (_REP, "abs", ("02:S3",)),
        "ethyl_hexanoate": (_REP, "abs", ("02:S3",)),
        "ethyl_octanoate": (_REP, "abs", ("02:S3",)),
        "ethyl_2methylbutanoate": (_REP, "abs", ("02:S3",)),
        "ethyl_2methylpropanoate": (_REP, "abs", ("02:S3",)),
        "methionol": (_REP, "presence", ("02:S5",)),
        "methylpropanoic_2": (_REP, "presence", ("02:S5",)),
        "methylbutanoic_2": (_REP, "presence", ("02:S5",)),
        "phenylethyl_acetate": (_REP, "presence", ("02:S5",)),
        "isobutyl_acetate": (_REP, "presence", ("02:S5",)),
        "ethyl_lactate": (_REP, "presence", ("02:S5",)),
        "acetaldehyde": (_REP, "presence", ("02:S5",)),
        "methylbutanoic_3": (_REP, "presence", ("02:S2", "02:S7")),
        "hexanoic": (_REP, "presence", ("02:S4", "02:S5")),
        "octanoic": (_REP, "presence", ("02:S4", "02:S5")),
        "acetoin": (_REP, "presence", ("02:S4", "02:S5")),
        "nonanal": (_REP, "presence", ("02:S5",)),
        "pentylfuran_2": (_REP, "presence", ("02:S5",)),
        "octen3ol": (_REP, "presence", ("02:S5",)),
        "octanol_3": (_REP, "presence", ("02:S5",)),
        "limonene": (_REP, "presence", ("02:S5",)),
        "heptanone_2": (_REP, "presence", ("02:S5",)),
        "butanoic": (_REP, "presence", ("02:S5",)),
        "octen3one": (_REP, "presence", ("02:S1", "02:S2")),
        "sotolon": (_REP, "presence", ("02:S1", "02:S2")),
        **{k: ("plausible", "", ()) for k in (
            "methylpropanal_2", "phenylacetaldehyde", "decanoic", "pentanedione_23",
            "butanediol_23", "z3_hexenal", "z3_hexenol", "z4_heptenal", "octanone_3",
            "vinylguaiacol_4", "vinylphenol_4",
        )},  # fmt: skip
        "acetic": ("engine", "abs", ("forecast",)),
        "ethanol": ("engine", "abs", ("forecast",)),
    },
    "vinegar": {  # § 4.2: every calibrated cell is a direction (wine -> vinegar)
        "acetaldehyde": (_CAL, "shape", ("02:V1", "02:V4")),
        "ethyl_acetate": (_CAL, "shape", ("02:V3", "02:V1")),
        "acetoin": (_CAL, "shape", ("02:V1", "02:V3", "02:V4", "02:V10")),
        "methylbutanol_3": (_CAL, "shape", ("02:V1", "02:V3", "02:V4")),
        "methylbutanol_2": (_CAL, "shape", ("02:V1", "02:V2", "02:V3")),
        "methylpropanol_2": (_CAL, "shape", ("02:V1", "02:V3", "02:V4")),
        "phenylethanol_2": (_CAL, "shape", ("02:V1", "02:V3", "02:V4")),
        "methylbutanoic_3": (_CAL, "shape", ("02:V4", "02:V8")),
        "methylpropanoic_2": (_CAL, "shape", ("02:V4",)),
        **{k: (_CAL, "shape", ("02:V3", "02:V4")) for k in (
            "isoamyl_acetate", "isobutyl_acetate", "ethyl_hexanoate", "ethyl_octanoate",
            "ethyl_decanoate", "ethyl_2methylpropanoate",
        )},  # fmt: skip
        "linalool": (_CAL, "shape", ("02:V3",)),
        "damascenone": (_CAL, "shape", ("02:V3",)),
        "diacetyl": (_REP, "presence", ("02:V3", "02:V6")),
        "butanediol_23": (_REP, "presence", ("02:V1", "02:V3", "02:V4")),
        "ethyl_lactate": (_REP, "presence", ("02:V1", "02:V3")),
        **{k: (_REP, "presence", ("02:V4", "02:V6", "02:V9", "02:V13")) for k in (
            "methylbutanal_3", "methylbutanal_2", "methylpropanal_2", "methional",
        )},  # fmt: skip
        "methylbutanoic_2": (_REP, "presence", ("02:V13",)),
        **{k: (_REP, "presence", ("02:V3", "02:V4", "02:V6", "02:V8")) for k in (
            "phenylethyl_acetate", "ethyl_butanoate", "ethyl_2methylbutanoate",
        )},  # fmt: skip
        **{k: (_REP, "presence", ("02:V4", "02:V3")) for k in (
            "hexanoic", "octanoic", "decanoic",
        )},  # fmt: skip
        **{k: (_REP, "presence", ("02:V3", "02:V4", "02:V5", "02:V6")) for k in (
            "hexanal", "nonanal", "octen3one", "citronellol",
        )},  # fmt: skip
        "vinylguaiacol_4": (_REP, "presence", ("02:V14",)),
        "ethylguaiacol_4": (_REP, "presence", ("02:V6", "02:V9")),
        "ethylphenol_4": (_REP, "presence", ("02:V6", "02:V9")),
        **{k: ("plausible", "", ()) for k in (
            "pentanedione_23", "phenylacetaldehyde", "methionol",
        )},  # fmt: skip
        "acetic": ("engine", "abs", ("forecast",)),
        "ethanol": ("engine", "abs", ("forecast",)),
    },
    "koji": {  # § 4.4 (exploratory type; time courses on bran, end points on rice)
        "octen3ol": (_CAL, "shape", ("02:J1", "02:J3")),
        "octanone_3": (_CAL, "shape", ("02:J1",)),
        "octanol_3": (_CAL, "shape", ("02:J1",)),
        "heptanone_2": (_CAL, "shape", ("02:J1", "02:J2")),
        "nonanone_2": (_CAL, "shape", ("02:J1", "02:J2")),
        "ethyl_acetate": (_CAL, "shape", ("02:J1",)),
        "isoamyl_acetate": (_CAL, "shape", ("02:J1",)),
        "hexanal": (_CAL, "shape", ("02:J1", "02:J4", "02:J2")),
        **{k: (_REP, "presence", ("02:J2", "02:J4")) for k in (
            "methylbutanol_3", "methylpropanol_2", "methylbutanol_2",
        )},  # fmt: skip
        **{k: (_REP, "presence", ("02:J2",)) for k in (
            "methylbutanal_3", "methylbutanal_2", "methylpropanal_2", "phenylacetaldehyde",
            "methional", "ethyl_2methylpropanoate", "ethyl_2methylbutanoate", "ethyl_hexanoate",
            "ethyl_octanoate",
        )},  # fmt: skip
        **{k: (_REP, "presence", ("02:J1", "02:J2")) for k in (
            "methylbutanoic_3", "methylpropanoic_2", "methylbutanoic_2", "nonanal",
            "pentylfuran_2", "vinylguaiacol_4",
        )},  # fmt: skip
        **{k: (_REP, "presence", ("02:J1", "02:J2", "02:J4")) for k in (
            "acetaldehyde", "diacetyl", "acetoin", "pentanedione_23", "butanediol_23",
        )},  # fmt: skip
        "ethylguaiacol_4": (_REP, "presence", ("02:J1",)),
        **{k: ("plausible", "", ()) for k in (
            "octen3one", "phenylethanol_2", "methionol", "ethyl_decanoate", "isobutyl_acetate",
            "ethyl_butanoate", "phenylethyl_acetate", "hexanoic", "octanoic", "decanoic",
            "e2_nonenal", "z3_hexenal", "z3_hexenol", "z4_heptenal", "acetylpyrroline_2",
        )},  # fmt: skip
    },
    "miso": {  # § 4.8 (exploratory type)
        "hemf": (_CAL, "abs", ("04:M9", "04:M1", "04:M2", "04:M8", "04:M10")),
        "furaneol": (_CAL, "abs", ("04:M1", "04:M2")),
        "norfuraneol": (_CAL, "abs", ("04:M1",)),
        "maltol": (_CAL, "shape", ("04:M2", "04:M1")),
        "methylbutanol_3": (_CAL, "shape", ("04:M2", "04:M8", "04:M1")),
        "methylbutanol_2": (_CAL, "shape", ("04:M2",)),
        "methylpropanol_2": (_CAL, "shape", ("04:M2",)),
        "phenylethanol_2": (_CAL, "shape", ("04:M2", "04:M8")),
        "methionol": (_CAL, "shape", ("04:M2", "04:M8")),
        "phenylethyl_acetate": (_CAL, "shape", ("04:M2",)),
        **{k: (_CAL, "shape", ("04:M3",)) for k in (
            "methylbutanal_3", "methylbutanal_2", "methylpropanal_2", "phenylacetaldehyde",
            "ethyl_2methylpropanoate", "ethyl_2methylbutanoate", "ethyl_acetate",
            "isoamyl_acetate", "acetaldehyde", "hexanal", "octen3ol",
        )},  # fmt: skip
        **{k: (_REP, "abs", ("04:M1",)) for k in (
            "methylbutanoic_3", "acetoin", "butanediol_23", "ethyl_lactate",
        )},  # fmt: skip
        "methional": (_REP, "presence", ("04:M5",)),
        "octen3one": (_REP, "presence", ("04:M5",)),
        "dmts": (_REP, "presence", ("04:M6",)),
        **{k: (_REP, "presence", ("04:M3",)) for k in (
            "ethyl_hexanoate", "ethyl_octanoate", "ethyl_decanoate",
        )},  # fmt: skip
        **{k: (_REP, "semi", ("04:M10",)) for k in (
            "hexanoic", "dimethylpyrazine_25", "trimethylpyrazine", "vinylguaiacol_4",
            "ethylguaiacol_4", "ethylphenol_4",
        )},  # fmt: skip
        **{k: ("plausible", "", ()) for k in (
            "methylbutanoic_2", "methylpropanoic_2", "isobutyl_acetate", "ethyl_butanoate",
            "octanoic", "decanoic", "diacetyl", "pentanedione_23", "z3_hexenal", "e2_nonenal",
            "nonanal", "pentylfuran_2", "z4_heptenal", "octanone_3", "octanol_3",
            "methanethiol", "dms", "dmds", "vinylphenol_4", "sotolon", "acetylpyrroline_2",
        )},  # fmt: skip
        "acetic": ("engine", "abs", ("forecast",)),
        "ethanol": ("engine", "abs", ("forecast",)),
    },
    "garum": {  # § 4.9 (exploratory type; traditional recipe: fish + salt)
        **{k: (_CAL, "semi", ("04:G1", "04:G2")) for k in (
            "methylbutanoic_3", "phenylacetaldehyde", "nonanal",
        )},  # fmt: skip
        **{k: (_CAL, "semi", ("04:G1",)) for k in (
            "methylpropanoic_2", "butanoic", "hexanoic", "octanoic", "decanoic",
            "ethyl_octanoate", "phenylethanol_2",
        )},  # fmt: skip
        "methylbutanal_3": (_CAL, "shape", ("04:G2", "04:G5", "04:G3")),
        "methylbutanal_2": (_CAL, "shape", ("04:G2", "04:G5")),
        **{k: (_CAL, "shape", ("04:G2",)) for k in ("hexanal", "pentylfuran_2", "octen3ol")},
        "dmts": (_REP, "semi", ("04:G1", "04:G4")),
        "methylpropanal_2": (_REP, "presence", ("04:G3", "04:G4", "04:G8")),
        "methional": (_REP, "presence", ("04:G6", "04:G2")),
        "dmds": (_REP, "presence", ("04:G3", "04:G2")),
        "dms": (_REP, "presence", ("04:G3", "04:G2")),
        "ethyl_acetate": (_REP, "presence", ("04:G2",)),
        "ethyl_decanoate": (_REP, "presence", ("04:G2",)),
        "methylbutanol_3": (_REP, "presence", ("04:G9",)),
        "diacetyl": (_REP, "presence", ("04:G8",)),
        "hemf": (_REP, "presence", ("04:G7",)),
        "trimethylamine": (_REP, "presence", ("04:G2",)),
        "ethylphenol_4": (_REP, "presence", ("04:G2", "04:G7")),
        "ethylguaiacol_4": (_REP, "presence", ("04:G2", "04:G7")),
        **{k: ("plausible", "", ()) for k in (
            "methylbutanoic_2", "methylbutanol_2", "methylpropanol_2", "methionol",
            "ethyl_2methylpropanoate", "ethyl_2methylbutanoate", "methanethiol",
            "dimethylpyrazine_25", "trimethylpyrazine", "z4_heptenal", "e2_nonenal",
            "acetaldehyde", "acetoin", "furaneol", "maltol",
        )},  # fmt: skip
        "acetic": ("engine", "abs", ("forecast",)),
        "ethanol": ("engine", "abs", ("forecast",)),
    },
    "kombucha": {  # § 4.1
        "methylbutanol_3": (_CAL, "abs", ("02:K1", "02:K2", "02:K3")),
        "methylbutanol_2": (_REP, "presence", ("02:K6",)),
        "methylpropanol_2": (_REP, "abs", ("02:K3", "02:K2")),
        "phenylethanol_2": (_CAL, "shape", ("02:K1", "02:K2")),
        "methylbutanal_3": (_REP, "presence", ("02:K3", "02:K6")),
        "methylbutanal_2": (_REP, "presence", ("02:K3", "02:K6")),
        "phenylacetaldehyde": (_REP, "presence", ("02:K1",)),
        "methionol": (_REP, "presence", ("02:K4",)),
        "methylbutanoic_3": (_CAL, "shape", ("02:K1", "02:K2")),
        "methylpropanoic_2": (_CAL, "shape", ("02:K1", "02:K2")),
        "methylbutanoic_2": (_REP, "presence", ("02:K6",)),
        "ethyl_acetate": (_CAL, "abs", ("02:K2", "02:K3", "02:K4")),
        "isoamyl_acetate": (_CAL, "semi", ("02:K2",)),
        "phenylethyl_acetate": (_CAL, "semi", ("02:K1", "02:K2")),
        "ethyl_hexanoate": (_CAL, "semi", ("02:K1", "02:K2")),
        "ethyl_octanoate": (_REP, "presence", ("02:K6", "02:K4")),
        "ethyl_decanoate": (_CAL, "semi", ("02:K2",)),
        "ethyl_2methylpropanoate": (_REP, "presence", ("02:K3",)),
        **{k: (_CAL, "shape", ("02:K1",)) for k in ("hexanoic", "octanoic", "decanoic")},
        **{k: (_REP, "presence", ("02:K3", "02:K6")) for k in (
            "acetaldehyde", "diacetyl", "acetoin",
        )},  # fmt: skip
        "hexanal": (_CAL, "shape", ("02:K1",)),
        "nonanal": (_CAL, "semi", ("02:K1", "02:K2")),
        "octen3ol": (_REP, "presence", ("02:K3",)),
        "linalool": (_CAL, "abs", ("02:K1", "02:K2", "02:K4")),
        "geraniol": (_CAL, "shape", ("02:K1",)),
        "citronellol": (_REP, "presence", ("02:K4", "02:K6")),
        "damascenone": (_REP, "presence", ("02:K4", "02:K6")),
        "methyl_salicylate": (_CAL, "semi", ("02:K1", "02:K2")),
        "ionone_beta": (_CAL, "semi", ("02:K1", "02:K2")),
        "limonene": (_CAL, "shape", ("02:K1",)),
        "vinylguaiacol_4": (_REP, "presence", ("02:K4",)),
        "dms": (_REP, "presence", ("02:K4",)),
        "ethylguaiacol_4": (_CAL, "semi", ("02:K1", "02:K2")),
        "ethylphenol_4": (_CAL, "semi", ("02:K2",)),
        **{k: ("plausible", "", ()) for k in (
            "methylpropanal_2", "methional", "isobutyl_acetate", "ethyl_butanoate",
            "ethyl_2methylbutanoate", "pentanedione_23", "butanediol_23", "ethyl_lactate",
            "methanethiol", "dmds", "dmts",
        )},  # fmt: skip
        "acetic": ("engine", "abs", ("forecast",)),
        "ethanol": ("engine", "abs", ("forecast",)),
    },
    "kefir": {  # § 4.6
        "acetaldehyde": (_CAL, "abs", ("03:S19", "03:S20", "03:S18", "03:S26")),
        "diacetyl": (_CAL, "shape", ("03:S21", "03:S18", "03:S19", "03:S22")),
        "pentanedione_23": (_CAL, "shape", ("03:S21",)),
        "acetoin": (_CAL, "abs", ("03:S19", "03:S22", "03:S25")),
        **{k: (_CAL, "shape", ("03:S21", "03:S18")) for k in (
            "ethyl_acetate", "ethyl_butanoate", "ethyl_hexanoate", "isoamyl_acetate",
        )},  # fmt: skip
        **{k: (_CAL, "semi", ("03:S23",)) for k in (
            "ethyl_octanoate", "ethyl_decanoate", "octanoic", "decanoic", "nonanone_2",
            "decalactone_delta", "dodecalactone_delta",
        )},  # fmt: skip
        "hexanoic": (_CAL, "semi", ("03:S23", "03:S21")),
        "phenylethanol_2": (_CAL, "semi", ("03:S23", "03:S21")),
        **{k: (_CAL, "shape", ("03:S21",)) for k in (
            "methylbutanol_3", "methylbutanol_2", "methylpropanol_2", "methylbutanal_3",
            "methylbutanal_2",
        )},  # fmt: skip
        "hexanal": (_REP, "abs", ("03:S34", "03:S21", "03:S22")),
        "butanoic": (_REP, "presence", ("03:S22",)),
        "heptanone_2": (_REP, "presence", ("03:S23",)),
        "butanediol_23": (_REP, "presence", ("03:S21",)),
        "nonanal": (_REP, "presence", ("03:S21",)),
        **{k: ("plausible", "", ()) for k in (
            "dms", "methional", "methionol", "methylpropanal_2", "phenylacetaldehyde",
            "isobutyl_acetate", "phenylethyl_acetate", "ethyl_2methylbutanoate",
            "ethyl_2methylpropanoate", "ethyl_lactate", "methylbutanoic_3", "methylbutanoic_2",
            "methylpropanoic_2",
        )},  # fmt: skip
        "acetic": ("engine", "abs", ("forecast",)),
        "ethanol": ("engine", "abs", ("forecast",)),
    },
    "cheese": {  # § 4.7 (curd and acidification stage, per kg of milk)
        "diacetyl": (_CAL, "shape", ("03:S30", "03:S27", "03:S28")),
        "acetoin": (_CAL, "shape", ("03:S30", "03:S28")),
        "acetaldehyde": (_REP, "presence", ("03:S27",)),
        **{k: (_REP, "abs", ("03:S34", "03:S32")) for k in (
            "butanoic", "octanoic", "decanoic", "decalactone_delta", "dodecalactone_delta",
        )},  # fmt: skip
        "hexanal": (_REP, "abs", ("03:S34",)),
        **{k: (_REP, "presence", ("03:S32",)) for k in (
            "hexanoic", "ethyl_butanoate", "ethyl_hexanoate", "methylbutanal_3",
            "methylbutanol_3", "phenylethanol_2", "methylbutanoic_3", "methylbutanoic_2",
            "methylpropanoic_2",
        )},  # fmt: skip
        **{k: ("plausible", "", ()) for k in (
            "butanediol_23", "pentanedione_23", "dms", "heptanone_2", "nonanone_2",
        )},  # fmt: skip
        "acetic": ("engine", "abs", ("forecast",)),
        "ethanol": ("engine", "abs", ("forecast",)),
    },
}

# type -> compound -> why it computes zero there (the † cells of § 4 and plausible
# compounds whose only route is an uncurated ingredient precursor)
_FLOUR_PENDING = (
    "nonanal", "pentylfuran_2", "octen3ol", "octanol_3", "limonene", "heptanone_2", "butanoic",
    "octen3one", "sotolon", "z3_hexenal", "z3_hexenol", "z4_heptenal", "octanone_3",
)  # fmt: skip
PENDING: dict[str, dict[str, str]] = {
    "sourdough": {
        **{k: f"the flour's {COMPOUNDS[k].name} is not curated yet" for k in _FLOUR_PENDING},
        "vinylphenol_4": "the flour's p-coumaric acid is not curated yet",
    },
    "vinegar": {
        **{k: f"the base wine's {COMPOUNDS[k].name} is not curated yet" for k in (
            "linalool", "damascenone", "hexanal", "nonanal", "octen3one", "citronellol",
        )},  # fmt: skip
        "vinylguaiacol_4": "the base fruit's ferulic acid is not curated yet",
    },
    "koji": {
        **{k: f"the rice's {COMPOUNDS[k].name} is not curated yet" for k in (
            "nonanal", "pentylfuran_2", "e2_nonenal", "z3_hexenal", "z3_hexenol", "z4_heptenal",
            "acetylpyrroline_2",
        )},  # fmt: skip
        "vinylguaiacol_4": "the rice's ferulic acid is not curated yet",
    },
    "miso": {
        **{k: f"the soybean's {COMPOUNDS[k].name} is not curated yet" for k in (
            "hexanal", "z3_hexenal", "e2_nonenal", "nonanal", "pentylfuran_2", "z4_heptenal",
        )},  # fmt: skip
        **{k: "the soybean's sulfur precursors are not curated yet" for k in (
            "methanethiol", "dms", "dmds", "dmts",
        )},  # fmt: skip
        "vinylguaiacol_4": "soy hydroxycinnamic acids are not curated yet",
        "vinylphenol_4": "soy hydroxycinnamic acids are not curated yet",
        "sotolon": "the soybean's sotolon is not curated yet",
        "acetylpyrroline_2": "the rice's 2-acetyl-1-pyrroline is not curated yet",
    },
    "kombucha": {
        "vinylguaiacol_4": "the tea's ferulic acid is not curated yet",
        **{k: "the tea's sulfur precursors are not curated yet" for k in (
            "dms", "methanethiol", "dmds", "dmts",
        )},  # fmt: skip
        "citronellol": "the tea's citronellol is not curated yet",
        "damascenone": "the tea's β-damascenone is not curated yet",
        "octen3ol": "the tea's 1-octen-3-ol is not curated yet",
    },
    "kefir": {
        "heptanone_2": "UHT milk (2-heptanone) is not a catalogue ingredient yet",
        "nonanone_2": "UHT milk (2-nonanone) is not a catalogue ingredient yet",
        "dms": "the milk's dimethyl sulfide is not curated yet",
    },
    "cheese": {
        "heptanone_2": "UHT milk (2-heptanone) is not a catalogue ingredient yet",
        "nonanone_2": "UHT milk (2-nonanone) is not a catalogue ingredient yet",
        "dms": "the milk's dimethyl sulfide is not curated yet",
    },
    "garum": {
        **{k: "fish lipolysis is not modelled yet" for k in (
            "butanoic", "hexanoic", "octanoic", "decanoic",
        )},  # fmt: skip
        "e2_nonenal": "the fish's (E)-2-nonenal is not curated yet",
        **{k: "the fish's sulfur precursors are not curated yet" for k in (
            "methanethiol", "dms", "dmds", "dmts",
        )},  # fmt: skip
    },
}
