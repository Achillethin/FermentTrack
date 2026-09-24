"""Kinetic profiles for the reference organisms in fermenttrack.biochem.ORGANISMS.

Each profile turns an organism into ODE terms: growth (Monod on its sugars, capped by a
carrying capacity), catabolic channels (substrate -> products at fixed mass yields) and
the cardinal/inhibition models that scale both. Values are literature priors: a median
and a ~90 % range. Sources are cited inline; "est." marks a reasoned estimate where the
literature is thin. Full research record: docs/superpowers/specs/
2026-09-24-fermentation-prediction-design.md § 4.

Ks (Monod half-saturation) is deliberately placed in the upper part of the literature
range (~0.5-2 g/kg): sparse home measurements cannot identify it, and the sub-g/kg values
reported for pure cultures make the ensemble numerically stiff for no visible change in
the g/kg-scale curves this model reports.

Channel yields are grams of product per gram of substrate consumed. Sugars are counted
as hexose equivalents: one gram of a disaccharide yields 360/342 = 1.0526 g of hexose.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fermenttrack.prediction.priors import Prior

# Mass yields per g hexose (theoretical in brackets):
# alcoholic 0.47 ethanol (0.511) + 0.45 CO2 (0.489); observed 0.46-0.49.
ALCOHOLIC = {"ethanol": 0.47, "co2": 0.45}
# homolactic 0.90 lactate (1.0); observed 0.85-0.95.
HOMOLACTIC = {"lactic_acid": 0.90}
# heterolactic, phosphoketolase: lactate 0.50 + ethanol 0.256 | acetate 0.333 + CO2 0.244
# on glucose; with fructose as electron acceptor part goes to mannitol (untracked) and
# acetate replaces ethanol. The split is a typical mixed outcome on vegetable sugars.
HETEROLACTIC = {"lactic_acid": 0.45, "ethanol": 0.12, "acetic_acid": 0.10, "co2": 0.22}
# acetic acid bacteria: ethanol -> acetic acid, 1.304 g/g theoretical, 1.0-1.25 observed.
ACETIC_OXIDATION = {"acetic_acid": 1.20}
# glucose -> gluconic acid, 1.089 g/g theoretical.
GLUCONIC = {"gluconic_acid": 1.05}
# aerobic respiration: full oxidation gives 6 CO2 per hexose (1.47 g/g); roughly half the
# substrate carbon ends in mycelium, so ~0.8 g CO2 per g consumed.
RESPIRATION = {"co2": 0.8}

SUGARS = ("hexoses", "sucrose", "maltose", "lactose")


@dataclass(frozen=True)
class Channel:
    """One catabolic route: consumes `substrates` (shared pool), makes `products`."""

    substrates: tuple[str, ...]
    products: dict[str, float]
    weight: float = 1.0  # relative capacity of this route vs the organism's primary one


@dataclass(frozen=True)
class OrganismKinetics:
    name: str
    kingdom: str  # bacteria | yeast | mold
    role: str  # one plain-language line shown in the UI
    channels: tuple[Channel, ...]
    mu_max: Prior  # 1/h at optimal T, pH, aw
    ks: Prior  # g/kg, Monod half-saturation on its substrate pool
    yield_xs: Prior  # g dry biomass / g substrate
    maint: Prior  # g substrate / g biomass / h, catabolism not tied to growth (L-P beta)
    t_min: Prior  # °C, CTMI cardinal temperatures (Rosso et al. 1993)
    t_opt: Prior
    t_max: Prior
    ph_min: Prior  # CPM cardinal pH (Rosso et al. 1995)
    ph_opt: Prior
    ph_max: Prior
    mic_lactic_mm: Prior  # undissociated lactic acid stopping growth, mmol/kg
    mic_acetic_mm: Prior  # undissociated acetic acid stopping growth, mmol/kg
    aw_min: Prior  # water activity cardinal minimum (NaCl-driven here)
    ethanol_max: Prior  # g/kg ethanol stopping growth
    x_max: Prior  # carrying capacity, log10 CFU/g (cells) or g/kg (mold)
    h0: Prior  # Baranyi "work to be done" before growth: lag = h0 / mu
    k_death: Prior  # 1/h, death rate under full environmental stress
    aw_opt: float = 0.997  # below 1 for halophiles
    cell_mass_g: float | None = 3e-13  # dry g per cell; None = mold (biomass in g/kg)
    obligate_aerobe: bool = False
    inverts_sucrose: Prior | None = None  # g sucrose / g biomass / h (extracellular invertase)
    makes_enzymes: bool = False  # koji mold: amylase + protease pool grows with biomass
    sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_mold(self) -> bool:
        return self.cell_mass_g is None


def _t(lo: float, med: float, hi: float) -> Prior:
    """Linear-scale prior written low-to-high (temperatures, pH, aw, log counts)."""
    return Prior(med, lo, hi, "lin")


def _r(lo: float, med: float, hi: float) -> Prior:
    """Log-scale prior written low-to-high (rates, concentrations)."""
    return Prior(med, lo, hi, "log")


# Dry mass per colony-forming unit. Yeast: ~20 pg per cell. Lactic acid bacteria and
# acetic acid bacteria: ~0.2-0.3 pg per cell, but they grow in pairs and chains, so one CFU
# is typically 2-4 cells.
YEAST_CELL_G = 2e-11
LAB_CELL_G = 6e-13
COCCUS_CELL_G = 5e-13

ORGANISM_KINETICS: dict[str, OrganismKinetics] = {
    k.name: k
    for k in [
        OrganismKinetics(
            name="Saccharomyces cerevisiae",
            kingdom="yeast",
            role="yeast: splits sucrose, ferments sugars to ethanol + CO2",
            channels=(Channel(("hexoses", "maltose"), ALCOHOLIC),),
            mu_max=_r(0.25, 0.37, 0.47),  # Salvadó 2011: 0.28-0.45 over 10 strains
            ks=_r(0.5, 1.0, 2.5),
            yield_xs=_r(0.05, 0.10, 0.15),  # est., anaerobic
            maint=_r(0.1, 0.3, 0.8),  # est.
            t_min=_t(0.4, 2.8, 5.0),  # Salvadó 2011 (CTMI fits)
            t_opt=_t(30.0, 32.3, 34.8),
            t_max=_t(42.0, 45.4, 46.1),
            ph_min=_t(2.2, 2.5, 3.0),  # est.
            ph_opt=_t(4.5, 5.0, 5.5),
            ph_max=_t(7.5, 8.0, 8.5),
            mic_lactic_mm=_r(150.0, 300.0, 600.0),  # est.
            mic_acetic_mm=_r(60.0, 100.0, 150.0),  # est.
            aw_min=_t(0.88, 0.90, 0.92),  # ~10 % NaCl max, est.
            ethanol_max=_r(90.0, 112.0, 120.0),  # Luong 1985
            x_max=_t(7.0, 7.5, 8.2),
            h0=_r(0.2, 0.8, 2.5),  # lag 0.5-2 h: backslopped vs rehydrated
            k_death=_r(0.001, 0.003, 0.01),
            cell_mass_g=YEAST_CELL_G,
            # est.; kombucha sucrose falls ~4.4 g/L/day at 24 °C (Jayabalan et al. 2007)
            inverts_sucrose=_r(0.4, 1.2, 3.0),
            sources=("Salvadó et al. 2011 AEM 77:2292", "Luong 1985 Biotechnol Bioeng 27:280"),
        ),
        OrganismKinetics(
            name="Zygosaccharomyces rouxii",
            kingdom="yeast",
            role="salt- and sugar-tolerant yeast: ferments sugars to ethanol in high-salt mashes",
            channels=(Channel(("hexoses", "maltose"), ALCOHOLIC),),
            mu_max=_r(0.10, 0.20, 0.35),  # est.; slowed 2-5x at 15-18 % NaCl via aw
            ks=_r(0.5, 1.0, 2.5),
            yield_xs=_r(0.05, 0.10, 0.15),
            maint=_r(0.05, 0.15, 0.4),
            t_min=_t(2.0, 5.0, 8.0),  # Jansen 2003 (best at 30 °C), est. cardinals
            t_opt=_t(25.0, 28.0, 30.0),
            t_max=_t(35.0, 38.0, 40.0),
            ph_min=_t(2.0, 2.5, 3.0),
            ph_opt=_t(4.0, 4.5, 5.0),  # Jansen 2003; Ito & Matsuyama 2021
            ph_max=_t(7.0, 7.5, 8.0),
            mic_lactic_mm=_r(150.0, 300.0, 600.0),
            mic_acetic_mm=_r(40.0, 80.0, 150.0),
            aw_min=_t(0.78, 0.81, 0.84),  # grows in 17-20 % NaCl soy mash (Jansen 2003)
            ethanol_max=_r(40.0, 60.0, 90.0),  # 2-4 % in soy mash (Ito & Matsuyama 2021)
            x_max=_t(6.0, 6.8, 7.5),
            h0=_r(0.5, 2.0, 5.0),
            k_death=_r(0.0005, 0.002, 0.008),
            aw_opt=0.96,
            cell_mass_g=YEAST_CELL_G,
            sources=(
                "Jansen et al. 2003 FEMS Yeast Res 3:313",
                "Ito & Matsuyama 2021 J Fungi 7:658",
            ),
        ),
        OrganismKinetics(
            name="Kluyveromyces marxianus",
            kingdom="yeast",
            role="lactose-fermenting yeast: lactose -> ethanol + CO2 (kefir's fizz)",
            channels=(Channel(("lactose", "hexoses"), {"ethanol": 0.43, "co2": 0.41}),),
            mu_max=_r(0.3, 0.6, 0.95),  # Ospanova 2026: 0.92; other fits 0.14-0.67
            ks=_r(2.0, 6.0, 15.0),  # lactose 10-22 g/L, glucose 1.0 (Tinôco 2021)
            yield_xs=_r(0.05, 0.10, 0.15),
            maint=_r(0.1, 0.3, 0.8),
            t_min=_t(6.0, 9.1, 12.0),  # Ospanova 2026; Fonseca 2008
            t_opt=_t(35.0, 37.8, 40.0),
            t_max=_t(47.0, 50.0, 52.0),
            ph_min=_t(2.5, 2.9, 3.3),  # Ospanova 2026
            ph_opt=_t(5.0, 5.4, 5.8),
            ph_max=_t(9.0, 10.2, 10.5),
            mic_lactic_mm=_r(150.0, 300.0, 600.0),
            mic_acetic_mm=_r(60.0, 100.0, 150.0),
            aw_min=_t(0.90, 0.92, 0.94),
            ethanol_max=_r(40.0, 54.0, 63.0),  # 6.8 % v/v (Tinôco 2021)
            x_max=_t(5.0, 5.8, 6.8),  # kefir yeasts ~1e5 CFU/mL at 24 h (Irigoyen 2005)
            h0=_r(0.3, 1.0, 3.0),
            k_death=_r(0.001, 0.003, 0.01),
            cell_mass_g=YEAST_CELL_G,
            sources=("Ospanova et al. 2026 Front Microbiol", "Tinôco & da Silveira 2021 Biologia"),
        ),
        OrganismKinetics(
            name="Acetobacter aceti",
            kingdom="bacteria",
            role="acetic acid bacterium: oxidises ethanol to acetic acid (needs air)",
            channels=(
                Channel(("ethanol",), ACETIC_OXIDATION),
                Channel(("hexoses",), GLUCONIC, weight=0.3),
            ),
            mu_max=_r(0.25, 0.38, 0.47),  # Moreno-Zambrano 2018 (on ethanol)
            ks=_r(0.5, 1.5, 5.0),  # ethanol; 0.5-16 g/L reported (16 in cocoa pulp)
            yield_xs=_r(0.02, 0.05, 0.10),  # est.: incomplete oxidation, low yield
            maint=_r(0.6, 1.5, 3.5),  # est.; calibrated to kombucha acetic acid (Jayabalan 2007)
            t_min=_t(5.0, 8.0, 12.0),  # est.
            t_opt=_t(28.0, 30.5, 32.0),  # de Ory 1998
            t_max=_t(34.0, 36.0, 38.0),  # mesophilic strains 35-37 (Saeki 1997)
            # est.: acetic acid bacteria keep oxidising in vinegar at pH 2.5-3
            ph_min=_t(2.0, 2.4, 2.8),
            ph_opt=_t(4.0, 4.8, 5.8),  # El-Askri 2022: optimum ~5
            ph_max=_t(7.0, 7.5, 8.0),
            mic_lactic_mm=_r(200.0, 400.0, 800.0),
            mic_acetic_mm=_r(500.0, 800.0, 1300.0),  # ~6 % total acid (El-Askri 2022)
            aw_min=_t(0.92, 0.94, 0.96),
            ethanol_max=_r(70.0, 100.0, 126.0),  # up to 16 % v/v, strain-dependent
            x_max=_t(6.0, 7.0, 8.0),
            h0=_r(1.0, 3.0, 8.0),  # days-long lags without a mother (est.)
            k_death=_r(0.0005, 0.002, 0.008),
            obligate_aerobe=True,
            sources=(
                "Moreno-Zambrano et al. 2018 R Soc Open Sci 5:180964",
                "de Ory et al. 1998 AMB 49:189",
                "El-Askri et al. 2022 Microorganisms 10:1741",
            ),
        ),
        OrganismKinetics(
            name="Acetobacter pasteurianus",
            kingdom="bacteria",
            role="vinegar bacterium: oxidises ethanol to acetic acid, tolerates strong vinegar",
            channels=(
                Channel(("ethanol",), ACETIC_OXIDATION),
                Channel(("hexoses",), GLUCONIC, weight=0.1),
            ),
            mu_max=_r(0.25, 0.38, 0.47),
            ks=_r(0.5, 1.5, 5.0),
            yield_xs=_r(0.02, 0.05, 0.10),
            maint=_r(0.6, 1.5, 3.5),
            t_min=_t(5.0, 8.0, 12.0),
            t_opt=_t(28.0, 30.5, 32.0),
            t_max=_t(36.0, 38.0, 42.0),  # heat-tolerant strains to 40-42 (Wang 2025)
            ph_min=_t(1.8, 2.1, 2.5),  # the vinegar organism: works at pH 2.5-3
            ph_opt=_t(3.5, 4.3, 5.5),
            ph_max=_t(7.0, 7.5, 8.0),
            mic_lactic_mm=_r(200.0, 400.0, 800.0),
            mic_acetic_mm=_r(700.0, 1100.0, 1600.0),  # 3-10 % total acid
            aw_min=_t(0.92, 0.94, 0.96),
            ethanol_max=_r(100.0, 126.0, 150.0),  # optimum 6-8 %, tolerated to 16 % v/v
            x_max=_t(6.0, 7.0, 8.0),
            h0=_r(1.0, 3.0, 8.0),
            k_death=_r(0.0005, 0.002, 0.008),
            obligate_aerobe=True,
            sources=("El-Askri et al. 2022 Microorganisms 10:1741", "Saeki et al. 1997 BBB 61:138"),
        ),
        OrganismKinetics(
            name="Gluconacetobacter xylinus",
            kingdom="bacteria",
            role="cellulose-forming acetic acid bacterium (the SCOBY): glucose -> gluconic acid",
            channels=(
                # part of the glucose becomes the cellulose pellicle, not tracked as a pool
                Channel(("hexoses",), {"gluconic_acid": 0.8}),
                Channel(("ethanol",), ACETIC_OXIDATION, weight=0.5),
            ),
            mu_max=_r(0.05, 0.15, 0.30),  # est.
            ks=_r(0.5, 1.5, 5.0),  # est. 0.2-5
            yield_xs=_r(0.02, 0.05, 0.10),
            maint=_r(0.4, 1.0, 2.5),  # ~0.7 g/L/d gluconic acid after day 6 (Chen & Liu 2000)
            t_min=_t(7.0, 10.0, 13.0),  # est.
            t_opt=_t(27.0, 29.0, 31.0),  # 30 °C best for cellulose
            t_max=_t(34.0, 36.0, 38.0),
            ph_min=_t(2.5, 3.0, 3.5),  # est.
            ph_opt=_t(4.5, 5.0, 5.8),
            ph_max=_t(7.0, 7.5, 8.0),
            mic_lactic_mm=_r(200.0, 400.0, 800.0),
            mic_acetic_mm=_r(500.0, 900.0, 1500.0),  # Komagataeibacter: 10-20 % acid
            aw_min=_t(0.92, 0.94, 0.96),
            ethanol_max=_r(70.0, 100.0, 126.0),
            x_max=_t(5.8, 6.5, 7.3),
            h0=_r(2.0, 5.0, 12.0),  # gluconic acid appears only after ~6 d (Chen & Liu 2000)
            k_death=_r(0.0005, 0.002, 0.008),
            obligate_aerobe=True,
            sources=("Chen & Liu 2000 J Appl Microbiol 89:834",),
        ),
        OrganismKinetics(
            name="Lactobacillus plantarum",
            kingdom="bacteria",
            role="acid-tolerant lactic acid bacterium: sugars -> lactic acid; finishes the ferment",
            channels=(Channel(("hexoses", "sucrose", "maltose"), HOMOLACTIC),),
            mu_max=_r(0.4, 0.7, 1.2),  # 0.8 (0.4-1.9 in MRS), x0.85 food factor
            ks=_r(0.4, 0.8, 2.0),  # est. 0.1-2
            yield_xs=_r(0.12, 0.19, 0.25),  # 0.9 / L-P alpha 4.7 (Passos 1994)
            maint=_r(0.35, 0.7, 1.2),  # L-P beta 0.65 g lactate/g/h (Passos 1994)
            t_min=_t(2.0, 5.0, 8.3),  # 2.0 (MRS) - 7.8 (milk); 3.4-8.3 over strains
            t_opt=_t(33.0, 35.5, 37.5),
            t_max=_t(40.0, 41.0, 43.0),
            ph_min=_t(3.15, 3.3, 3.5),  # Aryani 2016; 3.37 in cucumber (Passos 1993)
            ph_opt=_t(5.5, 6.0, 6.5),
            ph_max=_t(8.0, 8.5, 9.0),
            mic_lactic_mm=_r(35.0, 69.0, 120.0),  # 29-38 at pH 4.5; 69 in cucumber
            mic_acetic_mm=_r(100.0, 150.0, 220.0),  # Passos 1993
            aw_min=_t(0.93, 0.945, 0.955),  # 0.936-0.953; 11.8 % NaCl max
            ethanol_max=_r(50.0, 80.0, 120.0),
            x_max=_t(8.5, 9.0, 9.4),  # 1e8-1e9 CFU/g (Plengvidhya 2007)
            h0=_r(1.0, 3.0, 7.0),  # est.
            k_death=_r(0.001, 0.003, 0.01),
            cell_mass_g=LAB_CELL_G,
            sources=(
                "Passos et al. 1993 AMB 40:143",
                "Passos et al. 1994 AEM 60:2627",
                "Aryani et al. 2016 AEM 82:4896",
            ),
        ),
        OrganismKinetics(
            name="Leuconostoc mesenteroides",
            kingdom="bacteria",
            role="cold-tolerant heterofermentative starter: sugars -> lactic + acetic acid, "
            "ethanol, CO2; dominates early, then declines as acid builds",
            channels=(Channel(("hexoses", "sucrose"), HETEROLACTIC),),
            mu_max=_r(0.4, 0.6, 1.0),  # Dols 1997: 0.6 glucose/fructose, 0.98 sucrose
            ks=_r(0.4, 1.0, 3.0),  # est. 0.3-3
            yield_xs=_r(0.10, 0.15, 0.22),
            maint=_r(0.3, 0.6, 1.1),
            t_min=_t(-1.0, 2.0, 5.0),  # grows at 5-37 °C (Ko 2024); cardinals est.
            t_opt=_t(22.0, 26.0, 30.0),
            t_max=_t(35.0, 37.0, 40.0),
            ph_min=_t(4.3, 4.6, 5.0),  # effective in lactate (McDonald 1990)
            ph_opt=_t(6.0, 6.5, 7.0),
            ph_max=_t(8.0, 8.5, 9.0),
            mic_lactic_mm=_r(15.0, 30.0, 60.0),
            mic_acetic_mm=_r(40.0, 80.0, 150.0),
            aw_min=_t(0.95, 0.962, 0.975),  # ~6 % (4-8 %) NaCl max, est.
            ethanol_max=_r(50.0, 80.0, 120.0),
            x_max=_t(8.3, 8.8, 9.3),
            h0=_r(2.0, 4.0, 8.0),  # lag 12-24 h in raw cabbage at 18-22 °C
            k_death=_r(0.002, 0.006, 0.02),
            cell_mass_g=COCCUS_CELL_G,
            sources=("Dols et al. 1997 AEM 63:2159", "McDonald et al. 1990 AEM 56:2120"),
        ),
        OrganismKinetics(
            name="Lactobacillus sanfranciscensis",
            kingdom="bacteria",
            role="sourdough lactic acid bacterium: maltose -> lactic + acetic acid, CO2",
            channels=(
                Channel(("maltose",), HETEROLACTIC),
                Channel(("hexoses",), HETEROLACTIC, weight=0.3),
            ),
            mu_max=_r(0.5, 0.71, 0.9),  # Gänzle 1998
            ks=_r(0.4, 1.0, 3.0),  # est. 0.3-5
            yield_xs=_r(0.08, 0.13, 0.2),
            maint=_r(0.6, 1.2, 2.5),  # est.; sourdough acidifies in 8-16 h (Minervini 2012)
            t_min=_t(3.0, 8.0, 15.0),  # est.
            t_opt=_t(31.0, 32.0, 33.5),  # Gänzle 1998; Brandt 2004
            t_max=_t(38.0, 40.0, 41.0),
            ph_min=_t(3.8, 3.94, 4.1),  # Gänzle 1998
            ph_opt=_t(5.2, 5.47, 5.8),
            ph_max=_t(6.5, 6.67, 7.0),
            mic_lactic_mm=_r(60.0, 120.0, 200.0),
            mic_acetic_mm=_r(160.0, 240.0, 350.0),  # >160 mM tolerated (Gänzle 1998)
            aw_min=_t(0.955, 0.965, 0.975),  # fully inhibited by ~4 % NaCl (Gänzle 1998)
            ethanol_max=_r(60.0, 80.0, 120.0),  # affects growth only above 5 %
            x_max=_t(9.0, 9.3, 9.6),  # ~1e9 CFU/g (Minervini 2012)
            h0=_r(1.0, 2.5, 6.0),
            k_death=_r(0.001, 0.004, 0.012),
            cell_mass_g=LAB_CELL_G,
            sources=(
                "Gänzle et al. 1998 AEM 64:2616",
                "Brandt et al. 2004 Eur Food Res Technol 218:333",
            ),
        ),
        OrganismKinetics(
            name="Lactococcus lactis",
            kingdom="bacteria",
            role="mesophilic dairy starter: lactose -> lactic acid (acidifies milk)",
            channels=(Channel(("lactose", "hexoses"), {"lactic_acid": 0.88}),),
            mu_max=_r(0.8, 1.1, 1.3),  # Boonmee 2003; Chen 2015 (1.13, MG1363)
            ks=_r(0.3, 0.7, 1.5),  # est. 0.1-1
            yield_xs=_r(0.10, 0.15, 0.22),
            maint=_r(1.2, 2.5, 4.0),  # L-P beta 3.02 (Boonmee 2003, units unverified)
            t_min=_t(5.0, 8.0, 11.0),  # est.
            t_opt=_t(30.0, 32.0, 34.0),  # Chen 2015; Åkerberg 1998
            t_max=_t(38.5, 40.0, 41.5),
            ph_min=_t(4.2, 4.4, 4.6),  # est.
            ph_opt=_t(6.0, 6.3, 6.6),
            ph_max=_t(8.0, 8.5, 9.0),
            mic_lactic_mm=_r(15.0, 30.0, 60.0),  # lactate-sensitive (Boonmee 2003)
            mic_acetic_mm=_r(40.0, 80.0, 150.0),
            aw_min=_t(0.965, 0.975, 0.98),  # ~4 % NaCl (subsp. lactis), est.
            ethanol_max=_r(40.0, 70.0, 100.0),
            x_max=_t(8.8, 9.2, 9.6),
            h0=_r(0.5, 1.5, 4.0),
            k_death=_r(0.002, 0.005, 0.015),
            cell_mass_g=COCCUS_CELL_G,
            sources=(
                "Boonmee et al. 2003 Biochem Eng J 14:127",
                "Chen et al. 2015 Sci Rep 5:14199",
                "Åkerberg et al. 1998 AMB 49:682",
            ),
        ),
        OrganismKinetics(
            name="Lactobacillus kefiri",
            kingdom="bacteria",
            role="kefir-grain heterofermentative bacterium: lactose -> lactic + acetic acid, CO2",
            channels=(Channel(("lactose", "hexoses"), HETEROLACTIC),),
            mu_max=_r(0.15, 0.3, 0.5),  # est.
            ks=_r(0.4, 1.0, 3.0),
            yield_xs=_r(0.08, 0.13, 0.2),
            maint=_r(0.2, 0.5, 1.0),
            t_min=_t(7.0, 10.0, 13.0),  # est.
            t_opt=_t(28.0, 30.0, 33.0),
            t_max=_t(39.0, 42.0, 44.0),
            ph_min=_t(3.5, 3.8, 4.1),
            ph_opt=_t(5.0, 5.5, 6.0),
            ph_max=_t(8.0, 8.5, 9.0),
            mic_lactic_mm=_r(40.0, 90.0, 160.0),
            mic_acetic_mm=_r(80.0, 150.0, 250.0),
            aw_min=_t(0.94, 0.955, 0.965),
            ethanol_max=_r(50.0, 80.0, 120.0),
            x_max=_t(7.5, 8.2, 8.8),
            h0=_r(0.5, 1.5, 4.0),
            k_death=_r(0.001, 0.004, 0.012),
            cell_mass_g=LAB_CELL_G,
            sources=("estimates; Irigoyen et al. 2005 Food Chem 90:613 for counts",),
        ),
        OrganismKinetics(
            name="Lactobacillus kefiranofaciens",
            kingdom="bacteria",
            role="kefir-grain bacterium: lactose -> lactic acid + kefiran (grain polysaccharide)",
            channels=(Channel(("lactose", "hexoses"), {"lactic_acid": 0.80}),),
            mu_max=_r(0.1, 0.2, 0.4),  # est. (Cheirsilp 2001 model structure)
            ks=_r(0.4, 1.0, 3.0),
            yield_xs=_r(0.08, 0.13, 0.2),
            maint=_r(0.2, 0.5, 1.0),
            t_min=_t(7.0, 10.0, 13.0),
            t_opt=_t(28.0, 30.0, 33.0),
            t_max=_t(37.0, 40.0, 43.0),
            ph_min=_t(3.7, 4.0, 4.3),
            ph_opt=_t(5.0, 5.5, 6.0),
            ph_max=_t(8.0, 8.5, 9.0),
            mic_lactic_mm=_r(40.0, 90.0, 160.0),
            mic_acetic_mm=_r(80.0, 150.0, 250.0),
            aw_min=_t(0.94, 0.955, 0.965),
            ethanol_max=_r(50.0, 80.0, 120.0),
            x_max=_t(7.5, 8.2, 8.8),
            h0=_r(0.5, 1.5, 4.0),
            k_death=_r(0.001, 0.004, 0.012),
            cell_mass_g=LAB_CELL_G,
            sources=("Cheirsilp et al. 2001 AMB 57:639 (structure); values est.",),
        ),
        OrganismKinetics(
            name="Tetragenococcus halophilus",
            kingdom="bacteria",
            role="salt-loving lactic acid bacterium: sugars -> lactic acid in miso and fish sauce",
            channels=(Channel(("hexoses", "maltose", "sucrose"), {"lactic_acid": 0.85}),),
            mu_max=_r(0.08, 0.2, 0.4),  # est.
            ks=_r(0.4, 1.0, 3.0),
            yield_xs=_r(0.08, 0.13, 0.2),
            maint=_r(0.1, 0.3, 0.7),
            t_min=_t(7.0, 10.0, 13.0),  # est.
            t_opt=_t(28.0, 30.0, 33.0),  # Justé 2014
            t_max=_t(38.0, 40.0, 42.0),  # most strains not at 40 °C
            ph_min=_t(4.8, 5.1, 5.5),  # Röling & van Verseveld 1997; Justé 2014
            ph_opt=_t(6.8, 7.2, 8.0),
            ph_max=_t(9.0, 9.5, 10.0),
            mic_lactic_mm=_r(30.0, 60.0, 120.0),
            mic_acetic_mm=_r(60.0, 120.0, 200.0),
            aw_min=_t(0.77, 0.80, 0.84),  # grows up to 18-26 % NaCl
            ethanol_max=_r(40.0, 70.0, 100.0),
            x_max=_t(7.5, 8.2, 8.8),
            h0=_r(1.0, 3.0, 8.0),
            k_death=_r(0.0005, 0.002, 0.006),
            aw_opt=0.955,  # optimum 5-10 % NaCl
            cell_mass_g=COCCUS_CELL_G,
            sources=(
                "Justé et al. 2014 in Lactic Acid Bacteria (Wiley)",
                "Röling & van Verseveld 1997 Antonie van Leeuwenhoek 72:239",
                "Link et al. 2021 BMC Microbiol 21:320",
            ),
        ),
        OrganismKinetics(
            name="Aspergillus oryzae",
            kingdom="mold",
            role="koji mold: grows on steamed grain (needs air), makes amylases and proteases "
            "that turn starch into sugar and protein into amino acids",
            # Solid-state growth: hyphae digest the starch they grow into (standard logistic
            # SSF growth), so the mold is not limited by free sugar in the bed.
            channels=(Channel(("hexoses", "maltose", "starch"), RESPIRATION),),
            # est.; logistic growth on steamed rice, calibrated to full growth in 40-48 h
            # at 30 °C (Ito & Matsuyama 2021; Bechman et al. 2012)
            mu_max=_r(0.15, 0.25, 0.4),
            ks=_r(0.5, 1.0, 3.0),
            yield_xs=_r(0.30, 0.45, 0.55),
            maint=_r(0.005, 0.02, 0.06),
            t_min=_t(8.0, 10.0, 13.0),  # est.
            t_opt=_t(30.0, 32.5, 35.0),  # te Biesebeke 2002
            t_max=_t(42.0, 44.0, 46.0),  # no growth above 44 °C
            ph_min=_t(2.0, 2.5, 3.0),
            ph_opt=_t(5.0, 5.5, 6.5),
            ph_max=_t(8.0, 8.8, 9.5),
            mic_lactic_mm=_r(150.0, 300.0, 600.0),
            mic_acetic_mm=_r(30.0, 60.0, 120.0),
            aw_min=_t(0.78, 0.80, 0.83),
            ethanol_max=_r(40.0, 60.0, 90.0),
            x_max=_r(8.0, 15.0, 30.0),  # g dry mycelium / kg koji, est.
            h0=_r(0.7, 1.5, 3.0),  # spore germination, ~6-10 h at 30 °C
            k_death=_r(0.0003, 0.001, 0.004),
            aw_opt=0.99,
            cell_mass_g=None,
            obligate_aerobe=True,
            makes_enzymes=True,
            sources=(
                "te Biesebeke et al. 2002 FEMS Yeast Res 2:245",
                "Bechman et al. 2012 J Food Sci 77:M318",
                "Oguro et al. 2019 J Biosci Bioeng 127:570",
                "Ito & Matsuyama 2021 J Fungi 7:658",
            ),
        ),
    ]
}
