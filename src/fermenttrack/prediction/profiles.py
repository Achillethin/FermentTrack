"""Per-fermentation-type context for the kinetic model: the matrix (what the microbes live
in), typical temperature and horizon, starter/inoculum levels, a fallback recipe for
batches with no quantified recipe, and the milestones worth announcing.

Pool concentrations are g per kg of batch (~g/L for liquids). Inoculum priors are
log10 CFU per g of batch at t=0 (for molds: g dry mycelium per kg). Buffer capacities are
mmol H+ per kg per pH unit around pH 4-6, derived from titratable-acidity-vs-pH data
(estimates, see each entry). Research record:
docs/superpowers/specs/2026-09-24-fermentation-prediction-design.md § 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fermenttrack.prediction.priors import Prior


def _t(lo: float, med: float, hi: float) -> Prior:
    return Prior(med, lo, hi, "lin")


def _r(lo: float, med: float, hi: float) -> Prior:
    return Prior(med, lo, hi, "log")


@dataclass(frozen=True)
class Milestone:
    key: str
    title: str  # short: "pH below 4.6"
    note: str  # why it matters, one clause
    series: str  # series key it reads
    kind: Literal["below", "above", "consumed_fraction", "of_initial_fraction"]
    threshold: float
    # consumed_fraction: the series fell by `threshold` x its t=0 value (0.9 = 90 % used).
    # of_initial_fraction: the series reached `threshold` x the t=0 value of `ref`
    # (amino acids = 30 % of the starting protein).
    ref: str | None = None


@dataclass(frozen=True)
class FermentProfile:
    type: str
    temp_c: float  # typical fermentation temperature (the default when none is given)
    temp_range: tuple[float, float]  # typical range, shown as guidance
    horizon_h: float  # default forecast horizon from batch start
    aerobic: bool  # obligate aerobes (acetic acid bacteria, koji mold) can grow
    ph0: Prior  # matrix pH before any starter acids
    buffer_mm: Prior  # matrix buffer capacity
    typical_recipe: dict[str, float]  # g/kg; keys are pools plus "water" and "salt"
    inoculum: dict[str, Prior]  # organism -> log10 CFU/g at t=0 at the typical starter dose
    starter_fraction: float | None = None  # typical backslop/starter mass share, if any
    starter_acids: dict[str, float] = field(default_factory=dict)  # g/kg in the starter
    oxygen_factor: Prior = field(default_factory=lambda: Prior(1.0, 1.0, 1.0))
    starch_accessible: float = 1.0  # share of starch enzymes can reach (damaged starch in flour)
    flour_amylase: Prior | None = None  # 1/h at 50 °C, cereal enzymes on accessible starch
    fish_protease: Prior | None = None  # 1/h at 50 °C, fish digestive enzymes
    koji_enzyme0: Prior | None = None  # koji enzyme activity at t=0 (0-1 scale)
    enzyme_access: float = 1.0  # < 1 for solid-state koji (little free water)
    x_max_override: dict[str, Prior] = field(default_factory=dict)
    h0_factor: float = 1.0  # < 1 when an active, back-slopped starter shortens the lag
    sugar_default: str = "hexoses"  # where sugars without a USDA breakdown are booked
    # Solid ferments are often logged by dry weight; below this water share the grains and
    # beans are assumed soaked and cooked (water added up to it).
    min_water_fraction: float | None = None
    milestones: tuple[Milestone, ...] = ()
    show_density: bool = False  # gravity/Brix series make sense (clear liquids)
    show_ph: bool = True
    ph_safety_line: bool = True  # the 4.6 pH reference line applies
    # "established": kinetics from published pure-culture/food studies; "exploratory":
    # enzyme- and halophile-driven ferments with little published kinetics (bands are
    # wide and the curves sketch the mechanism rather than a calibrated forecast).
    confidence: Literal["established", "exploratory"] = "established"
    sources: tuple[str, ...] = ()  # trajectory data the defaults were checked against
    notes: tuple[str, ...] = ()


def _ph_below(value: float, note: str) -> Milestone:
    key = f"ph_below_{str(value).replace('.', '_')}"
    return Milestone(key, f"pH below {value}", note, "ph", "below", value)


# Worded as a threshold, never as "safe by": a forecast must not stand in for a reading.
_PH_46 = _ph_below(4.6, "the food-safety acidity threshold; confirm with a pH reading")
_SUGARS_90 = Milestone(
    "sugars_90pct_used", "90 % of the sugars fermented", "most of the sweetness gone",
    "sugars_total", "consumed_fraction", 0.9,
)  # fmt: skip


def _hydrolysed(pct: int) -> Milestone:
    return Milestone(
        f"protein_{pct}pct_hydrolysed", f"{pct} % of the protein broken down",
        "amino acids and peptides: savoury depth builds", "amino_acids",
        "of_initial_fraction", pct / 100, ref="protein",
    )  # fmt: skip


PROFILES: dict[str, FermentProfile] = {
    p.type: p
    for p in [
        FermentProfile(
            type="kombucha",
            temp_c=24.0,
            temp_range=(20.0, 28.0),
            horizon_h=21 * 24,
            aerobic=True,
            ph0=_t(4.6, 5.0, 5.5),
            buffer_mm=_r(0.5, 2.0, 5.0),  # sweet tea: nearly unbuffered (Jayabalan 2007)
            typical_recipe={"water": 830.0, "sucrose": 70.0},
            starter_fraction=0.10,
            # Mature kombucha used as starter: ~pH 2.8, acetic + gluconic acid.
            starter_acids={"acetic_acid": 5.0, "gluconic_acid": 2.0},
            # A transferred SCOBY brings its pellicle population, not just starter liquid.
            inoculum={
                "Saccharomyces cerevisiae": _t(5.3, 6.0, 6.6),
                "Acetobacter aceti": _t(6.3, 7.0, 7.7),
                "Gluconacetobacter xylinus": _t(6.3, 7.0, 7.7),
            },
            # Tea is nitrogen-poor: yeast in the liquid stays at 1e6-1e7 CFU/mL. Most of the
            # acetic acid bacteria live in the cellulose pellicle (the SCOBY), so their
            # effective population per kg of batch is far above liquid-phase counts.
            x_max_override={
                "Saccharomyces cerevisiae": _t(6.4, 7.0, 7.6),
                "Acetobacter aceti": _t(7.2, 7.8, 8.5),
                "Gluconacetobacter xylinus": _t(7.2, 7.8, 8.5),
            },
            # Acetic acid bacteria sit at the air surface: oxygen transfer through the
            # interface caps their rate (Cvetković et al. 2008; Chen & Liu 2000). Median
            # calibrated to acetic acid ~4 g/L by day 12 at 24 °C (Jayabalan et al. 2007).
            oxygen_factor=_r(0.3, 0.7, 1.0),
            h0_factor=0.4,
            milestones=(
                _ph_below(4.2, "the commonly cited kombucha acidity threshold"),
                _ph_below(3.3, "tart: most kombucha is bottled between pH 2.8 and 3.5"),
                Milestone(
                    "sugars_50pct_used", "Half the sugar fermented", "sweet-tart balance",
                    "sugars_total", "consumed_fraction", 0.5,
                ),  # fmt: skip
            ),
            show_density=True,
            sources=(
                "Jayabalan et al. 2007 Food Chem 102:392",
                "Chen & Liu 2000 J Appl Microbiol 89:834",
                "Cohen et al. 2023 Foods 12:3116",
            ),
            notes=(
                "Kombucha's real yeasts are mostly Brettanomyces/Zygosaccharomyces; "
                "S. cerevisiae kinetics stand in for them.",
                "Acetic acid bacteria need air: a wide, shallow vessel ferments faster than "
                "a narrow one, which the model cannot see.",
            ),
        ),
        FermentProfile(
            type="sourdough",
            temp_c=26.0,
            temp_range=(22.0, 30.0),
            horizon_h=24.0,
            aerobic=False,
            ph0=_t(5.8, 6.1, 6.3),
            # ~80 mmol/kg of acid (TTA ~8-10 mL) takes dough from pH 6.1 to ~3.8
            buffer_mm=_r(12.0, 20.0, 35.0),
            # A fed levain (1:1 flour:water, unsalted): the stage machine starts at feeding.
            typical_recipe={
                "water": 460.0, "starch": 370.0, "protein": 62.0, "maltose": 5.0,
                "hexoses": 2.0,
            },  # fmt: skip
            starter_fraction=0.20,
            starter_acids={"lactic_acid": 7.0, "acetic_acid": 2.0},  # ripe levain, TTA ~10
            inoculum={
                "Lactobacillus sanfranciscensis": _t(8.0, 8.6, 9.0),
                "Saccharomyces cerevisiae": _t(6.0, 6.6, 7.0),
            },
            starch_accessible=0.08,  # damaged starch in milled flour
            flour_amylase=_r(0.08, 0.2, 0.5),
            h0_factor=0.4,
            milestones=(
                _ph_below(4.5, "noticeably sour"),
                _ph_below(4.0, "ripe, well-acidified dough"),
            ),
            ph_safety_line=False,
            sources=("Minervini et al. 2012 AEM 78:1251", "Gänzle et al. 1998 AEM 64:2616"),
        ),
        FermentProfile(
            type="koji",
            temp_c=30.0,
            temp_range=(28.0, 35.0),
            horizon_h=72.0,
            aerobic=True,
            ph0=_t(5.9, 6.3, 6.7),
            buffer_mm=_r(10.0, 20.0, 40.0),
            typical_recipe={"water": 380.0, "starch": 500.0, "protein": 45.0, "hexoses": 2.0},
            inoculum={"Aspergillus oryzae": _r(0.003, 0.01, 0.03)},
            min_water_fraction=0.35,  # steamed koji rice
            koji_enzyme0=_r(0.003, 0.01, 0.03),
            # Little saccharification happens in the koji itself: free glucose rose only
            # 2.0 -> 2.7 g/kg over 48 h (te Biesebeke et al. 2002); the enzymes work once
            # the koji meets water (amazake, miso, garum).
            enzyme_access=0.05,
            milestones=(
                Milestone(
                    "mycelium_90pct", "Mycelium at 90 % of full growth",
                    "typical harvest point (40-48 h at 30 °C)", "mycelium", "above", 90.0,
                ),  # fmt: skip
            ),
            show_ph=False,
            ph_safety_line=False,
            confidence="exploratory",
            sources=("te Biesebeke et al. 2002 FEMS Yeast Res 2:245", "Bechman et al. 2012"),
            notes=(
                "Koji heats itself as it grows; the model assumes you hold the bed at the set "
                "temperature (keep it below 40 °C).",
            ),
        ),
        FermentProfile(
            type="cheese",
            temp_c=30.0,
            temp_range=(28.0, 32.0),
            horizon_h=24.0,
            aerobic=False,
            ph0=_t(6.55, 6.65, 6.75),
            # milk: ~0.75 % lactic acid takes it from 6.65 to ~4.5; peak near pH 5.1
            # (Salaün et al. 2005)
            buffer_mm=_r(25.0, 35.0, 50.0),
            typical_recipe={"water": 880.0, "lactose": 48.0, "protein": 32.0},
            inoculum={"Lactococcus lactis": _t(6.3, 7.0, 7.5)},  # DVS/bulk starter ~1e6-1e7
            h0_factor=0.6,
            sugar_default="lactose",
            milestones=(
                _ph_below(6.3, "typical draining point for many curds"),
                _ph_below(5.3, "typical milling acidity (cheddar-style)"),
                _ph_below(4.6, "acid-set fresh cheese range"),
            ),
            sources=("Poudel et al. 2022 J Dairy Sci 105:2069", "Salaün et al. 2005"),
            notes=("Models the acidification of the milk and curd, not ripening.",),
        ),
        FermentProfile(
            type="kefir",
            temp_c=22.0,
            temp_range=(18.0, 25.0),
            horizon_h=48.0,
            aerobic=False,
            ph0=_t(6.55, 6.65, 6.75),
            buffer_mm=_r(25.0, 35.0, 50.0),
            typical_recipe={"water": 880.0, "lactose": 48.0, "protein": 32.0},
            starter_fraction=0.05,
            inoculum={
                "Lactococcus lactis": _t(6.5, 7.2, 7.8),
                "Lactobacillus kefiranofaciens": _t(6.0, 6.8, 7.5),
                "Lactobacillus kefiri": _t(5.5, 6.5, 7.2),
                "Kluyveromyces marxianus": _t(3.8, 4.6, 5.4),
            },
            h0_factor=0.5,
            sugar_default="lactose",
            milestones=(
                _PH_46,
                _ph_below(4.3, "tangy, typical ready kefir (4.2-4.6)"),
            ),
            sources=("Irigoyen et al. 2005 Food Chem 90:613", "Garrote et al. 1998"),
            notes=(
                "Grain-to-milk ratio matters a lot: 2-5 % grains is assumed when none is "
                "logged.",
            ),
        ),
        FermentProfile(
            type="lacto_ferment",
            temp_c=20.0,
            temp_range=(16.0, 24.0),
            horizon_h=28 * 24,
            aerobic=False,
            ph0=_t(5.9, 6.2, 6.5),
            buffer_mm=_r(20.0, 35.0, 55.0),  # cabbage: 0.59 % TA at pH 4.97, 0.76 % at 4.41
            typical_recipe={
                "water": 900.0, "hexoses": 31.0, "sucrose": 1.0, "protein": 12.7, "salt": 20.0,
            },  # fmt: skip
            # Natural microbiota on vegetables (no starter): 1e4-1e6 LAB/g at the start of
            # commercial sauerkraut (Plengvidhya et al. 2007).
            inoculum={
                "Leuconostoc mesenteroides": _t(3.0, 4.2, 5.5),
                "Lactobacillus plantarum": _t(2.5, 3.6, 5.0),
            },
            milestones=(
                _PH_46,
                _ph_below(4.0, "tangy, typical sauerkraut/kimchi"),
                _SUGARS_90,
            ),
            sources=(
                "Plengvidhya et al. 2007 AEM 73:7697",
                "Hong et al. 2016 J Food Sci 81:C2623",
            ),
        ),
        FermentProfile(
            type="miso",
            temp_c=25.0,
            temp_range=(15.0, 30.0),
            horizon_h=180 * 24,
            aerobic=False,
            ph0=_t(5.9, 6.2, 6.5),
            buffer_mm=_r(40.0, 70.0, 110.0),  # protein-rich: pH 6.2 -> ~5 with ~1 % lactic
            typical_recipe={
                "water": 450.0, "starch": 190.0, "protein": 120.0, "hexoses": 5.0, "salt": 110.0,
            },  # fmt: skip
            inoculum={
                "Tetragenococcus halophilus": _t(1.5, 3.0, 4.5),
                "Zygosaccharomyces rouxii": _t(1.0, 2.5, 4.0),
            },
            koji_enzyme0=_r(0.3, 0.5, 0.8),  # koji is ~half the mash
            min_water_fraction=0.45,  # cooked soybeans + koji
            milestones=(
                _ph_below(5.0, "finished miso is typically pH 4.8-5.3"),
                _hydrolysed(30),
            ),
            ph_safety_line=False,
            confidence="exploratory",
            sources=("Allwood et al. 2021 J Food Sci", "Ito & Matsuyama 2021 J Fungi 7:658"),
            notes=("The koji mold does not grow in the mash; its enzymes do the work.",),
        ),
        FermentProfile(
            type="garum",
            temp_c=30.0,
            temp_range=(20.0, 60.0),
            horizon_h=180 * 24,
            aerobic=False,
            ph0=_t(6.0, 6.4, 6.8),
            buffer_mm=_r(40.0, 80.0, 150.0),
            # koji garum (the default organism set includes A. oryzae): fish, ~25 % koji, 12 % salt
            typical_recipe={"water": 580.0, "protein": 140.0, "starch": 90.0, "salt": 120.0},
            inoculum={"Tetragenococcus halophilus": _t(1.0, 2.5, 4.0)},
            koji_enzyme0=_r(0.15, 0.3, 0.5),  # koji garum: ~20-30 % koji
            fish_protease=_r(3e-4, 1e-3, 3e-3),  # fish digestive enzymes (viscera)
            milestones=(_hydrolysed(30), _hydrolysed(60)),
            ph_safety_line=False,
            confidence="exploratory",
            sources=("Lopetcharat et al. 2001 Food Rev Int 17:65", "Redzepi & Zilber 2018"),
            notes=(
                "Traditional garum relies on salt (2-3 parts fish to 1 part salt, 12-18 "
                "months); koji garum on heat (about 60 °C for 10-12 weeks).",
            ),
        ),
        FermentProfile(
            type="vinegar",
            temp_c=27.0,
            temp_range=(24.0, 30.0),
            horizon_h=60 * 24,
            aerobic=True,
            ph0=_t(3.1, 3.4, 3.8),
            buffer_mm=_r(10.0, 25.0, 45.0),  # wine/cider: tartaric/malic salts
            typical_recipe={"water": 850.0, "ethanol": 55.0, "hexoses": 3.0},
            starter_fraction=0.15,
            starter_acids={"acetic_acid": 50.0},
            inoculum={
                "Acetobacter aceti": _t(4.0, 5.0, 6.0),
                "Acetobacter pasteurianus": _t(4.0, 5.0, 6.0),
            },
            # The mother of vinegar, like a SCOBY, is a cellulose mat dense with bacteria.
            x_max_override={
                "Acetobacter aceti": _t(7.6, 8.3, 9.0),
                "Acetobacter pasteurianus": _t(7.6, 8.3, 9.0),
            },
            # Still surface culture (Orleans method): 1-3 g/L/day, 3-8 weeks (est.).
            oxygen_factor=_r(0.2, 0.5, 1.0),
            h0_factor=0.5,
            milestones=(
                Milestone(
                    "acetic_above_40", "Acetic acid above 40 g/kg",
                    "4 %, table-vinegar strength", "acetic_acid", "above", 40.0,
                ),  # fmt: skip
                Milestone(
                    "ethanol_below_5", "Ethanol below 5 g/kg", "most of the alcohol converted",
                    "ethanol", "below", 5.0,
                ),  # fmt: skip
            ),
            show_density=True,
            sources=("El-Askri et al. 2022 Microorganisms 10:1741", "Djafri et al. 2026 Foods"),
        ),
    ]
}

# Types without a profile (a free-string culture type) borrow this one: a generic,
# moderately buffered lactic ferment at room temperature.
GENERIC_PROFILE = FermentProfile(
    type="generic",
    temp_c=22.0,
    temp_range=(18.0, 26.0),
    horizon_h=14 * 24,
    aerobic=False,
    ph0=_t(5.5, 6.2, 6.8),
    buffer_mm=_r(5.0, 20.0, 60.0),
    typical_recipe={"water": 900.0, "hexoses": 30.0},
    inoculum={},
    milestones=(_PH_46,),
    confidence="exploratory",
)

# An organism attached to a batch whose type has no inoculum entry for it: a deliberate
# addition, assumed at a modest starter-culture level.
ADDED_ORGANISM_INOCULUM = _t(3.5, 5.0, 6.5)
ADDED_MOLD_INOCULUM = _r(0.003, 0.01, 0.03)


def profile_for(fermentation_type: str) -> FermentProfile:
    return PROFILES.get(fermentation_type, GENERIC_PROFILE)
