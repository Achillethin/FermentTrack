# Aroma curation (increment B) — compounds, evidence, template parameters

**Date:** 2026-10-05
**Status:** DRAFT for scientific review (spec 2026-10-02 § 5: an independent review precedes encoding in `compounds.py`).
**Builds on:** `2026-10-02-flavour-nutrition-design.md` § 1, 4, 5, 7, 8, 9 and its increment-A implementation notes. Research inputs: `docs/superpowers/research/aroma/BRIEF.md` and files `01`–`05` in that folder.

## 1. Status, sources, how to read

**What this is.** The curation passes 1–3 of spec § 5, written from five literature slices: identity and thresholds (01), kombucha/vinegar/sourdough/koji (02), lacto-ferments/kefir/cheese (03), miso/garum (04), template parameters (05). No new searches were made for this document; anything missing is listed as a gap (§ 10), never filled from memory.

**Source tags.** Every number carries a tag that points into a research file's Sources list: `<file>:<tag>`.

| Prefix | Tags (as in that file's Sources list) |
|---|---|
| `01:` | `CZ` Czerny et al. 2008 Table 1; `LSB` Leibniz-LSB@TUM Odorant DB v1.2 (basic table or a literature row it names); `LEF` Leffingwell compilation; `HSDB` PubChem/HSDB; `MJ20` Marcinkowska & Jeleń 2020 (abstract); `Schwab13`; `BvG93` Boelens & van Gemert 1993; `Kelting20` |
| `02:` | `K1`–`K6` kombucha, `V1`–`V14` vinegar, `S1`–`S9` sourdough, `J1`–`J4` koji |
| `03:` | `S1`–`S37` (sauerkraut, kimchi, cucumber, kefir, cheese). **Not** the same as `02:S*` |
| `04:` | `M1`–`M11` miso, `G1`–`G9` garum |
| `05:` | first author + year, e.g. `05:Godillot23`, `05:Rollero17`, `05:RameyOugh80`, `05:Sander23` (05's numbered Sources list) |

"**est.**" = no source gives the value; a one-line reason follows and the prior is deliberately wide. "**derived**" = arithmetic on sourced numbers (the arithmetic is shown).

**Caveats carried from the research files.** "(abs.)" = abstract only. "(fig.)" = read from a figure, ±~10 %. "(semi)" = internal-standard equivalent or response factor 1: good for shape and order of magnitude, not absolute. "(area)" = relative peak area: shape or presence only. "(app.)" = apparent value from a porous-polymer trap without recovery correction (`04:M2`, `04:M8`, `04:M10`): a lower bound (HEMF is ×8–10 low, `04:M9` p. 162).

**Priors.** `(median, lo, hi)` is a median and a ~90 % range, as `Prior(median, lo, hi, scale)` in `priors.py`; log scale unless marked "lin".

**Tiers** (spec § 4.3), refined here with an **anchor** per cell:

| Tier | Meaning | Anchor values | Test (§ 7) |
|---|---|---|---|
| calibrated | a published time course in this ferment | `abs` (absolute concentrations), `semi`, `shape` (area, figure direction, "increased" in an abstract) | shape + timing always; magnitude ×/÷ 3 only when `abs` |
| reported | present at an end point (concentration, AEDA, OAV), no time course | `abs`, `semi`, `presence` | end point ×/÷ 3 when `abs`; otherwise non-negative only |
| plausible | precursor or producer present, not reported in this ferment | — | non-negative, mass balance |
| drop | no precursor or producer in this ferment | — | — |

**Series sums** (the headline aroma strip) include a compound in a ferment only when (i) its tier is calibrated, or reported with an `abs` or `semi` anchor, (ii) its threshold basis is `measured` or `class` (§ 3), and (iii) it is not "P0 pending" for that ferment (it would compute zero). Everything else appears in the drill-down only. This is the one place this document tightens spec § 4.3: a "reported (presence)" compound has no magnitude to stand on, so it must not drive the headline.

**"†" in § 4** marks a cell whose only route is an ingredient precursor not yet curated (§ 6): it computes ~0, and its test is deferred until the precursor exists.

**Compound status.** `active`; `active, conc-only` (no threshold, kept because it is a branch of a modelled pool and its mass balance matters); `inactive` (the producing organism is not in the model); `drop` (no usable threshold and not needed for a mass balance).

## 2. Design changes from the research

Each row changes or sharpens spec 2026-10-02 § 4.

| # | Change against spec § 4 | Why | Source |
|---|---|---|---|
| D1 | **Branched fusel alcohols and their acids/acetates are a b-term** (yield per g sugar fermented by yeast), not an amino-acid precursor pool `rᵢ·Pᵢ`. Yields: 3-+2-methylbutanol 0.42–0.72 mg/g sugar, 2-methylpropanol 0.18–0.40 mg/g. The free-amino-acid pool does not cap them (its yield effect is ±15 %, inside the prior). | ¹³C-Leu/Val labelling: only 2–8 % of isoamyl alcohol and 5–15 % of isobutanol came from the exogenous amino acid; ">90 % of the acids and higher alcohols (and their acetate esters)" come from central carbon metabolism. Matters for N-poor tea and brine. | `05:Rollero17` Abstract, Figs 3–6; `05:Godillot23` Table 2 (÷ 200 g/L sugar, derived) |
| D2 | **2-Phenylethanol is also a b-term** (derived yield, § 5.1); **methionol and methional keep an amino-acid precursor term** (methionine share of the free-amino-acid pool). | Methionol rose ×~140 when methionine was the nitrogen source: precursor-limited. No source splits 2-phenylethanol into de novo vs phenylalanine-derived, and it rises strongly in protein-free tea (`02:K1`, `02:K2`), so a sugar-linked yield is the form the data support. | `05:JL26` Fig. 7 text; `05:Hazelwood08` |
| D3 | **Diacetyl is a precursor chain, not a yield.** Citrate (milk pool) → α-acetolactate (new non-odorous tracer state) → diacetyl (chemical oxidative decarboxylation, small share) or acetoin (non-oxidative decarboxylation); diacetyl → acetoin → 2,3-butanediol by reduction (yeast, *Leuconostoc*; switches on near citrate depletion). | "Diacetyl was not found as a direct metabolite of citrate or pyruvate metabolism"; 30–50 % of citrate-derived pyruvate goes to α-acetolactate/acetoin. α-Acetolactate peaks at citrate exhaustion (6 h), then decays while diacetyl and acetoin keep rising. | `05:Verhue91`; `03:S30` Fig. 1 (fig.); `03:S27`, `03:S28` (abs.) |
| D4 | **Milk citrate prior = 9.0 mmol/L (6.3–11.7, lin) ≈ 1.74 g/kg citric acid (1.21–2.25).** The "≈ 9 mmol/L" and "1.9–2.2 g/L" values are the same quantity from different populations (§ 6). | Grelet: mean 9.04 mmol/L, n = 506 herds in three countries, MIR SD 1.65 mmol/L (Chen 2024) → ±1.645 SD = 6.3–11.7. Garnsworthy's 9.7–11.3 mmol/L (24 cows, one diet) = 1.86–2.17 g/L at 192.1 g/mol, inside that range. | `05:Grelet16`, `05:Chen24`, `05:Garnsworthy06` = `03:S35` |
| D5 | **pH-corrected odour activity for volatile acids and trimethylamine:** OAV = C · f_neutral(pH) / threshold, with f_neutral = 1/(1 + 10^(pH − pKa)) for acids and 1/(1 + 10^(pKa − pH)) for the amine, on the trajectory's pH (the same protonated-fraction idea as `derived.py`'s sour activity). The water threshold is read as a threshold of the neutral form (est.: a dilute acid at threshold level in unbuffered water is ≳ 85 % protonated, derived for acetic acid at 99 mg/L: pH ≈ 3.8, 90 % neutral). | Only the neutral species is volatile. Check: trimethylamine's water threshold 0.87 µg/kg with pKa 9.8 predicts ≈ 690 µg/kg at pH 6.9; the measured buffer value is 440 µg/kg (derived). Ferments at pH 5–6.5 (cheese, miso, garum) would otherwise overstate acid odour by up to ×50. | `01:` caveat (i), acid and TMA rows; `01:LSB` row Mall & Schieberle 2017 (TMA, pH 6.9) |
| D6 | **Inactive until an organism exists:** 4-ethylguaiacol and 4-ethylphenol (*Brettanomyces/Dekkera* vinylphenol reductase; *Candida*/*Torula* in soy) and trimethylamine (TMAO-reducing spoilage bacteria). No producer is faked; their kombucha time courses are recorded as future calibration targets. | Kombucha shows both ethylphenols clearly (`02:K1`, `02:K2`) but the model's kombucha yeast is an *S. cerevisiae* stand-in; rice miso with *Z. rouxii* only has none; salmon sauce 4-EG came from *C. versatilis* only. No model organism is documented as a TMAO reducer. | `02:K1`–`K4`; `04:M2` p. 1096; `04:G7` (abs.); `04:G2` Discussion |
| D7 | **Compounds without a water threshold are decided one by one** (§ 3, § 8): allyl isothiocyanate keeps a **class** threshold (the 5–200 µg/L range of 19 ITCs in water, compound named in the abstract) and counts in series sums, because the pungent note of sauerkraut is otherwise empty; 3-butenyl isothiocyanate gets the same range as an **est.** threshold (compound not named) and is drill-down only; allyl cyanide and 2,3-butanediol are **conc-only** (branches of the sinigrin and C4 pools); 4-methylthio-3-butenyl ITC, diallyl disulfide, allyl methyl disulfide, zingiberene and S-methyl thioacetate are **dropped**. | No orthonasal water threshold in CZ, LSB, LEF or the further sources searched. Kraut sulfur flavour tracks DMTS, which has a good threshold; AITC tracks raw-cabbage flavour. | `01:MJ20` (abs.); `01:BvG93` Table II; `03:S1` Table 5, Fig. 8 |
| D8 | **Semi-quantitative and area time courses define shape and timing only.** Magnitudes come from absolute studies where they exist: kombucha `02:K3`, `02:K4`; kefir `03:S18`–`S20`, `03:S26` (abs.); cheese chain `03:S30` (fig.); cucumber `03:S13`; sauerkraut `03:S1`; miso `04:M9` (solvent extraction, 90–94 % recovery) and `04:M1` (GC-FID). Everything else is `semi` or `shape` (§ 4). `02:K1`'s "ppm" are ~10³× off and never set a magnitude. | Mixing semi and absolute values would put the prior median wrong by up to 10³. | `02:K1` caveat; `02:K2` caveat; `04:M9` p. 162 |
| D9 | **Acetate esters are a fraction of their parent alcohol's flux** (isoamyl acetate : isoamyl alcohol = 0.0062–0.015 mol/mol), not an independent yield; MCFA ethyl esters are b-terms with an excreted fraction. | Acetate esters carry the parent alcohol's ¹³C label; the ratio was measured directly. Excretion falls with chain length (C6 ~100 %, C8 54–68 %, C10 8–17 %). | `05:Rollero17` Figs 4, 6; `05:Godillot23` Table 2; `05:Saerens10` Intro |
| D10 | **Volatility loss has two physical forms instead of one free k⁰:** CO₂ stripping (gas flow from the engine's CO₂ flux × Henry's K_aw × an efficiency factor) for ferments whose gas escapes, and a surface term k_surf·K_aw for open vessels (kombucha, vinegar, koji bed). Dough keeps its gas (`co2_escapes=False`): no stripping. | K_aw spans 10⁻⁵ (2-phenylethanol, acetic acid) to 0.1 (methanethiol); measured ester losses (14–60 %) match CO₂ stripping within ×2–4; higher alcohols lose < 3 %. | `05:Sander23`; `05:Godillot23` § 3.1.2 |
| D11 | **Acetic acid bacteria are mainly a sink**: c_AAB oxidises fusel alcohols (with a matching source on the fusel acid), acetaldehyde, and 2,3-butanediol → acetoin. **Vinegar starts from a base with yeast volatiles** (wine/cider priors, § 6), since the engine's vinegar has no yeast stage. | Fusel alcohols and acetaldehyde are consumed during acetification; acetoin is the one product; kombucha 3-methylbutanol falls late as AAB take over. | `02:V1` (abs.), `02:V3`, `02:V4`, `02:V11`; `02:K2` |
| D12 | **Ingredient-borne compounds dominate several ferments; microbes modulate them.** Flour aldehydes (sourdough), tea terpenes (kombucha), cabbage/cucumber LOX volatiles and sulfides (lacto), milk lactones and fatty acids (kefir, cheese) start as **initial pools** with microbial reduction (c_ij: lactobacilli, leuconostocs, yeast; not lactococci) or first-order loss. Linalool in kombucha also has a yeast-dependent glycoside release. | Wheat/rye sourdough: "no new odorants", lipid aldehydes fall; tea terpenes decline from day 0 except linalool; kimchi sulfides peak at salting and crash by day 3. | `02:S1`, `02:S2` (abs.); `02:K1`, `02:K2`, `02:K4`; `03:S10`; `05:Engels22` |
| D13 | **HEMF is yeast-gated, not plain slow Maillard.** A koji-derived, unstable pentose-Maillard precursor is converted only by *Z. rouxii*; HEMF then decomposes chemically with a strong temperature dependence (k ≈ 0.031 d⁻¹ at 30 °C, 0.008 d⁻¹ at 20 °C, ≈ 0 at 10 °C; Q10 ≈ 3.9, derived). Norfuraneol is consumed by yeast; maltol is made in soybean cooking and only lost in the mash. | No HEMF without yeast or without soybean; warm miso peaks early then falls; yeast-stopped miso loses HEMF at 30 °C but not at 10 °C. | `04:M9` Fig. 1, Table 3; `04:M1` Fig. 4–6; `04:M2` Table 2; `04:M10` Table 1 |
| D14 | **Sinigrin gives little volatile product**: < 5 % of sinigrin is recovered as AITC + allyl cyanide, so the glucosinolate template has a volatile-product share (prior median 0.05) besides the ITC/nitrile split (wide, 0.1–0.9) and a loss rate. | Measured recovery; nitriles can be 82 % of products in some cabbages, acid shifts the split towards ITC. | `05:CiskaPathak04` (abs.); `05:Puc25b`; `05:Hanschen24` (abs.) |
| D15 | **New non-odorous tracer states**: citrate, α-acetolactate, sinigrin/gluconapin, SMCSO, bound tea terpenes, ferulic acid, HEMF precursor. They are internal (not in series, not in the API compound list) and carry the mass balance tests of spec § 9. | Needed by D3, D12–D14. | — |
| D16 | **Table-D key odorants are not added in increment B** (e.g. α-terpineol and linalool oxides in kombucha, (E,E)-2,4-decadienal in sourdough, MMTSO₂ in sauerkraut, 2-furanmethanethiol in miso, 2-ethylpyridine and indole in fish sauce). | No threshold was curated for them (pass 1 covered the spec § 4.2 list only). Listed in § 10 for the next pass. | `02`, `03`, `04` tables D |
| D17 | **The engine diagnostics hook does not exist yet.** `engine.make_rhs(p, max_evals)` has no `diagnostics` argument on this branch; the per-organism μⱼXⱼ and vⱼ that every b- and a-term needs must be built first (§ 11). | Spec § 1 listed it under increment A; it was not implemented. | `src/fermenttrack/prediction/engine.py` lines 330–497 |

## 3. Compound table

**Identity** (PubChem CID · ChEBI · KEGG) is copied from `01` table A, where every ID was resolved twice and checked against its ChEBI/KEGG entry; "—" = no entry. **Descriptor** is the Munich aroma language (`01:CZ`, else `01:LSB`); series as assigned in `01`.

**Threshold prior rule** (orthonasal detection in water, µg/kg):
- median = `01`'s median over distinct sources (geometric mean of the two middle values when even);
- lo/hi = min/max of the determinations actually opened (`01:CZ` D, `01:LSB` TW and its rows, both ends of a `01:LEF` range, `01:HSDB`, named papers). The CZ *lit* column and `01:Schwab13`'s secondary ranges are **excluded** (secondary, primaries unopened; they would make e.g. ethyl butanoate span five decades) unless they are the only source; they are recorded in § 9;
- widened to at least ×/÷ 3 around the median, or ×/÷ 5 when only one source or one compiled value exists (est.: thin evidence).
- On top, one **matrix factor** per ensemble member, shared by all compounds, `(1, 1/3, 3)` est. (the ×/÷ ~3 matrix allowance of spec § 3; shared so that series sums do not average it away).

**Threshold basis:** `measured` = at least one water determination; `class` = a measured class range with the compound named in the source; `est.` = a class range without the compound named; `none`.

**pH** = neutral-fraction correction of D5, with pKa: acetic 4.76 (`engine.ACIDS`), 3-methylbutanoic ≈ 4.8 (`01` row); the other carboxylic acids 4.8 est. (same class, no value in the files); trimethylamine 9.8 (`01` row, base).

**Templates** (§ 5): T1 Ehrlich/fusel · T2 esters and MCFA · T3 acetaldehyde · T4 citrate → α-acetolactate → C4 · T5 chemical esterification/hydrolysis · T6 glucosinolates · T7 sulfur · T8 lipid oxidation, mould C8 and milk fat · T9 terpenoids · T10 hydroxycinnamic decarboxylation · T11 slow chemistry (Maillard/Strecker/HEMF, cooked-ingredient carry-through) · T12 volatility loss (applies to every compound, not listed per row) · `engine` = existing pool.

"P0 pending" = active, but its only route is an ingredient precursor that no opened source quantifies: it computes zero and the ingredient appears in `sensory.not_modelled_aroma.ingredients` (spec § 4.1).

| key | name | CID · ChEBI · KEGG | descriptor (series) | threshold (median, lo, hi) µg/kg | basis · source | pH | template | status |
|---|---|---|---|---|---|---|---|---|
| methylbutanal_3 | 3-methylbutanal | 11552 · 16638 · C07329 | malty (malty) | 0.45, 0.15, 2.0 | measured · CZ, LSB, LEF | — | T1 + T11 | active |
| methylbutanal_2 | 2-methylbutanal | 7284 · 16182 · C02223 | malty (malty) | 1.5, 0.50, 4.5 | measured · CZ, LSB, LEF | — | T1 + T11 | active |
| methylpropanal_2 | 2-methylpropanal | 6561 · 48943 · C22919 | malty (malty) | 0.48, 0.10, 2.3 | measured · CZ, LEF | — | T1 + T11 | active |
| phenylacetaldehyde | phenylacetaldehyde | 998 · 16424 · C00601 | floral, honey-like (floral) | 4.6, 1.5, 14 | measured · LSB, LEF | — | T1 + T11 | active |
| methional | methional | 18635 · 49017 · — | cooked potato-like (sulfurous) | 0.29, 0.10, 0.87 | measured · CZ, LEF | — | T1 (Met) + T11 | active |
| methylbutanol_3 | 3-methylbutan-1-ol | 31260 · 15837 · C07328 | malty (malty, solvent) | 250, 83, 750 | measured · CZ, LEF | — | T1 | active |
| methylbutanol_2 | 2-methylbutan-1-ol | 8723 · 48945 · — | malty, solvent-like (malty, solvent) | 1200, 240, 6000 | measured · CZ only | — | T1 | active |
| methylpropanol_2 | 2-methylpropan-1-ol | 6560 · 46645 · C14710 | malty (malty, solvent) | 3600, 550, 19000 | measured · CZ, LSB, LEF | — | T1 | active |
| phenylethanol_2 | 2-phenylethanol | 6054 · 49000 · C05853 | flowery, honey-like (floral) | 360, 120, 1100 | measured · CZ, LEF | — | T1 | active |
| methionol | methionol | 10448 · 49019 · — | cooked potato-like (sulfurous) | 36, 7.2, 180 | measured · CZ only | — | T1 (Met) | active |
| methylbutanoic_3 | 3-methylbutanoic acid | 10430 · 28484 · C08262 | sweaty (cheesy) | 380, 120, 1100 | measured · CZ, LEF | acid 4.8 | T1 | active |
| methylbutanoic_2 | 2-methylbutanoic acid | 8314 · 37070 · C18319 | fruity, sweaty (cheesy, fruity) | 2600, 870, 7800 | measured · CZ (×2), LSB | acid 4.8 est. | T1 | active |
| methylpropanoic_2 | 2-methylpropanoic acid | 6590 · 16135 · C02632 | sweaty, cheesy (cheesy) | 16000, 5300, 60000 | measured · CZ (×2), LSB, LEF/HSDB | acid 4.8 est. | T1 | active |
| ethyl_acetate | ethyl acetate | 8857 · 27750 · C00849 | solvent-like (solvent, fruity) | 1400, 5.0, 12000 | measured (weak) · LSB, LEF | — | T2 + T5 | active |
| isoamyl_acetate | 3-methylbutyl acetate | 31276 · 31725 · C12296 | banana-like, fruity (fruity) | 7.2, 2.0, 22 | measured · LSB, LEF, HSDB | — | T2 | active |
| phenylethyl_acetate | 2-phenylethyl acetate | 7654 · 31988 · C12303 | honey-like, floral (floral, fruity) | 360, 72, 1800 | measured · LSB only | — | T2 | active |
| isobutyl_acetate | 2-methylpropyl acetate | 8038 · 50569 · — | fruity (fruity) | 76, 25, 230 | measured · LSB, LEF | — | T2 | active |
| ethyl_butanoate | ethyl butanoate | 7762 · 88764 · — | fruity (fruity) | 0.76, 0.25, 2.3 | measured · CZ, LSB, LEF | — | T2 | active |
| ethyl_hexanoate | ethyl hexanoate | 31265 · 86055 · — | fruity, pineapple-like (fruity) | 1.1, 0.37, 3.3 | measured · LSB, LEF | — | T2 | active |
| ethyl_octanoate | ethyl octanoate | 7799 · 87426 · C12292 | fruity, green (fruity) | 8.7, 1.7, 44 | measured · LSB only | — | T2 | active |
| ethyl_decanoate | ethyl decanoate | 8048 · 87430 · — | soapy, pear-like (fruity) | 74, 15, 370 | measured · LSB only (primary unnamed) | — | T2 | active |
| ethyl_2methylbutanoate | ethyl 2-methylbutanoate | 24020 · 88452 · — | fruity (fruity) | 0.016, 0.0053, 0.30 | measured · CZ, LSB, LEF | — | T2 | active |
| ethyl_2methylpropanoate | ethyl 2-methylpropanoate | 7342 · 87303 · — | fruity (fruity) | 0.094, 0.031, 0.28 | measured · CZ, LEF | — | T2 | active |
| hexanoic | hexanoic acid | 8892 · 30776 · C01585 | sweaty (cheesy) | 3000, 1000, 9000 | measured · LSB, LEF | acid 4.8 est. | T2 + T8 | active |
| octanoic | octanoic acid | 379 · 28837 · C06423 | carrot-like, musty (cheesy) | 750, 190, 3000 | measured · LSB, LEF | acid 4.8 est. | T2 + T8 | active |
| decanoic | decanoic acid | 2969 · 30813 · C01571 | soapy, musty (cheesy) | 10000, 2000, 50000 | measured · LEF only (LSB 3.5 excluded, § 9) | acid 4.8 est. | T2 + T8 | active |
| acetaldehyde | acetaldehyde | 177 · 15343 · C00084 | fresh, green (green, pungent) | 25, 8.3, 120 | measured · CZ, LSB, LEF | — | T3 | active |
| diacetyl | butane-2,3-dione | 650 · 16583 · C00741 | buttery (buttery) | 1.7, 0.57, 6.5 | measured · CZ, LSB, LEF | — | T4 | active |
| pentanedione_23 | 2,3-pentanedione | 11747 · 52774 · — | butter-like (buttery) | 3.9, 0.78, 20 | measured · LSB only | — | T4 | active |
| acetoin | 3-hydroxybutan-2-one | 179 · 15688 · C00466 | butter-like, carrot-like (buttery) | 690, 230, 2100 | measured · LSB, LEF | — | T4 | active |
| butanediol_23 | 2,3-butanediol | 262 · 62064 · — | butter-like, sweet (buttery) | none | none · `01` | — | T4 | active, conc-only (C4 pool branch) |
| ethyl_lactate | ethyl lactate | 7344 · 78321 · — | fruity (fruity) | 14000, 2800, 70000 | measured · LEF only (medium possibly aqueous ethanol) | — | T5 | active |
| hexanal | hexanal | 6184 · 88528 · — | green, grassy (green) | 3.4, 1.1, 10 | measured · CZ, LEF | — | T8 | active |
| z3_hexenal | (Z)-3-hexenal | 643941 · 23292 · C16310 | green, grassy (green) | 0.17, 0.057, 0.51 | measured · CZ, LEF | — | T8 | active |
| z3_hexenol | (Z)-3-hexen-1-ol | 5281167 · 28857 · C08492 | lettuce-like (green) | 17, 3.9, 70 | measured · CZ, LEF | — | T8 | active |
| e2_nonenal | (E)-2-nonenal | 5283335 · 142592 · — | fatty, green (green) | 0.22, 0.073, 0.69 | measured · CZ, LSB, LEF | — | T8 | active |
| nonanal | nonanal | 31289 · 84268 · — | citrus-like, soapy (green, fruity) | 1.7, 0.57, 5.1 | measured · CZ, LEF | — | T8 | active |
| pentylfuran_2 | 2-pentylfuran | 19602 · 89197 · — | vegetable-like (green) | 6.0, 1.2, 30 | measured · LEF only | — | T8 | active |
| z4_heptenal | (Z)-4-heptenal | 5362814 · 195657 · — | fishy, fish-oil-like (fishy) | 0.060, 0.0087, 0.80 | measured · CZ, LSB, LEF | — | T8 | active |
| octen3ol | 1-octen-3-ol | 18827 · 34118 · C14272 | mushroom-like (mushroom) | 6.7, 1.0, 45 | measured · LSB, LEF | — | T8 | active |
| octen3one | 1-octen-3-one | 61346 · 88900 · — | mushroom-like (mushroom) | 0.0089, 0.0030, 0.027 | measured · CZ, LEF | — | T8 | active |
| octanone_3 | 3-octanone | 246728 · 80946 · C17145 | citrus-like, fruity (fruity, mushroom) | 67, 22, 200 | measured · LSB, LEF | — | T8 | active |
| octanol_3 | 3-octanol | 11527 · 80945 · C17144 | citrus-like, soapy (mushroom) | 240, 48, 1200 | measured · LSB only (primary unnamed) | — | T8 | active |
| allyl_itc | allyl isothiocyanate | 5971 · 73224 · C19317 | pungent, mustard-like (pungent) | 32, 5.0, 200 | **class** · `01:MJ20` (abs.): 19 ITCs, 5–200 µg/L; median = geometric midpoint | — | T6 | active (badge "threshold from a class range") |
| allyl_cyanide | allyl cyanide | 8009 · 183063 · — | pungent, mustard-like (pungent) | none | none · `01` | — | T6 | active, conc-only (nitrile branch of sinigrin) |
| butenyl_itc | 3-butenyl isothiocyanate | 76922 · 138747 · — | pungent, garlic-like (pungent, sulfurous) | 32, 5.0, 200 | **est.** · `01:MJ20` class range; compound not named in the abstract | — | T6 | active, drill-down only |
| mtb_itc | (E)-4-(methylthio)-3-butenyl ITC | 5368086 · — · — | radish character impact | none ("unknown", `01:BvG93`) | none | — | — | drop (§ 8) |
| methanethiol | methanethiol | 878 · 16007 · C00409 | sulfuric, cabbage-like (sulfurous) | 0.11, 0.020, 0.59 | measured · LSB, LEF | — | T7 | active |
| dms | dimethyl sulfide | 1068 · 17437 · C00580 | asparagus-like, putrid (sulfurous) | 0.55, 0.18, 1.7 | measured · CZ, LSB, LEF | — | T7 | active |
| dmds | dimethyl disulfide | 12232 · 4608 · C08371 | cabbage-like, sulfuric (sulfurous) | 1.5, 0.16, 12 | measured · LSB, LEF | — | T7 | active |
| dmts | dimethyl trisulfide | 19310 · 4614 · C08372 | cabbage-like (sulfurous) | 0.0099, 0.0033, 0.099 | measured · CZ, LSB, LEF | — | T7 | active |
| s_methyl_thioacetate | S-methyl thioacetate | 73750 · 51280 · — | cheesy (sulfurous, cheesy) | none (beer flavour only, `01:Kelting20`) | none | — | — | drop (§ 8) |
| diallyl_disulfide | diallyl disulfide | 16590 · 4488 · C08369 | garlic-like (sulfurous) | none | none | — | — | drop (§ 8) |
| allyl_methyl_disulfide | allyl methyl disulfide | 62434 · 6854 · C08383 | garlic-like (sulfurous) | none | none | — | — | drop (§ 8) |
| linalool | linalool | 6549 · 17580 · C03985 | citrus-, bergamot-like, floral (floral, fruity) | 0.80, 0.087, 8.3 | measured · CZ (R), LSB, LEF; (S) 2.7–8.3 sets hi | — | T9 | active |
| geraniol | geraniol | 637566 · 17447 · C01500 | rose-, citrus-like (floral) | 40, 1.1, 120 | measured · CZ, LSB, LEF, HSDB | — | T9 | active |
| citronellol | citronellol | 8842 · 50462 · — | soapy, rose-like (floral) | 10, 3.3, 40 | measured · LSB (R, S), LEF | — | T9 | active |
| methyl_salicylate | methyl salicylate | 4133 · 31832 · C12305 | peppermint (herbal) | 40, 8.0, 200 | measured · LEF only | — | T9 | active |
| damascenone | (E)-β-damascenone | 5366074 · 67251 · — | baked apple-like (fruity) | 0.0060, 0.0020, 0.018 | measured · CZ, LSB, LEF | — | T9 | active |
| ionone_beta | (E)-β-ionone | 638014 · 32325 · C12287 | flowery, violet-like (floral) | 0.27, 0.021, 3.5 | measured · CZ 3.5 vs LSB 0.021 (170×, § 9) | — | T9 | active |
| geranial | geranial | 638011 · 16980 · C01499 | citrus-like (fruity) | 28, 9.3, 84 | measured · LSB, LEF | — | T9 | active, P0 pending (lemongrass, citrus, ginger) |
| neral | neral | 643779 · 29020 · C09847 | citrus-like, soapy (fruity) | 55, 18, 170 | measured · LSB, LEF | — | T9 | active, P0 pending |
| zingiberene | (−)-zingiberene | 92776 · 10115 · C09750 | spice, fresh, sharp (herbal) | none | none | — | — | drop (§ 8) |
| carvone | carvone | 7439 · 38265 · C01767 (R) / C11383 (S) | mint- (R), caraway-like (S) (herbal) | 69, 23, 210 | measured · LSB (S), LEF (R) | — | T9 | active, P0 pending (caraway, dill, mint) |
| limonene | limonene | 22311 · 15384 · C06078 | citrus-like (fruity, herbal) | 10, 3.3, 30 | measured · LSB (R, S), LEF | — | T9 | active |
| vinylguaiacol_4 | 4-vinylguaiacol | 332 · 42438 · C17883 | clove-like, smoky (phenolic) | 5.1, 1.7, 21 | measured · CZ, LSB, LEF | — | T10 | active |
| vinylphenol_4 | 4-vinylphenol | 62453 · 1883 · C05627 | phenolic, earthy (phenolic) | 28, 9.3, 84 | measured · LSB, LEF | — | T10 | active, P0 pending (p-coumaric acid) |
| ethylguaiacol_4 | 4-ethylguaiacol | 62465 · 179252 · C23176 | smoky, gammon-like (phenolic) | 50, 4.4, 150 | measured · CZ, LSB, LEF | — | T10 | **inactive** (*Brettanomyces*/*Candida*) |
| ethylphenol_4 | 4-ethylphenol | 31242 · 49584 · C13637 | phenolic (phenolic) | 13, 2.6, 65 | measured · CZ only | — | T10 | **inactive** (*Brettanomyces*/*Candida*) |
| hemf | HEMF (homofuraneol, both tautomers as one) | 33931 / 93111 · 137995 · — | caramel-like (caramel) | 27, 9.0, 81 | measured · LSB, LEF (`01:Schwab13` 0.04–21 excluded, § 9) | — | T11 | active |
| furaneol | furaneol (HDMF) | 19309 · 76247 · C20717 | caramel-like (caramel) | 53, 18, 160 | measured · CZ, LSB rows | — | T11 | active |
| norfuraneol | norfuraneol | 4564493 · 74456 · — | caramel-like (caramel) | 6900, 2100, 23000 | measured (secondary only) · `01:Schwab13` | — | T11 | active |
| maltol | maltol | 8369 · 69438 · C11918 | caramel-like (caramel) | 13000, 4300, 39000 | measured · LSB, LEF | — | T11 | active |
| sotolon | sotolon | 62835 · 67890 · — | seasoning-like, fenugreek (caramel, herbal) | 0.91, 0.30, 2.7 | measured · CZ, LSB (LEF excluded as doubtful, § 9) | — | T11 | active, P0 pending (flour) |
| dimethylpyrazine_25 | 2,5-dimethylpyrazine | 31252 · 89762 · — | earthy, nutty (roasty) | 410, 140, 1800 | measured · LSB, LEF | — | T11 | active |
| trimethylpyrazine | 2,3,5-trimethylpyrazine | 26808 · 190131 · — | earthy (roasty) | 97, 11, 1800 | measured · LSB, LEF (160×, § 9) | — | T11 | active |
| decalactone_delta | δ-decalactone | 12810 · 87327 · — | coconut-like (fruity, buttery) | 56, 19, 170 | measured · CZ, LEF | — | T8 | active |
| dodecalactone_delta | δ-dodecalactone | 12844 · 171817 · — | peach-, coconut-like (fruity, buttery) | 53, 11, 270 | measured · CZ only | — | T8 | active |
| butanoic | butanoic acid | 264 · 30772 · C00246 | sweaty (cheesy) | 1500, 240, 4500 | measured · CZ, LSB, LEF | acid 4.8 est. | T8 | active |
| heptanone_2 | 2-heptanone | 8051 · 5672 · C08380 | fruity, soapy (fruity, cheesy) | 650, 130, 3300 | measured · LEF range only | — | T8 | active |
| nonanone_2 | 2-nonanone | 13187 · 77927 · — | fruity, musty (fruity) | 32, 5.0, 200 | measured · LEF range only | — | T8 | active |
| trimethylamine | trimethylamine | 1146 · 18139 · C00565 | ammonia-, fish-like (fishy) | 0.87, 0.29, 2.6 (free base) | measured · LSB, LEF | base 9.8 | TMAO precursor | **inactive** (TMAO-reducing bacteria) |
| acetylpyrroline_2 | 2-acetyl-1-pyrroline | 522834 · 67125 · — | popcorn-like, roasty (roasty) | 0.053, 0.011, 0.27 | measured · CZ only | — | T11 (rice initial pool) | active, P0 pending (rice) |
| acetic | acetic acid | 176 · 15366 · C00033 | vinegar-like (vinegary) | 24000, 5600, 99000 | measured · CZ 99 000 vs LSB 5 600 (18×) | acid 4.76 | engine | active |
| ethanol | ethanol | 702 · 16236 · C00469 | ethanol-like (solvent) | 310000, 100000, 990000 | measured · CZ, LEF | — | engine | active |

**Counts:** 85 compounds: **77 active** (of which 2 conc-only, 1 drill-down only with an est. threshold, 6 P0 pending, 2 engine pools), **3 inactive**, **5 dropped**.

## 4. Evidence matrix

One table per ferment type in `profiles.py`. Columns: tier · anchor (§ 1) · key sources · **calibration target** (calibrated: shape, timing, conditions, magnitude where `abs`) or **end point** (reported `abs`/`semi`). Engine pools (acetic acid, ethanol) are not counted. Rows not listed for a ferment are **drop** for it (no precursor or producer). Inactive compounds (4-ethylguaiacol, 4-ethylphenol, trimethylamine) are listed where evidence exists, so the targets are ready when an organism arrives.

### 4.1 Kombucha

Model: *S. cerevisiae* (stand-in for *Brettanomyces*/*Zygosaccharomyces*, `profiles.py` note), *A. aceti*, *G. xylinus*; sweet tea. Sources: `02:K1` (30 °C, sucrose 60 g/L, 8 g/L green + black tea, commercial SCOBY, D0–D14), `02:K2` (30 °C, Fu-brick tea 5 g/L, sucrose 100 g/L, D0–D14), `02:K3` (28 °C, black tea, sucrose 50 g/L, defined consortia, abs.), `02:K4` (28 °C, 14 d, isolates, abs.), `02:K6` (23 °C, presence). `02:K2` semi values set magnitudes only for non-polar compounds (esters, terpenes, aldehydes); its polar compounds (alcohols, acids) were badly under-recovered and count as `shape`.

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| 3-methylbutanol | calibrated | abs | `02:K1`, `K2`; `K3` | rises D0 → D7 (×2–5); a late fall is allowed (AAB). D12 at 28 °C: 700–2 000 µg/L (`K3`) → 233–6 000 µg/kg |
| 2-methylbutanol | reported | presence | `02:K6` | — |
| 2-methylpropanol | reported | abs | `02:K3` (range given jointly with 3-methylbutanol), `K2` | D12: 233–6 000 µg/kg |
| 2-phenylethanol | calibrated | shape | `02:K1`, `K2` | rises to D7, then plateau (D7–D14 within ×/÷ 1.5) |
| 3-methylbutanal, 2-methylbutanal | reported | presence | `02:K3`, `K6` (tea-derived, D0 only) | — |
| phenylacetaldehyde | reported | presence | `02:K1` (D14 only) | — |
| methionol | reported | presence | `02:K4` (heatmap) | — |
| 3-methylbutanoic acid | calibrated | shape | `02:K1` (×7), `K2` | rises D0 → D14 |
| 2-methylpropanoic acid | calibrated | shape | `02:K1`, `K2` | rises D0 → D14 |
| 2-methylbutanoic acid | reported | presence | `02:K6` | — |
| ethyl acetate | calibrated | abs | `02:K2` (×8.4, accelerating after D7); `K3`, `K4` | more than half of the D14 value formed after D7; D12–14: 17–21 000 µg/kg (spans `K3` 600–7 000 and `K4` 51.3, ×/÷ 3; § 9.2) |
| isoamyl acetate | calibrated | semi | `02:K2` | nd/low until D7, present D10–D14 |
| 2-phenylethyl acetate | calibrated | semi | `02:K1` (×9), `K2` (×14) | rises D0 → D14, ≥ ×3 |
| ethyl hexanoate | calibrated | semi | `02:K1`, `K2` | ~0 until D4, present from D7 |
| ethyl octanoate | reported | presence | `02:K6`, `K4` | — |
| ethyl decanoate | calibrated | semi | `02:K2` | rises to D7, then plateau |
| ethyl 2-methylpropanoate | reported | presence | `02:K3` (*B. bruxellensis* signature) | — |
| hexanoic, octanoic, decanoic acid | calibrated | shape | `02:K1` (`K2` erratic) | rise to D4–D9, then plateau |
| acetaldehyde, diacetyl, acetoin | reported | presence | `02:K3`, `K6` | — |
| hexanal | calibrated | shape | `02:K1` | falls: D9 < 0.3 × D0 |
| nonanal | calibrated | semi | `02:K1`, `K2` | present from D2; D14 ≤ its D2–D7 maximum |
| 1-octen-3-ol | reported | presence | `02:K3` | — |
| linalool | calibrated | abs | `02:K1`, `K2` (directions disagree); `K4` | no direction test; D14 at 28 °C: 1.4–34 µg/kg (`K4` 4.14–11.27, ×/÷ 3) |
| geraniol | calibrated | shape | `02:K1` | D14 / D0 in 0.3–1.0 (`K1` 0.67) |
| citronellol, β-damascenone | reported | presence | `02:K4`, `K6` | — |
| methyl salicylate | calibrated | semi | `02:K1`, `K2` | D4 / D0 < 0.1 |
| β-ionone | calibrated | semi | `02:K1`, `K2` | D4 / D0 < 0.2 |
| limonene | calibrated | shape | `02:K1` | D11 / D2 < 0.5 (`K1` 0.26) |
| 4-vinylguaiacol | reported† | presence | `02:K4` | tea ferulic acid not curated |
| dimethyl sulfide | reported | presence | `02:K4` (heatmap) | — |
| 4-ethylguaiacol | calibrated (**inactive**) | semi | `02:K1`, `K2` | future target: rises to D4, plateau D7–D14 |
| 4-ethylphenol | calibrated (**inactive**) | semi | `02:K2` | future target: rises to D3, plateau |

Plausible: 2-methylpropanal, methional, isobutyl acetate, ethyl butanoate, ethyl 2-methylbutanoate, 2,3-pentanedione, 2,3-butanediol, ethyl lactate (needs lactic acid), methanethiol, DMDS, DMTS. Drop: tea LOX volatiles without a tea P0 ((Z)-3-hexenal, (Z)-3-hexenol, (E)-2-nonenal, 2-pentylfuran, (Z)-4-heptenal, 1-octen-3-one, 3-octanone, 3-octanol); geranial, neral, carvone (no ingredient in a plain kombucha); glucosinolate, *Allium*, Maillard, milk, fish and rice compounds; 4-vinylphenol.

### 4.2 Vinegar

Model: *A. aceti*, *A. pasteurianus*, still surface culture, 27 °C; the base wine/cider volatiles of § 6.2 are the initial pools (D11). No absolute acetification time course was opened: every calibrated cell is a **direction** (wine → vinegar, two points) from `02:V1` (abs., submerged white wine), `02:V3` (surface flasks, 30 °C, relative area), `02:V4` (date products, normalised response). Tests run with a wine base; magnitudes are never pinned (`02:V6` units unreliable).

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| acetaldehyde | calibrated | shape | `02:V1`, `V4` | consumed: end / start < 0.5 (`V4` 0.24) |
| ethyl acetate | calibrated | shape | `02:V3` (surface) vs `V1` (submerged) | surface culture: end / start < 0.5 (`V3` 0.012) |
| acetoin | calibrated | shape | `02:V1`, `V3`, `V4`, `V10` | produced: end / start > 1.5 (`V4` 1.9); context 855 ± 150 mg/L in date vinegar (`V4`), not pinned |
| 3-methylbutanol | calibrated | shape | `02:V1`, `V3`, `V4` | end / start < 0.5 (`V3` 0.07, `V4` 0.30) |
| 2-methylbutanol | calibrated | shape | `02:V1`, `V2`, `V3` | end / start < 0.5 (`V3` 0.06) |
| 2-methylpropanol | calibrated | shape | `02:V1`, `V3`, `V4` | end / start < 0.5 (`V3` 0.09, `V4` 0.11) |
| 2-phenylethanol | calibrated | shape | `02:V1`, `V3`, `V4` | end / start 0.8–2.0 |
| 3-methylbutanoic acid | calibrated | shape | `02:V4`; high OAV `V8` | rises: end / start > 1.5 (`V4` 2.1) |
| 2-methylpropanoic acid | calibrated | shape | `02:V4` | rises: end / start > 1.5 (`V4` 3.2) |
| isoamyl acetate, isobutyl acetate | calibrated | shape | `02:V3`, `V4` | fall: end / start < 0.7 |
| ethyl hexanoate, ethyl octanoate, ethyl decanoate, ethyl 2-methylpropanoate | calibrated | shape | `02:V3`, `V4` | fall: end / start < 0.5 |
| linalool, β-damascenone | calibrated† | shape | `02:V3` | fall; base P0 not curated → test deferred |
| diacetyl | reported | presence | `02:V3`, `V6`; key odorant `V7`–`V9` (aged Sherry) | — |
| 2,3-butanediol | reported (conc-only) | presence | `02:V1`, `V3`, `V4` | — |
| ethyl lactate | reported | presence | `02:V1` vs `V3` (directions disagree) | — |
| 3-methylbutanal, 2-methylbutanal, 2-methylpropanal, methional | reported | presence | `02:V4`, `V6`, `V9`, `V13` | — |
| 2-methylbutanoic acid | reported | presence | `02:V13` | — |
| 2-phenylethyl acetate, ethyl butanoate, ethyl 2-methylbutanoate | reported | presence | `02:V3`, `V4`, `V6`, `V8` | — |
| hexanoic, octanoic, decanoic acid | reported | presence | `02:V4` ↑ vs `V3` ↓ | — |
| hexanal, nonanal, 1-octen-3-one, citronellol | reported† | presence | `02:V3`–`V6` | fruit-base P0 not curated |
| 4-vinylguaiacol | reported† | presence | `02:V14` (abs.) | fruit HCA not curated |
| 4-ethylguaiacol, 4-ethylphenol | reported (**inactive**) | presence | `02:V6`, `V9` | wine *Brettanomyces* / wood |

Plausible: 2,3-pentanedione, phenylacetaldehyde, methionol. Drop: sotolon (forms over months–years of wood ageing, outside an acetification), other Maillard, glucosinolate, sulfur, milk, fish and rice compounds; fruit LOX volatiles without a base P0.

### 4.3 Sourdough (dough before baking)

Model: *L. sanfranciscensis* + *S. cerevisiae*, levain at 26 °C (plans: levain → bulk → proof). Flour is the main aroma source (D12). Directions from `02:S1` (wheat) and `02:S2` (rye), both SIDA but abstract only; end points from `02:S3` (wheat, **15 °C, 5 d**, *S. cerevisiae* × *L. brevis* or *L. plantarum*; µg/kg as printed, calibration not described). Tests at `02:S3` conditions use those organisms (`L. brevis`, `L. plantarum` exist in the model).

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| 3-methylbutanal | calibrated | shape | `02:S1`, `S2`; OAV > 100 (rye sourdough) | rises flour → sourdough (end > start) |
| 2-methylbutanal | calibrated† | shape | `02:S2` | falls; flour P0 not curated → test deferred |
| 3-methylbutanol | calibrated | abs | `02:S2` ↑; `02:S3` | rises; at 15 °C, 120 h: 274–38 500 µg/kg (`S3` 823–12 838, ×/÷ 3) |
| diacetyl | calibrated | shape | `02:S2`; OAV > 100 | rises flour → sourdough |
| hexanal | calibrated | abs | `02:S1` ↓; `02:S3` | falls from the flour P0; at 15 °C, 120 h: 33–1 100 µg/kg (`S3` 100–372, ×/÷ 3) |
| (E)-2-nonenal | calibrated | shape | `02:S1` | falls (end < start) |
| methional | reported | abs (lower bound) | `02:S2` OAV > 100 in rye flour and sourdough | end ≥ 10 µg/kg (29 / 3; § 6.2) |
| 2-methylbutanol | reported | abs | `02:S3` | 15 °C, 120 h: 42–6 100 µg/kg |
| 2-methylpropanol | reported | abs | `02:S3`, `S4` | 56–10 700 µg/kg |
| 2-phenylethanol | reported | abs (upper bound only, § 9.2) | `02:S3` | ≤ 209 000 µg/kg |
| ethyl acetate | reported | abs | `02:S3`, `S4`, `S6`; ↑ with time `S9` | 450–171 000 µg/kg |
| isoamyl acetate / ethyl butanoate / ethyl decanoate | reported | abs | `02:S3` (nd–6.73 / nd–6.93 / nd–3.73) | ≤ 20 / ≤ 21 / ≤ 11 µg/kg |
| ethyl hexanoate / ethyl octanoate | reported | abs | `02:S3` (4.17–604 / 0.68–60.7) | 1.4–1 800 / 0.23–182 µg/kg |
| ethyl 2-methylbutanoate / ethyl 2-methylpropanoate | reported | abs | `02:S3` (nd–0.61 / nd–1.73) | ≤ 1.8 / ≤ 5.2 µg/kg |
| methionol; 2-methylpropanoic, 2-methylbutanoic acid; 2-phenylethyl acetate, isobutyl acetate; ethyl lactate; acetaldehyde | reported | presence | `02:S5` | — |
| 3-methylbutanoic acid | reported | presence | `02:S2` (OAV > 100), `S7` (acid stress) | — |
| hexanoic, octanoic acid; acetoin | reported | presence | `02:S4` (area), `S5` | — |
| nonanal, 2-pentylfuran, 1-octen-3-ol, 3-octanol, limonene, 2-heptanone, butanoic acid | reported† | presence | `02:S5` | flour P0 not curated |
| 1-octen-3-one, sotolon | reported† | presence | `02:S1`, `S2` (high FD / odour activity in flour) | flour P0 not curated |

Plausible: 2-methylpropanal, phenylacetaldehyde, decanoic acid, 2,3-pentanedione, 2,3-butanediol, (Z)-3-hexenal, (Z)-3-hexenol, (Z)-4-heptenal, 3-octanone, 4-vinylguaiacol (flour ferulic acid curated; *L. plantarum*/Pof⁺ yeast), 4-vinylphenol†. Drop: glucosinolate, *Allium*, sulfur, tea terpenes, Maillard/furanones/pyrazines (formed on baking), lactones, 2-nonanone, trimethylamine, 2-acetyl-1-pyrroline, 4-ethylphenols.

### 4.4 Koji

Model: *A. oryzae* on steamed rice, 30 °C, 72 h. Time courses are relative and on **bran** (`02:J1`, 30 °C, 70 % RH, 48 h); rice end points from `02:J2` (30 °C, 48 h, sealed dishes, "ppm" with no stated basis → presence). All koji cells are exploratory (type is exploratory). The model's *A. oryzae* respires only (no ethanol), unlike `02:J2`'s sealed dishes.

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| 1-octen-3-ol | calibrated | shape | `02:J1` (bran); `J3` (rice koji, *ppoC*-dependent) | monotone rise to 48 h |
| 3-octanone, 3-octanol | calibrated | shape | `02:J1` | monotone rise to 48 h |
| 2-heptanone, 2-nonanone | calibrated | shape | `02:J1`; `J2` (2-heptanone ×1.8) | monotone rise to 48 h |
| ethyl acetate, isoamyl acetate | calibrated | shape | `02:J1` | transient: maximum between 12 and 40 h, lower at 48 h |
| hexanal | calibrated | shape | `02:J1`, `J4` (bran, bread: falls); `J2` (rice ~flat) | rice: end / start ≤ 2 (`J2` 1.0–2.1) |
| 3-methylbutanol, 2-methylpropanol, 2-methylbutanol | reported | presence | `02:J2`, `J4` | — |
| 3-methylbutanal, 2-methylbutanal, 2-methylpropanal, phenylacetaldehyde, methional | reported | presence | `02:J2` (×10²–10³ over raw rice) | — |
| 3-methylbutanoic, 2-methylpropanoic, 2-methylbutanoic acid | reported | presence | `02:J1`, `J2` | — |
| ethyl 2-methylpropanoate, ethyl 2-methylbutanoate, ethyl hexanoate, ethyl octanoate | reported | presence | `02:J2` | — |
| acetaldehyde, diacetyl, acetoin, 2,3-pentanedione, 2,3-butanediol | reported | presence | `02:J1`, `J2`, `J4` | — |
| nonanal, 2-pentylfuran | reported | presence | `02:J1`, `J2` | — |
| 4-vinylguaiacol | reported† | presence | `02:J1`, `J2` | rice HCA not curated |
| 4-ethylguaiacol | reported (**inactive**) | presence | `02:J1` (high moisture) | — |

Plausible: 1-octen-3-one, 2-phenylethanol (nd with *A. oryzae* on rice), methionol, ethyl decanoate, isobutyl acetate, ethyl butanoate, 2-phenylethyl acetate, hexanoic/octanoic/decanoic acid, (E)-2-nonenal, (Z)-3-hexenal, (Z)-3-hexenol, (Z)-4-heptenal, 2-acetyl-1-pyrroline†. Drop: glucosinolates (rapeseed substrates only), sulfur, terpenoids, Maillard/furanones/pyrazines, lactones, butanoic acid, trimethylamine.

### 4.5 Lacto-ferment (sauerkraut, kimchi, cucumber, radish)

Model: *Leuc. mesenteroides* + *L. plantarum*, 20 °C, 2 % salt; the vegetable sets the precursors (§ 6). One type, so the tier is the best across vegetables, but **each target names its vegetable and conditions**. Sources: sauerkraut `03:S1` (abs., brine, standard additions; 18 °C, 2 % NaCl, *Leuc. mesenteroides* starters, 9 months), `03:S2`, `S8`, `S9` (presence/area); kimchi `03:S10` (napa cabbage brined 20 h at 8 °C to 2.5 % salt, then **cabbage alone at 15 °C for 15 d**, spontaneous LAB, SAFE, semi ±×2–3; t0 = after salting), `03:S11` (full kimchi, GC-O, abs.); cucumber `03:S13` (2 % NaCl + 53 mM acetic acid, *L. plantarum* MOP-3 at 10⁶/mL, sugars gone by d13, d0–d21, T not stated; 7 compounds with 3-level standards).

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| 3-butenyl ITC | calibrated (kimchi) | semi | `03:S10` Tables 1–3; kraut presence `03:S8` | kimchi, 15 °C: rises from t0 (212) to a peak at d7 (window d5–d9; 553), then d15 / peak < 0.5 (0.27) |
| dimethyl disulfide | calibrated (kimchi); reported (kraut) | semi; abs | `03:S10`; `03:S1` Table 5 | kimchi: d3 / d0 < 0.1 (0.033), then d15 / d3 > 1.5 (4.7). Kraut, 18 °C, 9 months: 10–234 µg/kg (30.3–77.9, ×/÷ 3) |
| dimethyl trisulfide | calibrated (kimchi); reported (kraut) | semi; abs | `03:S10` (FD 5 after salting), `03:S11`; `03:S1` (kraut sulfur flavour ∝ DMTS) | kimchi: d3 / d0 < 0.05 (0.010), d5–d15 within ×/÷ 2. Kraut, 9 months: 7–92 µg/kg (21.7–30.6, ×/÷ 3) |
| ethyl butanoate | calibrated (kimchi) | semi | `03:S10` | ~0 at d0–d3; peak at d7 (d5–d9); d15 / peak < 0.4 (0.14) |
| ethyl 2-methylbutanoate | calibrated (kimchi) | semi | `03:S10` | peak at d9 (d7–d15); d15 / peak < 0.5 (0.23) |
| hexanal | calibrated (kimchi, cucumber) | semi; abs | `03:S10`; `03:S13` Table 2 | kimchi: d3–d15 within ×/÷ 3 of t0 (LOX inactivated by salting). Cucumber d21: 4–114 µg/kg (cucumber 12, brine 38, ×/÷ 3) |
| (Z)-3-hexenal | calibrated (kimchi) | semi | `03:S10` | none formed after salting: stays ≤ its t0 value |
| (Z)-3-hexenol | calibrated (kimchi) | semi | `03:S10` | transient: peak at d5 (d3–d7) ≥ 3 × t0; d15 / peak < 0.4 (0.16) |
| methional | calibrated (kimchi) | semi | `03:S10`; `03:S11` | rises d0 → d15 by ≥ ×2 (×5) |
| phenylacetaldehyde | calibrated (kimchi) | semi | `03:S10`; `03:S11` | flat: every day within ×/÷ 2 of t0 |
| (E)-2-nonenal | calibrated (cucumber) | shape | `03:S13` Fig. 4 | d5 / d0 < 0.01 (not detected after d5); fresh-cucumber P0 est. 5 (1–25) µg/kg, enough for a shape test |
| linalool | calibrated† (cucumber) | abs | `03:S13` Table 2, Fig. 4 | rises d3 → d10, then stable; d21: 15–240 µg/kg (cucumber 44, brine 81, ×/÷ 3). Needs a cucumber bound-linalool pool (not curated) → test deferred |
| allyl isothiocyanate | reported (kraut) | abs | `03:S1` Table 5; `03:S3` (abs.: up to 9 800 µg/kg FW with *L. sakei*) | kraut, 18 °C, 9 months: 18–256 µg/kg brine (54.6–85.2, ×/÷ 3) |
| allyl cyanide | reported (conc-only) | presence | `03:S4`, `S7` (abs.) | — |
| methanethiol, dimethyl sulfide | reported (kraut) | presence | `03:S2`, `S9` | — |
| acetaldehyde, ethyl acetate, ethyl lactate | reported (kraut) | presence | `03:S2`, `S8`, `S9` | — |
| ethyl acetate (cucumber) | reported | abs, confounded | `03:S13` (43 → 345–365) | not a test (§ 9.2) |
| diacetyl | reported (kimchi) | presence | `03:S10` (FD 1 after salting), `03:S11` | — |
| acetoin, 2,3-butanediol | reported (kimchi) | semi (t0 values) | `03:S10` (74.1, 3.7 after salting) | initial pools (§ 6.2), not end points |
| 3-methylbutanol, 2-methylbutanol, nonanal, geraniol | reported (cucumber) | presence | `03:S13` Table 1 (area) | — |

Plausible: 2,3-pentanedione; carvone† (caraway, dill), geranial†, neral† (ginger, lemongrass), 4-vinylguaiacol† (*L. plantarum* decarboxylases in kimchi isolates, `05:Rosimin15`; vegetable HCA not curated); AITC and allyl cyanide in kimchi† (mustard greens or radish: no sinigrin P0 for napa cabbage). Drop: 4-methylthio-3-butenyl ITC (radish character compound, dropped compound; its yellowing loss path is `03:S12`), allyl methyl disulfide and diallyl disulfide (calibrated and reported in kimchi, `03:S10`, `03:S11`, but dropped compounds), S-methyl thioacetate (reported, dropped), zingiberene; yeast-only compounds (no yeast in the type), MCFA, mould C8, tea terpenes, Maillard, milk, fish and rice compounds.

### 4.6 Kefir

Model: *Lc. lactis*, *L. kefiranofaciens*, *L. kefiri*, *K. marxianus*; milk, 22 °C, 48 h. The sources' main producers include *S. cerevisiae*, *Leuconostoc*, *Acetobacter* and *Lb. bulgaricus*, none in the kefir profile: *K. marxianus* carries the yeast templates (multipliers in § 5). Sources: `03:S19` (abs., storage at 4 °C, 0–21 d), `03:S20`, `S18`, `S26` (abs. end points), `03:S21` (25 °C, three grains, 0/8/24 h, relative abundance: direction only), `03:S23` (UHT whole milk + 3 % grains, room temperature, 0/24/48 h, semi ±×3), `03:S22` (sensomics key odorants, abs.).

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| acetaldehyde | calibrated | abs | `03:S19`, `S20`, `S18`, `S26` | end of fermentation (24–48 h): 1 270–71 000 µg/kg (3 800–23 600, ×/÷ 3); optional 4 °C storage: no fall > 2× over 21 d (`S19`: doubled) |
| diacetyl | calibrated | shape | `03:S21` ↑; `S18` max 1 870; `S19` nd; `S22` key odorant | rises from 0 h; at 24 h ≤ 5 600 µg/kg (upper bound only, § 9.2) |
| 2,3-pentanedione | calibrated | shape | `03:S21` | rises from 0 h |
| acetoin | calibrated | abs | `03:S19`; `S22` key; `S25` | end of fermentation: 8 300–75 000 µg/kg (25 000, ×/÷ 3); optional 4 °C storage: d21 / d0 in 0.4–1.0 (`S19` 0.64) |
| ethyl acetate, ethyl butanoate, ethyl hexanoate, isoamyl acetate | calibrated | shape | `03:S21`; `S18` | rise after 0 h |
| ethyl octanoate | calibrated | semi | `03:S23` | 0 → peak at 24 h (930) → lower at 48 h: 48 h / 24 h < 0.6 (0.26) |
| ethyl decanoate | calibrated | semi | `03:S23` | ~0 at 24 h, present at 48 h (290) |
| hexanoic acid | calibrated | semi | `03:S23`; `S21` ↑ | monotone rise, nd → 2 530 µg/kg at 48 h |
| octanoic acid / decanoic acid | calibrated | semi | `03:S23` | monotone rise over 48 h: ×2.2 (2 550 → 5 690) / ×4 (2 830 → 11 470) |
| 2-nonanone | calibrated | semi | `03:S23` (UHT milk) | falls: 24 h < 0.5 × 0 h (2 200 → 430) |
| δ-decalactone | calibrated | semi | `03:S23` | monotone rise ×6.4 over 48 h (240 → 1 540) |
| δ-dodecalactone | calibrated | semi | `03:S23` | ~flat to 24 h (740 → 750), ×1.9 by 48 h |
| 2-phenylethanol | calibrated | semi | `03:S23`; `S21` | nd → 300 (24 h) → 1 700 (48 h): rise, faster in the second day |
| 3-methylbutanol, 2-methylbutanol, 2-methylpropanol, 3-methylbutanal, 2-methylbutanal | calibrated | shape | `03:S21` | rise after 0 h |
| hexanal | reported | abs (milk baseline) | `03:S34`; did not rise (`03:S21`); key odorant (`03:S22`) | 48 h within ×/÷ 3 of the milk value (51.3 µg/kg pasteurised) |
| butanoic acid | reported | presence | `03:S22` (key odorant) | milk P0 from `03:S34` |
| 2-heptanone | reported | presence | `03:S23` vs `S21`, `S34` (§ 9.2) | — |
| 2,3-butanediol | reported (conc-only) | presence | `03:S21` | — |
| nonanal | reported | presence | `03:S21` | — |

Plausible: dimethyl sulfide, methional, methionol, 2-methylpropanal, phenylacetaldehyde, isobutyl acetate, 2-phenylethyl acetate, ethyl 2-methylbutanoate, ethyl 2-methylpropanoate, ethyl lactate, the three fusel acids. Drop: limonene (rises in `03:S23`, but no mechanism: origin unexplained), mould C8, glucosinolate, sulfur-vegetable, tea, Maillard, fish and rice compounds.

### 4.7 Cheese (curd and acidification stage)

Model: *Lc. lactis*, milk, 30 °C, 24 h, **per kg of milk**. No fresh-cheese time course exists. The C4 chain is calibrated on a milk culture (`03:S30`: 10 % reconstituted skim milk, 30 °C, *Lc. lactis* biovar *diacetylactis* MR3, an **ALDC⁻ mutant: upper bound** for diacetyl and α-acetolactate). Gouda at week 0 (`03:S32`, SIDA, µg/kg **dry matter** after pressing and 28 h brining) cannot be compared with a per-kg-milk model: it is presence evidence only. Milk baselines (`03:S34`, external standard) give the reported end points: the curd stage should not move them much.

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| diacetyl | calibrated | shape (fig.) | `03:S30` Fig. 1; `03:S27`, `S28` (abs.) | citrate-positive culture, 30 °C: α-acetolactate (internal state) peaks at 4–8 h, at citrate exhaustion; diacetyl > 0 and still rising at 24 h; at 24 h ≤ 41 000 µg/kg (≈ 13 800 ×3, upper bound) |
| acetoin | calibrated | shape (fig.) | `03:S30`; `03:S28` | rises through 24 h; acetoin / diacetyl at 24 h > 3 (`S30` ≈ 16); at 24 h ≤ 690 000 µg/kg (≈ 229 000 ×3) |
| acetaldehyde | reported | presence | `03:S27` (abs.) | — |
| butanoic, octanoic, decanoic acid | reported | abs (milk baseline) | `03:S34` Table 2; Gouda `03:S32` (presence) | 24 h within ×/÷ 3 of the milk value (pasteurised: 1 094 / 1 037 / 380 µg/kg) |
| δ-decalactone, δ-dodecalactone | reported | abs (milk baseline) | `03:S34`; `03:S32` ("already quite high in the unripened cheese") | 24 h within ×/÷ 3 of 138 / 844 µg/kg (pasteurised) |
| hexanal | reported | abs (milk baseline) | `03:S34` | 24 h within ×/÷ 3 of 51.3 µg/kg |
| hexanoic acid; ethyl butanoate, ethyl hexanoate; 3-methylbutanal; 3-methylbutanol, 2-phenylethanol; 3-methylbutanoic, 2-methylbutanoic, 2-methylpropanoic acid | reported | presence | `03:S32` (Gouda key odorants, DM) | — |

Plausible: 2,3-butanediol, 2,3-pentanedione, dimethyl sulfide, 2-heptanone and 2-nonanone (UHT milk only, `03:S34`). Drop: yeast-only compounds, vegetable, tea, mould, Maillard, fish and rice compounds; ripening compounds are out of scope (spec non-goals).

### 4.8 Miso (exploratory type)

Model: *T. halophilus* + *Z. rouxii*, koji enzymes (the mould does not grow in the mash), 25 °C, 11 % salt, 180 d. Sources: `04:M9` (**abs.**, solvent extraction 90–94 % recovery; rice miso, base case 30 °C, 12 % NaCl, 50 % moisture, koji ratio 10, *Z. rouxii* S96 at 10⁶/g, no LAB, 0–75 d; dose, salt, temperature and koji-ratio series; yeast-stopped storage table), `04:M1` (barley miso, GC-FID; HEMF/HMMF on the HDMF calibration line; 30 °C after a 2-week pre-age; 4-week temperature series), `04:M2` (Sendai rice miso, 13 % NaCl, 0–120 d, porous polymer: **app.**, T not stated), `04:M8` (red rice miso, 25 vs 30 °C, 180 d, app.), `04:M10` (contest misos, app.), `04:M3` (barley miso, 28 °C, 20–365 d, area), `04:M5`, `M6` (AEDA, abs.). App. values are lower bounds: a magnitude test from them is "≥ value / 3" only.

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| HEMF | calibrated | abs | `04:M9` Figs 1–4, Table 3; `04:M1`; `M2`, `M8`, `M10` (app.) | base case: rises from 0, peak at 45 d (window 30–60 d) of 5 700–51 000 µg/kg (17 000 ×/÷ 3), 75 d / peak in 0.5–1.0 (0.76). No yeast: < 1 % of the base-case peak throughout. 35 °C: peak ≤ 30 d and 75 d / peak < 0.4. 25 °C: still rising at 75 d (later peak, as in `M8`). Yeast stopped: 60 d / 20 d = 0.15–0.45 at 30 °C (0.29) and 0.55–0.95 at 20 °C (0.73) |
| furaneol (HDMF) | calibrated (barley); reported (rice, trace) | abs | `04:M1` Table 3, Fig. 4; `04:M2` | barley miso, 4 weeks: increases with T (15 < 20 < 30 < 37 °C; 410 / 610 / 1 470 / 5 780); at 30 °C 490–4 400 µg/kg (1 470 ×/÷ 3) |
| norfuraneol | calibrated (barley) | abs (fig.) | `04:M1` Fig. 4 | barley miso, 30 °C, after pre-aging: falls to 0.1–0.35 × its end-of-mashing value by d8 |
| maltol | calibrated | shape (app.) | `04:M2` Table 2; barley P0 `04:M1` | falls from d0: 120 d / 0 d < 0.3 (0.17) |
| 3-methylbutanol | calibrated | shape (app.) | `04:M2` Table 3, `04:M8` Fig. 1; barley `04:M1` (abs., mean 27 000) | peak at 60–90 d, then −20–60 % by 120–180 d; 25 °C peak ≥ 30 °C peak (`M8`); peak ≥ 5 700 µg/kg (`M8` 17 000 app. ÷ 3) |
| 2-methylbutanol, 2-methylpropanol | calibrated | shape (app.) | `04:M2` Table 3 | rise to 90 d, lower at 120 d |
| 2-phenylethanol | calibrated | shape (app.) | `04:M2`, `04:M8` Fig. 1 | peak at 60–90 d; 180 d / peak 0.25–0.6 (`M8` 0.35–0.45) |
| methionol | calibrated | shape (app.) | `04:M2`, `04:M8` Fig. 2 | peak at 60–120 d; 180 d / peak 0.4–0.9 |
| 2-phenylethyl acetate | calibrated | shape (app.) | `04:M2` | ~0 at 0–30 d; present from 60 d, rising to 120 d |
| 3-methylbutanal, 2-methylbutanal, 2-methylpropanal, phenylacetaldehyde, ethyl 2-methylpropanoate, ethyl 2-methylbutanoate, ethyl acetate, isoamyl acetate, acetaldehyde, hexanal, 1-octen-3-ol | calibrated | shape (area) | `04:M3` Table 1 | barley miso, 28 °C: value at 365 d > value at 90 d (`M3` ×2–100). 1-octen-3-ol has no non-growth source in the model (the mould does not grow in the mash): this target is expected to fail until one is added (§ 11) |
| 3-methylbutanoic acid | reported | abs | `04:M1` (barley, mean 5 900, nd–18 000) | mature barley miso: 2 000–18 000 µg/kg |
| acetoin | reported | abs | `04:M1` (mean 1 900, nd–5 400) | 630–5 700 µg/kg |
| 2,3-butanediol | reported (conc-only) | abs | `04:M1` (meso 159 000 + (R,R)/(S,S) 85 000) | 81 000–730 000 µg/kg total |
| ethyl lactate | reported | abs | `04:M1` (mean 3 900, nd–49 000) | 1 300–11 700 µg/kg |
| methional, 1-octen-3-one | reported | presence | `04:M5` (AEDA) | — |
| dimethyl trisulfide | reported | presence | `04:M6` (cooked soy miso) | — |
| ethyl hexanoate, ethyl octanoate, ethyl decanoate | reported | presence | `04:M3` (area) | — |
| hexanoic acid | reported | semi (app.) | `04:M10` (16–150) | ≥ 5 µg/kg |
| 2,5-dimethylpyrazine, 2,3,5-trimethylpyrazine | reported (barley and soybean miso) | semi (app.) | `04:M10` (14–22) | barley/soybean recipes: ≥ 5 µg/kg; rice: ~0 |
| 4-vinylguaiacol | reported† | semi (app.) | `04:M10` (58–902) | soy HCA not curated |
| 4-ethylguaiacol, 4-ethylphenol | reported (**inactive**, barley and soybean miso); drop (rice miso with *Z. rouxii* only: nd 0–120 d, `04:M2`) | semi (app.) | `04:M10` | — |

Plausible: 2-methylbutanoic and 2-methylpropanoic acid; isobutyl acetate, ethyl butanoate; octanoic, decanoic acid; diacetyl, 2,3-pentanedione; (Z)-3-hexenal, (E)-2-nonenal, nonanal, 2-pentylfuran, (Z)-4-heptenal (soy LOX); 3-octanone, 3-octanol (*A. oryzae*); methanethiol, dimethyl sulfide, dimethyl disulfide; 4-vinylphenol†; sotolon†; 2-acetyl-1-pyrroline† (rice koji). Drop: glucosinolate, *Allium*, tea/spice terpenoids, milk lactones and methyl ketones, trimethylamine.

### 4.9 Garum (fish sauce; exploratory type)

Model: *T. halophilus*; fish enzymes; koji enzymes in koji garum; default 30 °C (traditional garum 18–25 °C, months; hot koji garum ~60 °C, weeks). No absolute aroma time course exists. Sources: `04:G1` (*colatura di alici*, anchovies dry-salted, 18–25 °C, 12/24/48 months; IS-equivalent, semi), `04:G2` (3 → 7 months: natural, 30 % salt, ~20 °C outdoor; koji, ~25 °C; heat-held 35 °C; IS-relative, presence and direction), `04:G3`–`G9` (abs.). Tests use the traditional recipe (fish + salt, no koji) at 22 °C unless a koji process is named.

| compound | tier | anchor | sources | calibration target / end point |
|---|---|---|---|---|
| 3-methylbutanoic acid | calibrated | semi | `04:G1` Tables 4–5; `04:G2` | rises 12 → 48 months by ≥ ×5 (×22) |
| 2-methylpropanoic acid | calibrated | semi | `04:G1` | rises 12 → 48 months by ≥ ×3 (×15) |
| butanoic acid | calibrated | semi | `04:G1` | 48 / 12 months in 1.0–2.5 (1.4) |
| hexanoic / octanoic / decanoic acid | calibrated | semi | `04:G1` | rises 24 → 48 months (×3.2) / flat within ×/÷ 1.5 / 48 / 12 months in 0.5–1.1 (0.79) |
| ethyl octanoate | calibrated | semi | `04:G1` | slight rise 12 → 48 months (×1.5; end / start 1.0–3) |
| phenylacetaldehyde | calibrated | semi | `04:G1`; `04:G2` (natural ×15 from 3 to 7 months) | rise, then fall: maximum before 24 months; 48 months < 0.2 × maximum (nd) |
| 2-phenylethanol | calibrated | semi | `04:G1` | rises 12 → 48 months by ≥ ×3 (×6.7) |
| nonanal | calibrated | semi | `04:G2` (natural 18 → 477), `04:G1` (1 022 → 57) | rises 3 → 7 months, then 48 / 12 months < 0.2 |
| 3-methylbutanal | calibrated | shape | `04:G2` (rises in every process), `04:G5` (budu, 60 d, abs.), `04:G3` | rises over the first 7 months |
| 2-methylbutanal | calibrated | shape | `04:G2` (natural 25 → 159), `04:G5` | natural recipe: rises 3 → 7 months |
| hexanal | calibrated | shape | `04:G2` (natural 279 → 22, koji 202 → 78) | falls 3 → 7 months |
| 2-pentylfuran, 1-octen-3-ol | calibrated | shape | `04:G2` (natural 0 → 424, 0 → 357) | rise 3 → 7 months |
| dimethyl trisulfide | reported | semi | `04:G1` (commercial 23–27; nd at 12–48 months in the sampled producer); `04:G4` (key: fishy, faecal) | non-negative only (the time-course producer had none) |
| 2-methylpropanal | reported | presence | `04:G3`, `G4` (distinctive odorant), `G8` | — |
| methional | reported | presence | `04:G6` (highest OAV in Yu-lu), `04:G2` (koji processes only) | — |
| dimethyl disulfide, dimethyl sulfide | reported | presence | `04:G3`; `04:G2` (heat + enzyme only) | — |
| ethyl acetate, ethyl decanoate | reported | presence | `04:G2` | — |
| 3-methylbutanol | reported | presence | `04:G9` (*Aspergillus* fish sauce marker) | — |
| diacetyl | reported | presence | `04:G8` (koji "fish miso") | — |
| HEMF | reported (with *Z. rouxii* added) | presence | `04:G7` (salmon sauce + barley koji; only when *Z. rouxii* was inoculated) | — |
| trimethylamine | reported (**inactive**) | presence | `04:G2` (0 at 3 months → present at 7; lower when heat-held) | — |
| 4-ethylphenol (producer unknown), 4-ethylguaiacol (*C. versatilis*) | reported (**inactive**) | presence | `04:G2`; `04:G7` | — |

Plausible: 2-methylbutanoic acid (co-elutes with 3-methylbutanoic in `04:G1`); 2-methylbutanol, 2-methylpropanol, methionol; ethyl 2-methylpropanoate, ethyl 2-methylbutanoate; methanethiol; 2,5-dimethylpyrazine, 2,3,5-trimethylpyrazine; (Z)-4-heptenal, (E)-2-nonenal (fish n-3/n-6 lipids); acetaldehyde, acetoin; furaneol, maltol (koji garum). Drop: glucosinolate, *Allium*, tea-terpene and milk-lactone groups; 2-acetyl-1-pyrroline.

### 4.10 Counts per ferment (cells; engine pools excluded; inactive cells counted separately)

| ferment | calibrated | reported | plausible | inactive | † cells, any tier (compute ~0) |
|---|---|---|---|---|---|
| kombucha | 19 | 17 | 11 | 2 | 1 |
| vinegar | 17 | 19 | 3 | 2 | 7 |
| sourdough | 6 | 32 | 11 | 0 | 11 |
| koji | 8 | 23 | 15 | 1 | 2 |
| lacto-ferment | 12 | 14 | 5 | 0 | 5 |
| kefir | 22 | 5 | 13 | 0 | 0 |
| cheese | 2 | 16 | 5 | 0 | 0 |
| miso | 21 | 14 | 21 | 2 | 4 |
| garum | 15 | 10 | 15 | 3 | 0 |
| **total** | **122** | **150** | **99** | **10** | |

Of the 122 calibrated cells, 11 carry an absolute magnitude window (kombucha 3, sourdough 2, lacto-ferment 2 of which 1 deferred, kefir 2, miso 2) and 4 an upper or lower bound only (kefir diacetyl, cheese diacetyl and acetoin, miso 3-methylbutanol); the rest pin shape and timing only.

## 5. Template parameters

**Units and conventions.** b_ij in mg compound per g substrate fermented by organism j, in the engine's hexose-equivalent flux v_j (so dC [µg/kg/h] = 1000·b·v). a_ij in mg per g biomass made. A microbial conversion c_ij is given as **k_max** (1/d) = the pseudo-first-order rate when organism j sits at its carrying capacity; c_ij = k_max / x_max_j. r_i and k⁰_i in 1/d at the stated temperature, with Q10 (default (2, 1.5, 3), est., where none is given). "lin" marks linear-scale priors; others are log scale. Calibration pass 3 (§ 7) may move a median inside its stated range, never outside it.

### 5.1 T1 Ehrlich / fusel (b-term; methionine route as precursor)

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| b(3-methylbutanol + 2-methylbutanol), yeast | 0.55, 0.30, 1.0 | mg/g | b_ij | `05:Godillot23` Table 2: 84.6–144.1 mg/L at 200 g/L sugar = 0.42–0.72 (derived); widened ×/÷ 1.4 for strain and medium (est.) |
| 2-methylbutanol share of that sum | 0.20, 0.10, 0.35 lin | — | split of b | derived: 0.13 in sourdough (`02:S3`: 126–2 028 vs 823–12 838 µg/kg), 0.30 in rice miso (`04:M2`: 2 090 vs 4 760 at 120 d) |
| b(2-methylpropanol), yeast | 0.28, 0.18, 0.40 | mg/g | b_ij | `05:Godillot23` 35.4–79.9 mg/L ÷ 200 (derived) |
| Q10 of b(2-methylpropanol) | 2.3, 1.5, 3.0 | — | b(T) | derived: 35.4 (18 °C) → 79.9 (28 °C) (`05:Godillot23`); range est. |
| Q10 of b(methylbutanols) | 1.0, 0.8, 1.3 | — | b(T) | derived: 106 / 118 / 114 mg/L at 18 / 23 / 28 °C (`05:Godillot23`); range est. |
| non-*Saccharomyces* multiplier (*Z. rouxii*, *K. humilis*, *K. marxianus*) | 1.0, 0.3, 3.0 | × | b_ij | est.: no yields for these species (`05:E8`); `02:K4` shows ×3–6 between kombucha yeasts |
| b(2-phenylethanol), yeast | 0.20, 0.05, 0.80 | mg/g | b_ij | derived: 2-phenylethanol/ethanol = 3.3×10⁻⁴ (kefir, `03:S23` semi) and 7×10⁻⁴ (rice miso, `04:M2` / `04:M10`, app.) × 0.47 g ethanol/g sugar = 0.16–0.33; ×/÷ 4 for semi/app. (D2) |
| *K. marxianus* multiplier on b(2-phenylethanol) | 0.4, 0.3, 0.5 lin | × | b_ij | `05:Zhang22` Table 1 (cider, semi): ×0.3–0.5 vs *S. cerevisiae* |
| LAB b(3-methylbutanol) | 0.01, 0.002, 0.05 | mg/g | b_ij | derived: *F. sanfranciscensis* alone 0.84 vs *S. cerevisiae* 35.3 (area) in the same dough (`02:S4`) ≈ 2 % of the yeast yield; LAB b(2-methylpropanol) = 0 (nd, `02:S4`) |
| fusel-acid share of Ehrlich flux (fermentative yeast) | 0.10, 0.03, 0.30 | mol/mol | b split → 3-methylbutanoic, 2-methylbutanoic, 2-methylpropanoic acid | `05:Hazelwood08`: phenylalanine → ~90 % 2-phenylethanol, < 10 % phenylacetate; range est. (respiratory regimes shift to acids, no number) |
| fusel-aldehyde share of Ehrlich flux, yeast | 0.01, 0.001, 0.05 | mol/mol | b_ij | est.: transient intermediates (`05:Hazelwood08`), no yield opened |
| aldehyde → alcohol reduction, yeast and LAB | k_max 2, 0.5, 10 | 1/d | c_ij | est. |
| methionine share of free amino acids | 0.02, 0.01, 0.04 | g/g | P (methionol, methional, methanethiol) | est.: methionine is a minor protein amino acid (no composition in the files) |
| Leu / Ile / Val / Phe shares of free amino acids | 0.08 (0.04–0.12) / 0.04 (0.02–0.07) / 0.05 (0.03–0.08) / 0.04 (0.02–0.07) | g/g | P (Strecker and mould routes, T11) | est.: typical food-protein composition, not in the files |
| aminotransferase route of non-yeast organisms (*A. oryzae*, LAB, *T. halophilus*): free Leu/Ile/Val/Phe/Met → aldehyde, then the alcohol/acid splits above | k_max 0.05, 0.005, 0.5 | 1/d | r_i on the amino-acid shares, gated by that organism's biomass | est.; evidence of the route: koji Strecker/Ehrlich aldehydes ×10²–10³ over raw rice (`02:J2`), LAB 3-methylbutanal in Gouda (`03:S32`), koji fish sauce α-keto-acid decarboxylase (`04:G2`) |
| methionine → methionol, yeast | k_max 0.05, 0.01, 0.3 | 1/d | r_i on P_Met | est.; precursor limitation from `05:JL26` (methionol ×~140 with methionine as N source); median to be set against `04:M8` |
| methionol share of converted methionine (rest: acid, methional, methanethiol) | 0.5, 0.2, 0.9 lin | — | split | est. |
| AAB oxidation of fusel alcohols (source on the matching acid) | k_max 0.1, 0.02, 0.5 | 1/d | c_ij (AAB) | derived: kombucha 3-methylbutanol 5 633 (D3) → 2 014 (D14) = 0.093 d⁻¹ net, a lower bound (`02:K2`, semi ratio); vinegar ×0.07 over an acetification (`02:V3`) |
| AAB oxidation of 2-phenylethanol | k_max 0.005, 0, 0.02 lin | 1/d | c_ij | `02:V1` n.s.; `02:V3`, `V4` ×1.5–1.6 rise: poor AAB substrate |
| abiotic loss of fusel alcohols | T12 only | — | k⁰ | `05:Godillot23`: evaporation "negligible" (K_aw 4.9×10⁻⁴) |

The free-amino-acid pool does not modulate the branched-chain yields: across 70–210 mg N/L their effect is ±15 % (`05:Godillot23`), inside the prior (D1).

### 5.2 T2 Esters and medium-chain fatty acids

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| isoamyl acetate : isoamyl alcohol | 0.010, 0.0062, 0.015 lin | mol/mol of parent flux | b = ratio × b(parent) × MW ratio | `05:Godillot23` Table 2 ("Ratio IsoA"), rises with N |
| isobutyl acetate : 2-methylpropanol and 2-phenylethyl acetate : 2-phenylethanol | 0.010, 0.003, 0.03 | mol/mol | b | est.: same Atf route (labels match the parent alcohol, `05:Rollero17`), ratio not measured |
| *K. marxianus* multiplier on acetate esters | 1.3, 0.9, 1.9 | × | b | `05:Zhang22` (isoamyl acetate ×0.9–1.9, semi) |
| b(ethyl acetate), *S. cerevisiae* | 0.18, 0.11, 0.32 | mg/g | b_ij | derived: wine 22.5–63.5 mg/L (`05:Saerens10` Table 2) ÷ 200 g/L sugar (est. sugar of a dry wine) |
| b(ethyl acetate), *K. marxianus* | 1.8, 0.5, 24 | mg/g | b_ij | `05:Zhang22` ×9–12 vs *S. cerevisiae* in static cider → 1.6–2.2; hi = aerobic basal 24 mg/g (`05:Hoffmann21` Table 1) |
| b(ethyl acetate), heterofermentative LAB | 0.05, 0.005, 0.3 | mg/g | b_ij | est.; *F. sanfranciscensis* alone made as much as *S. cerevisiae* in dough (area 9.66 vs 5.38, `02:S4`) |
| *A. oryzae* acetate esters (ethyl acetate, isoamyl acetate) | a = 0.01, 0.001, 0.1 | mg/g mycelium | a_ij, with fungal esterase loss k_max 0.5, 0.1, 2 1/d after growth stops | est.; transient: enriched mid-fermentation, lower at 48 h (`02:J1`) |
| b(ethyl hexanoate), yeast | 0.0025, 0.0012, 0.005 | mg/g | b_ij | `05:Godillot23` 0.42–0.58 mg/L ÷ 200 = 0.0021–0.0029 (derived), ×/÷ 2 est. |
| b(ethyl octanoate), yeast | 0.0025, 0.0012, 0.005 | mg/g | b_ij | `05:Godillot23` 0.39–0.63 mg/L ÷ 200 = 0.0019–0.0032 (derived), ×/÷ 2 est. |
| b(ethyl decanoate), yeast | 0.0005, 0.0001, 0.003 | mg/g | b_ij | est.: b(C8) × excreted-fraction ratio 0.12/0.6 (`05:Saerens10`) |
| b(ethyl butanoate), yeast | 0.0007, 0.00005, 0.009 | mg/g | b_ij | derived: wine 0.01–1.8 mg/L (`05:Saerens10` Table 2) ÷ 200; median at the geometric midpoint |
| b(ethyl 2-methylbutanoate), b(ethyl 2-methylpropanoate), yeast | 0.00003, 0.000005, 0.0002 | mg/g | b_ij | derived: 1/100–1/300 of ethyl hexanoate in sourdough (`02:S3`: nd–0.61, nd–1.73 vs 4.17–604 µg/kg) × b(ethyl hexanoate) |
| LAB b(ethyl butanoate), b(ethyl 2-methylbutanoate) | 0.001, 0.0001, 0.01 | mg/g | b_ij | derived-est.: kimchi peaks 22.8 and 35.3 µg/kg (semi) over ~25 g/kg sugar (`03:S10`) ≈ 0.001 mg/g; ×/÷ 10 for semi and loss |
| Q10 of ethyl-ester b | 1.0, 0.7, 1.4 | — | b(T) | conflict `05:Godillot23` (−28 %/10 °C) vs `05:Saerens08` (+), § 9.2 |
| b(hexanoic), b(octanoic), b(decanoic), yeast | 0.005, 0.0005, 0.05 each | mg/g | b_ij | est.: no usable yield (`05:` Liu 2021 not used, `05:E6`); median twice the ethyl-ester yield (fatty acyl-CoA is the esters' limiting precursor, `05:Saerens08`), two-decade range |
| excreted fraction | C6 1.0; C8 0.60, 0.54, 0.68 lin; C10 0.12, 0.08, 0.17 lin | — | multiplier on b where b is not a medium measurement | `05:Saerens10` Intro (citing Nykänen & Nykänen 1977) |
| sanity bounds | beer: ethyl acetate 8–32, isoamyl acetate 0.3–3.8, 2-phenylethyl acetate 0.10–0.73, ethyl hexanoate 0.05–0.21, ethyl octanoate 0.04–0.53 mg/L | — | test bound | `05:Saerens10` Table 1 |

Abiotic ester hydrolysis and chemical ethyl acetate: T5. Stripping: T12.

### 5.3 T3 Acetaldehyde

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| b, *S. cerevisiae* (gross) | 2.0, 0.4, 42 | mg/g | b_ij | `05:LiMira11`: 0.4–42 mg/g glucose, 26 strains (resting cells, abs.); median est. low because growing-cell peaks are 2.2–189 mg/L at ~200 g/L sugar |
| re-uptake, yeast | k_max 1.0, 0.2, 5 | 1/d | c_ij | `05:LiMira11`: all strains degrade it, rate unrelated to production; magnitude est., tuned so the residual after fermentation is 14–34 mg/L (`05:LiMira17`, *S. cerevisiae*) |
| b, *K. marxianus* | 2.0, 0.4, 24 | mg/g | b_ij | hi = 16–24 mg/g under Fe/O₂ limitation (`05:Hoffmann21` Table 1); median est. as *S. cerevisiae* |
| b, LAB | 0.5, 0.05, 3 | mg/g | b_ij | derived order: kefir 3 800–23 600 µg/kg (`03:S20`, abs.) over ~12 g/kg lactose fermented (`03:S23`: lactic 10.6 g/L) ≈ 0.3–2 mg/g |
| AAB (ALDH) removal | k_max 5, 1, 20 | 1/d | c_ij (AAB) | est.; "consumed in substantial amounts", never accumulates (`02:V1`); vinegar ×0.24 (`02:V4`) |
| AAB production | 0 | — | — | est. (D11: a net intermediate) |
| bound | wine 'a few' to ~60 mg/L, higher at 30 °C | — | test bound | `05:Romano94` (abs.) |

### 5.4 T4 Citrate → α-acetolactate → diacetyl / acetoin / 2,3-butanediol

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| P_citrate,0 (milk) | 9.0, 6.3, 11.7 lin | mmol/kg | P0 | D4, § 6 |
| citrate-active share of the *Lc. lactis* population | 0.5, 0.1, 1.0 lin (clipped to 0–1) | — | multiplies uptake | est.: the model's *Lc. lactis* stands for mixed starters; the cit⁺ (biovar *diacetylactis*) share is in no opened source |
| citrate uptake, cit⁺ LAB | k_max 12, 5, 36 (= 0.5, 0.2, 1.5 per h) | 1/d at 30 °C | r on P_citrate | derived order: citrate exhausted at ~6 h in 10 % RSM at 30 °C (`03:S30` p. 5519); range est. |
| pH factor of uptake | CPM, optimum 5.5–6.0 | — | r(pH) | `05:Starrenburg91` (abs.) |
| *Leuconostoc* sugar gate | C4 from citrate off while hexoses > 1.8 g/kg (10 mM) | — | gate | `05:Cogan81` (abs.): 10 mM glucose or lactose "totally inhibited acetoin production" |
| C4 share of citrate-derived pyruvate, *Lc. lactis* | 0.4, 0.3, 0.5 lin | mol/mol | yield; α-acetolactate = 0.5 × share mol per mol citrate (1 citrate → 1 pyruvate; 2 pyruvate → 1 α-AL) | `05:Verhue91` (abs.): 30–50 % to α-acetolactate/acetoin |
| same, *Leuconostoc* | 0.7, 0.3, 1.0 lin | mol/mol | yield | hi: "all of the citrate utilized was recovered as acetoin" at pH 4.3 (`05:Cogan81`); median est. |
| sugar-derived acetoin, LAB (no citrate) | 0.002, 0.0002, 0.023 | g/g sugar | b_ij | `03:S31` (abs.): 2.3 % aerobic, none anaerobic → closed ferments near the low end (median est.) |
| α-acetolactate total decay at 30 °C | 0.10, 0.05, 0.20 | 1/h | chem | derived: 2.5 mM (6 h) → ≈ 0.4 mM (24 h), ln(6.25)/18 h (`03:S30` Fig. 1, fig.) |
| oxidative share (→ diacetyl; rest → acetoin) | 0.05, 0.02, 0.20 lin | — | chem split | derived lower bound: Δdiacetyl ≈ 0.06 mM vs Δα-AL ≈ 2.1 mM from 6 to 24 h (≈ 3 %) plus what reduction removed (`03:S30`, fig.); hi est. |
| Q10 of α-acetolactate decay | 2.0, 1.5, 3.0 | — | chem(T) | est. (`05:Kobayashi05` formulated it vs T, pH, ethanol; no numbers, `05:E3`) |
| diacetyl → acetoin reduction, yeast and *Leuconostoc* | k_max 2, 0.5, 10 | 1/d | c_ij | `03:S27` (abs.): C4 destroyed once citric acid fell to ~1 000 / 600 µg/g (*Leuconostoc* gate: on below 800, 600–1 000 µg/g); `03:S19` (abs.): no diacetyl in grain kefir (yeast-rich); rate est. |
| same, *Lc. lactis* | k_max 0.05, 0.005, 0.3 | 1/d | c_ij | est.: `03:S30`'s lactococcus kept diacetyl rising to 24 h |
| acetoin → 2,3-butanediol, yeast and LAB | k_max 0.2, 0.02, 1.0 | 1/d | c_ij | est.; storage check: kefir acetoin 25 000 → 16 000 µg/kg over 21 d at 4 °C = 0.021 d⁻¹ (`03:S19`, derived) |
| AAB: 2,3-butanediol → acetoin | k_max 0.5, 0.1, 2 | 1/d | c_ij (sink on butanediol, source on acetoin) | est.; direction `02:V1`, `02:V12` (abs.) |
| 2,3-pentanedione : diacetyl formation | 0.3, 0.05, 1.0 | mol/mol | chem split | est.: the isoleucine-pathway analogue (α-aceto-α-hydroxybutyrate); both present in koji (`02:J2`), no ratio |

AAB oxidation of lactate to acetoin (`02:V12`) is not modelled: the engine's vinegar has no lactic acid.

### 5.5 T5 Chemical esterification and hydrolysis

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| k_hyd at pH 3.58, ~21 °C: isoamyl acetate / isobutyl acetate / 2-phenylethyl acetate / ethyl butanoate / ethyl hexanoate / ethyl octanoate | 32.6 / 40.0 / 46.6 / 18.2 / 25.8 / 44.5, each ×/÷ 1.5 | 10⁻⁹ s⁻¹ (32.6 ≈ 0.0028 d⁻¹, t½ ≈ 250 d) | k⁰ | `05:RameyOugh80` Table IV (12 % ethanol); "~21 °C" inferred from Table II; ×/÷ 1.5 est. for that inference |
| k_hyd for ethyl acetate, ethyl lactate, ethyl decanoate, ethyl 2-methyl esters | 20, 7, 60 | 10⁻⁹ s⁻¹ | k⁰ | est.: not measured (ethyl decanoate too fast to quantify); ethyl butanoate/hexanoate as stand-in, ×/÷ 3 |
| pH exponent n (k ∝ [H⁺]ⁿ) | 0.8, 0.3, 1.0 lin | — | k⁰(pH) | derived: ethyl butanoate 18.2 → 64.1 from pH 3.58 to 2.95: n = 0.87; ethyl hexanoate 0.80; ethyl octanoate ≈ 0.2 (Tables IV–V) |
| activation energy | per ester 10.4–16.8 kcal/mol → Q10 1.8–2.5 near 25 °C | — | k⁰(T) | `05:RameyOugh80` Table II; Q10 derived |
| esterification equilibrium K | 4, 1, 16 | — (neat-mixture basis) | chem: forward = k_hyd · (K / 55.5 M) · [RCOOH, neutral] · [EtOH] (mol/L) | `05:RameyOugh80` Intro (citing Berthelot); dilute-aqueous K unverified (`05:E1`), hence the range; esterification acts on the neutral acid (est.) |

Sanity check (derived): kombucha with 6 g/kg acetic acid (0.1 M, ~all neutral at pH 3) and 4.6 g/kg ethanol (0.1 M): equilibrium ethyl acetate = 4 × 0.01 / 55.5 M ≈ 63 mg/kg; at k_hyd ≈ 0.003 d⁻¹, 14 days reach ~4 % of it ≈ 2.5 mg/kg, the order of `02:K3`'s 0.6–7 mg/L. So chemistry matters for kombucha and vinegar ethyl acetate within weeks, and for ethyl lactate in miso over months.

### 5.6 T6 Glucosinolates (myrosinase → isothiocyanate / nitrile)

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| P0 sinigrin, gluconapin | § 6 | µmol/g FW | P0 | § 6 |
| release (myrosinase + LAB) at 20 °C | 0.7, 0.3, 1.5 | 1/d | r_i | est. from time points: steep loss on days 2–5, none left at 7 d at 20 °C (`05:Palani16`); traces at 7 d, 25 °C (`05:MV09`); 91–100 % lost in over-fermented kimchi (`05:Kim22`) |
| volatile-product share of degraded glucosinolate (ITC + nitrile) | 0.05, 0.005, 0.3 | mol/mol | yield | derived: < 5 % of sinigrin recovered as AITC + allyl cyanide in stored sauerkraut (`05:CiskaPathak04`, abs.); 70–96 % for glucoraphanin products shows the share is GSL-specific |
| ITC fraction of the volatile product | 0.5, 0.1, 0.9 lin | — | split (rest → nitrile, conc-only) | `05:Puc25b`: nitriles + epithionitriles 82 ± 4 % (red cabbage seedlings, autumn); `05:Puc25a`: white cabbage shows no strong seasonal shift; `05:Hanschen24`: acid favours ITC |
| ITC loss at 15 °C | 0.16, 0.08, 0.4 | 1/d | k⁰ (chemical + volatility) | derived: kimchi 3-butenyl ITC 553 (d7) → 148 (d15) after release ended, ln(3.74)/8 d (`03:S10`, semi ratio) |
| release starts | at t0 (shredding, salting) | — | — | `03:S10` (salting activates myrosinase) |

AITC stability alone is no help: "relatively stable" at pH 5–7 in buffered water (`05:Tsao00`, abs.); no half-life (`05:E9`).

### 5.7 T7 Sulfur (S-methylcysteine sulfoxide, methionine)

Each sulfide is the sum of two linear pools: a **burst pool** made at tissue disruption (salting) that decays fast, and a **fermentation pool** made by the LAB that decays only by T12.

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| P0 SMCSO | § 6 | µmol/g FW | P0 | § 6 |
| burst pool at t0 (kimchi recipes, post-salting): DMDS / DMTS | 205 / 425 (×/÷ 3, semi) | µg/kg | initial | `03:S10` Table 3 (d0) |
| burst pool at t0, dry-salted sauerkraut | 50, 10, 300 (DMDS); 50, 10, 500 (DMTS) | µg/kg | initial | est.: same order as salted kimchi cabbage; acidification later stops SMCSO hydrolysis (`05:Hanschen24`) |
| burst decay at 15 °C: DMDS / DMTS | 1.1 (0.5–2.5) / 1.5 (0.7–3.0) | 1/d | k⁰ (burst pool) | derived: 204.6 → 6.7 and 425.4 → 4.3 from d0 to d3 (`03:S10`, semi ratios) |
| fermentation pool, LAB yield: DMDS / DMTS | 0.002 (0.0002–0.02) / 0.001 (0.0001–0.01) | mg/g sugar | b_ij (LAB) | derived: fermented kraut 30–78 µg/kg DMDS and 22–31 µg/kg DMTS vs 2.3 and 0.5 in the acidified, unfermented control after 9 months (`03:S1` Table 5) over ~30 g/kg sugar |
| DMS : DMDS in the fermentation pool | 0.3, 0.05, 1.0 | mol/mol | split | est.; DMS and DMDS "most dominant" sulfur compounds of household kraut (`03:S9`) |
| methanethiol (intermediate) → DMDS oxidation | 5, 1, 20 | 1/d | chem | est.; methanethiol is the proposed precursor (`03:S10` Discussion); too volatile for SAFE |
| LAB methionine → methional / methanethiol | 0 by default; strain flag | — | c/b | `05:Amarita01` (abs.): only 1 of the screened lactococci high |
| alliin → garlic sulfides | not used | — | — | garlic disulfides dropped (D7); alliin P0 recorded in § 6 |

### 5.8 T8 Lipid oxidation, mould C8 and milk fat

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| initial aldehydes, ketones, lactones, fatty acids | § 6 | µg/kg | P0 (initial) | § 6 |
| reduction of n-aldehydes and (E)-2-nonenal by *Lactobacillus*, *Leuconostoc*, yeast | k_max 0.3, 0.05, 1.5 | 1/d | c_ij | `05:Engels22` (lactobacilli and leuconostocs lower them); rate est.; check: kombucha hexanal 9.07 → 1.93 over 9 d = 0.17 d⁻¹ (`02:K1`, semi ratio) |
| same, *Lactococcus* | 0 | — | c_ij | `05:Engels22`: lactococci "generally did not" |
| LOX formation after t0 | none | — | — | capacity is lost in fermentation (`03:S13`); salting inactivates LOX (`03:S10`, citing Kim 1997) |
| loss of (E)-2-nonenal and (Z)-3-hexenal in vegetable brines | 0.9, 0.5, 2.0 | 1/d | k⁰ + c | derived lower bound: cucumber (E)-2-nonenal not detected after day 5 (`03:S13`, area: ≥ ln 100 / 5 d) |
| (Z)-3-hexenol residual release / loss (kimchi, 15 °C) | 0.3, 0.1, 1.0 / 0.3, 0.1, 1.0 | 1/d | r / k⁰ | est., shaped to `03:S10` (peak d5, then 0.16× by d15) |
| *A. oryzae* 1-octen-3-ol | a = 0.02, 0.002, 0.2 | mg/g mycelium | a_ij | est.: a 48 h koji should reach 10²–10³ µg/kg; anchor 187–266 µg/kg on tomato pomace (*A. sojae*, *T. atroviride*, `05:Guneser17`, abs., other substrate); no rice-koji value (`05:E15`) |
| C8 split relative to 1-octen-3-ol: 3-octanone / 3-octanol / 1-octen-3-one | 0.4 (0.1–1) / 0.2 (0.05–0.6) / 0.05 (0.01–0.2) | mol/mol | split of a | order 1-octen-3-ol > 3-octanone > 2-octen-1-ol > 1-octen-3-one (`05:Miyamoto14`); values est. |
| *A. oryzae* 2-heptanone, 2-nonanone (methyl-ketone β-oxidation) | a = 0.005, 0.0005, 0.05 each | mg/g mycelium | a_ij | est.; direction `02:J1` (rise to 48 h on bran) |
| δ-lactone release from milk fat | precursor pool = (5, 1, 20) × the initial free lactone; release 0.7, 0.1, 2.4 | 1/d | r_i | est., shaped to kefir (`03:S23`: δ-decalactone 240 → 1 540 µg/L in 48 h, semi); mechanism: direct lactonisation from triglycerides suggested (`03:S32` Discussion) |
| milk free fatty acids | initial pools only (§ 6); in-ferment increase from T2 yeast b | — | — | raw ≫ pasteurised (`03:S34`); no in-ferment lipolysis rate opened |
| fish lipid oxidation (garum: hexanal, nonanal, 2-pentylfuran, (Z)-4-heptenal, 1-octen-3-ol) | zero-order source 1, 0.1, 10 µg/kg/d at 25 °C each, Q10 2; loss 0.005, 0.001, 0.02 1/d | µg/kg/d; 1/d | chem; k⁰ | est.; no fish-lipid pool curated; shapes `04:G1`, `04:G2` (semi) |

### 5.9 T9 Terpenoids (tea; free pool + glycoside release)

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| free and bound pools at t0 | § 6 | µg/kg | P0 | § 6 |
| yeast β-glucosidase release from the bound pool | k_max 0.1, 0.02, 0.5 | 1/d | r_i (yeast-gated) | est.; direction: linalool ×4.7 to D7 (`02:K2`), yeast-dependent (`02:K4`: 8.17 *Z. parabailii*, 4.14 *B. bruxellensis*, 11.27 µg/L co-culture) |
| acid hydrolysis release | 0.002, 0.0005, 0.01 | 1/d | chem | est.; "slowly released … in a weakly acidic environment" (`05:Yan24`, abs.) |
| release split: linalool / geraniol / methyl salicylate | 0.4 (0.2–0.6) / 0.3 (0.1–0.5) / 0.3 rest | — | split | est.; Keemun bound pool: linalool-oxide > geranyl > benzyl > 2-phenylethyl glycosides (`05:Zhou26tea`) |
| first-order loss at 30 °C: geraniol | 0.03, 0.01, 0.1 | 1/d | k⁰ | derived: 18.03 → 12.09 over 14 d (`02:K1`, semi ratio) |
| limonene | 0.15, 0.07, 0.5 | 1/d | k⁰ | derived: 13.0 (D2) → 3.4 (D11) (`02:K1`) |
| methyl salicylate, β-ionone | 0.3, 0.15, 1.0 | 1/d | k⁰ | derived: 17.61 → 10.05 and 2.77 → 1.63 from D0 to D2, both nd from D4 (`02:K1`) |
| linalool (incl. rearrangement to α-terpineol at pH ~3) | 0.05, 0.01, 0.2 | 1/d | k⁰ | est.; linalool oxides fell 0.08 d⁻¹ (`02:K1`); α-terpineol rose (table D) |
| β-damascenone, citronellol | 0.05, 0.01, 0.3 | 1/d | k⁰ | est. |

### 5.10 T10 Hydroxycinnamic acids → vinylphenols

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| P0 ferulic acid | § 6 | mg/g DM | P0 | § 6 |
| feruloyl-esterase release by yeast | k_max 0.5, 0.1, 2 | 1/d | r_i | rate est.; extent: 60–90 % of ferulic acid hydrolysed in a beer fermentation (`05:Coghe04`, abs.) |
| decarboxylation, *S. cerevisiae* | Pof⁺ with P = 0.5 per member (est.); k_max 1, 0.2, 5 | 1/d | c_ij (sink on ferulic, source on 4-VG) | `05:Coghe04`: Pof⁺ yeast → more 4-vinylguaiacol; Pof⁺ share of baker's/kombucha strains not in the files (est.) |
| decarboxylation, *L. plantarum* | active with P = 0.12 per member; k_max as yeast | 1/d | c_ij | `05:Rosimin15` (abs.): 6 of 50 kimchi isolates (all *L. plantarum*, padA⁺) |
| vinyl : dihydro split (dihydroferulic acid is odourless) | 0.3, 0.05, 0.8 lin | — | split | `05:Rogozinska21` (abs.): *L. plantarum* 299v only reduces ferulic acid; split est. |
| yield | 0.773 | g 4-VG / g ferulic acid | stoichiometry | 150.2 / 194.2 g/mol |
| 4-vinylguaiacol loss | 0.01, 0.002, 0.05 | 1/d | k⁰ | est. (low volatility; no Henry value parsed in `05`) |

### 5.11 T11 Slow chemistry (HEMF, furanones, maltol, pyrazines, Strecker)

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| HEMF precursor formation | zero-order source ∝ koji amylase activity (engine pool `amylase`) and soybean present; rate est., calibrated to the `04:M9` base case | µg/kg/d | chem | `04:M1` (no furanones without soybean); `04:M9` Fig. 6 (xylose + alanine → ≈ 57 000 µg/kg) |
| HEMF precursor decay without yeast, 30 °C | 0.05, 0.02, 0.15 | 1/d | k⁰ | est.; `04:M9`: at 10⁴ yeast/g HEMF 3 500 at 45 d → 0 at 60 d; precursor peaks at ~2 weeks of aging at 37 °C (`04:M1` Fig. 5) |
| *Z. rouxii* conversion precursor → HEMF | k_max 0.1, 0.03, 0.3; only at pH < 5.6 | 1/d | r_i (yeast-gated) | est.; pH gate `04:M10` (formation starts once pH < 5.6); no HEMF without yeast (`04:M9` Fig. 1) |
| HEMF chemical loss at 30 °C | 0.031, 0.02, 0.045 | 1/d | k⁰ | derived: 16 890 (20 d) → 4 870 (60 d) with yeast stopped (`04:M9` Table 3) |
| Q10 of HEMF loss | 3.9, 2.5, 6 | — | k⁰(T) | derived: 0.031 (30 °C) vs 0.008 d⁻¹ (20 °C; 16 120 → 11 690) (`04:M9` Table 3); ≈ 0 at 10 °C |
| furaneol (HDMF) formation at 30 °C | 50, 15, 150 | µg/kg/d | chem | derived: 1 470 µg/kg in 4 weeks, barley miso (`04:M1` Table 3) |
| Q10 of furaneol formation | 2.4, 2.0, 4.0 | — | chem(T) | derived: 610 (20 °C) → 1 470 (30 °C); 410 (15 °C) → 610 (20 °C) = Q10 2.2; 30 → 37 °C steeper (`04:M1` Table 3) |
| norfuraneol uptake by *Z. rouxii* | k_max 0.2, 0.1, 0.5 | 1/d | c_ij | derived: 15 000 → 4 000 in 4 d (37 °C pre-aged) and 8 000 → ~2 250 in 8 d (30 °C pre-aged) (`04:M1` Fig. 4, fig.) |
| maltol loss | 0.015, 0.007, 0.03 | 1/d | k⁰ | derived: 1 430 (0 d) → 240 (120 d) (`04:M2` Table 2, app.; T not stated) |
| pyrazines | initial pool only (cooking), T12 loss | — | P0 | `04:M10` (present only in barley and soybean miso) |
| Strecker aldehydes from free amino acids (miso, garum) | 0.5, 0.05, 5 µg per g amino acid per day at 25 °C; Q10 2.5, 1.5, 4 | µg/(g·d) | chem on the T1 amino-acid shares | est.: no Arrhenius parameters near ambient (`05:E18`); shapes `04:M3`, `04:G2` |
| Strecker aldehyde → acid oxidation (long ferments) | 0.002, 0.0005, 0.01 | 1/d | k⁰ | derived-est.: garum phenylacetaldehyde 11.6 (24 mo) → nd (48 mo) while phenylacetic acid rose to 516 (`04:G1`, semi) |

### 5.12 T12 Volatility loss (all compounds)

| parameter | prior (median, lo, hi) | units | maps to | source or est. |
|---|---|---|---|---|
| K_aw at 25 °C | acetaldehyde 3.1×10⁻³; ethyl acetate 6.2×10⁻³; isoamyl acetate 1.9×10⁻²; ethyl butanoate 1.6×10⁻²; ethyl hexanoate 2.1×10⁻²; ethyl octanoate 2.4×10⁻²; ethyl lactate 2.4×10⁻⁵; diacetyl 5.5×10⁻⁴; 3-methylbutanol, 2-methylpropanol 4.9×10⁻⁴; 2-phenylethanol 2.4×10⁻⁵; 3-methylbutanal 1.7×10⁻²; hexanal 9.0×10⁻³; (E)-2-nonenal 7.0×10⁻³; 1-octen-3-ol 2.1×10⁻³; AITC 1.9×10⁻²; methanethiol 0.11; DMS 7.6×10⁻²; DMDS 7.0×10⁻²; DMTS 3.4×10⁻²; linalool 2.0×10⁻³; TMA (neutral) 4.1×10⁻³; acetic acid (neutral) 1.0×10⁻⁵ | — | k_strip, k_surf | `05:Sander23` (row per `05` § 11); K_aw = 1/(H·R·T) derived. Spread: the page's min–max (`05` § 11) as a ×/÷ range |
| K_aw for compounds without a value | class stand-in, ×/÷ 10: esters → ethyl hexanoate; alcohols → 3-methylbutanol; aldehydes → hexanal; ketones → diacetyl; acids → acetic; terpenes → linalool; furanones, lactones, phenols, pyrazines, maltol → 2-phenylethanol | — | — | est. |
| K_aw temperature factor | ×2.1 (1.9–2.3) per +10 °C | — | K_aw(T) | derived: d ln H/d(1/T) = 5 500–7 200 K (`05:Sander23`) |
| CO₂ stripping | k_strip = (dCO₂/dt ÷ 44.01 × 24.5 L/mol) × K_aw × η, on the engine's CO₂ flux (g/kg/h), only when `co2_escapes` | 1/h | k⁰ | form from `05` § 11 (derived) |
| stripping efficiency η | 0.35, 0.15, 0.7 lin | — | k_strip | derived: isoamyl acetate predicted 63 % loss vs 14–30 % measured (`05:Godillot23`, `05` § 11) |
| acids and amines | strip only as the neutral form (× f_neutral, D5) | — | — | `05:Sander23` constants are for the neutral form |
| open-surface loss k_surf (k⁰ = k_surf × K_aw): vinegar surface culture / kombucha / koji bed | 20 (5–80) / 10 (2–50) / 50 (10–200) | 1/d | k⁰ | vinegar derived: ethyl acetate −99 % over an assumed ~6-week acetification (`02:V3`; duration est.) → 0.11 d⁻¹ ÷ 6.2×10⁻³; kombucha and koji est. (`05:E19`) |
| closed jars (lacto-ferment, miso, garum, kefir, cheese) | k_surf = 0; CO₂ stripping only | — | — | est. |
| dough (sourdough) | no loss: gas stays in the dough | — | — | `profiles.py` `co2_escapes=False`; est. |

## 6. Precursor priors per ferment type

These go into `profiles.py` (per type) and the ingredient precursor map (per ingredient, spec § 4.1). "FW" = fresh weight. Pools are per kg of starting batch, scaled by the ingredient's mass share.

### 6.1 Precursor pools

| precursor | ingredient → types | prior (median, lo, hi) | units | source or est. |
|---|---|---|---|---|
| citrate | milk → kefir, cheese | 9.0, 6.3, 11.7 lin (≈ 1.74; 1.21–2.25 g/kg citric acid) | mmol/kg milk | `05:Grelet16` (mean 9.04 mmol/L, 3.88–16.12, n = 506) with SD 1.65 from `05:Chen24` → ±1.645 SD; `05:Garnsworthy06` = `03:S35` 11.3 / 9.7 / 10.1 mmol/L (1.86–2.17 g/L at 192.1 g/mol, derived) lies inside. The brief's 1.6–1.8 g/L is the low half of the same range |
| citrate | vegetables → lacto-ferment | not curated (0) | — | no value opened (`03` notes cabbage citrate is low); lacto-ferment C4 comes from the sugar route only (T4) |
| sinigrin (→ AITC, allyl cyanide) | white cabbage → lacto-ferment | 11, 3, 25 µmol/g DM → **1.0, 0.3, 3.0 µmol/g FW** | µmol/g | `05:Fabjan26`: 11.1 ± 1.2 (mean ± SE, 25 genotypes → SD ≈ 6, derived); FW via dry matter 9 % (5–17 %), derived from `05:Friedrich22` (SMCSO ≈ 1 % of DM and 3.2–10.2 µmol/g FW at 165.2 g/mol) |
| total GSL, white cabbage (context) | — | 42.0 (19.7–67.8) µmol/g DM; glucobrassicin 8.2, glucoiberin 7.9, progoitrin 4.7, glucobrassicanapin 3.3 (± SE 0.5–0.8) | µmol/g DM | `05:Fabjan26`; cv. Taler glucobrassicin 1.83–2.54 (`05:MV09`). Their products are non-volatile or not on the list: not modelled |
| gluconapin (→ 3-butenyl ITC) | white cabbage | 1.0, 0.2, 4.0 | µmol/g DM | est.: not among the GSL `05:Fabjan26` reports, but 3-butenyl ITC is present in sauerkraut (`03:S8`) |
| gluconapin | kimchi (napa) cabbage | total GSL 2.7–57.9 µmol/g DM (literature range quoted) × gluconapin share 0.3, 0.1, 0.6 lin | µmol/g DM | `05:Kim22` (Introduction); share est. (no profile opened) |
| 4-methylthio-3-butenyl GSL | radish | 54.8 (19.9–109.6) µmol/g | µmol/g (basis not stated) | `05:Ishida12` Table 3 — **recorded, unused** (mtb_itc dropped) |
| SMCSO (→ methanethiol, DMDS, DMTS, DMS) | white or red cabbage; napa cabbage (est. same) | 5.7, 3.2, 10.2 | µmol/g FW | `05:Friedrich22` (white 3.2–10.2, red 3.9–10.3); cross-check 185–2 218 ppm FW = 1.1–13.4 µmol/g (`03:S1`, secondary); stable over 8 months' cold storage (`05:Andernach24`) |
| alliin | garlic | ≈ 0.9 % FW (allicin after full conversion ≈ 0.4 %) | g/g | `05:Iberl90` (abs.) — **recorded, unused** (garlic disulfides dropped) |
| ferulic acid, total | wheat/rye flour → sourdough | 0.30, 0.18, 0.52 | mg/g DM | `05:Boudaoud21` Table 3 (sourdoughs 0.18–0.52; doughs 0.24–0.28) |
| ferulic acid, free share at t0 | flour | 0.03, 0.01, 0.10 | — | derived-est.: free 0.01 mg/g DM in bran vs 0.18–0.52 total (`05:Boudaoud21`); the rest needs esterase (T10) |
| ferulic acid | soy, rice → miso, koji | not curated | — | `05:E17` (no soybean HCA content opened): miso and koji 4-vinylguaiacol compute zero |
| p-coumaric acid | all | not curated | — | no value in any file: 4-vinylphenol is P0 pending |
| bound terpenoids (glycosides), total | tea → kombucha | 1.0, 0.5, 2.9 | mg/kg batch | derived: 105–366 µg/g made black tea (`05:Zhou26tea`, Keemun) × 5–8 g tea/kg (`02:K2` 5 g/L, `02:K1` 8 g/L); the kombucha recipe carries no tea entry, so 5 g/kg is the default (est.) |
| methionine, leucine, isoleucine, valine, phenylalanine | engine free-amino-acid pool × shares | T1 table | g/g | est. |
| HEMF precursor | koji + soybean → miso | formation rate, T11 | — | est. |
| TMAO | fish → garum | not curated | — | TMA inactive (D6) |

### 6.2 Ingredient-borne initial concentrations (µg/kg of the ingredient unless stated)

| ingredient → types | compound: prior or value | source |
|---|---|---|
| tea (free, at t0 of kombucha) | linalool 10, 3, 30 | est., anchored to the D14 absolute values 4–11 µg/L (`02:K4`) with the near-flat D0→D14 course of `02:K1` |
| tea, relative to linalool (same SBSE sample, derived ratios) | geraniol ×0.25 (`02:K1` D0: 18.03/72.2); methyl salicylate ×0.24 (17.61/72.2); β-ionone ×0.04 (2.77/72.2); limonene ×0.27 (black-tea infusion 60.3/222.3); hexanal ×0.045 (10.0/222.3); nonanal ×0.16 (34.7/222.3); each ratio ×/÷ 4 | `02:K1` Table 1 (semi; ratios within one sample, compound-specific recovery still unknown) |
| flour → sourdough | hexanal 500, 150, 2 000; (E)-2-nonenal 40, 20, 150; methional 50, 29, 300 | derived lower bounds: "OAV > 100" in rye flour (`02:S2`, abs.) × § 3 threshold medians (hexanal 340, (E)-2-nonenal 22, methional 29 µg/kg); hexanal cross-checked against the dough end point 100–372 µg/kg after it "decreased" (`02:S1`, `02:S3`) |
| flour | 1-octen-3-one, sotolon, (E,E)-2,4-decadienal | P0 pending (abstracts give FD/OAV, no numbers: `02:S1`, `02:S2`; `02:E`) |
| white cabbage (raw, shredded at t0 of sauerkraut) | hexanal 11.7, (Z)-3-hexenal 12.9, (Z)-3-hexenol 1 490, each ×/÷ 3 | `03:S10` Table 1 (napa cabbage, raw; semi) as stand-in (est.) |
| napa cabbage after salting (t0 of kimchi) | hexanal 1.9; (Z)-3-hexenal 0; (Z)-3-hexenol 10.4; methional 0.3; phenylacetaldehyde 6.6; acetoin 74; 2,3-butanediol 3.7; 3-butenyl ITC 212; DMDS 205; DMTS 425 (each ×/÷ 3) | `03:S10` Tables 1, 3 (semi) |
| cucumber (fresh) | hexanal 29; linalool 4.6 (free) | `03:S13` Table 2 (3-level standards) |
| milk, pasteurised / raw / UHT | hexanal 51.3 / 57.2 / —; diacetyl 9.7 / 11.1 / —; butanoic acid 1 094 / 32 110; octanoic acid 1 037 / 16 835; decanoic acid 380 / 7 167; δ-decalactone 138 / 292; δ-dodecalactone 844 / 2 388; 2-heptanone nd / nd / 23–44 (each ×/÷ 2) | `03:S34` Table 2 (external standard) |
| milk, UHT (kefir) | hexanoic acid nd; 2-nonanone 2 200 (semi, presence) | `03:S23` Table 3 |
| rice, bread crust → koji | hexanal: rice "4.05 ppm" (relative only); bread-crust substrate 180 µg/kg | `02:J2`, `02:J4` |
| cooked soybean → miso | maltol 2 980 (app.) / barley-miso mash P0 28 000 (3 400–59 000); furaneol 30 (app.); norfuraneol at end of mashing 8 000–15 000 (barley, fig.); 2,5-dimethylpyrazine and trimethylpyrazine 14–22 (app., barley and soybean miso only) | `04:M2` Table 2; `04:M1` Table 1, Fig. 4; `04:M10` Table 4 |
| koji → miso | 1-octen-3-ol: carried in from the koji tracer (koji ratio) | T8; magnitudes `04:M10` 20–76 (app.) |
| wine/cider base → vinegar (scale every value by ethanol₀ / 94 g/kg, derived: 200 g/L sugar × 0.47) | ethyl acetate 40 000 (22 500–63 500); isoamyl acetate 600 (100–3 400); isobutyl acetate 100 (10–1 600); 2-phenylethyl acetate 300 (50–18 500); ethyl butanoate 130 (10–1 800); ethyl hexanoate 300 (30–3 400); ethyl octanoate 400 (50–3 800); ethyl decanoate 100 (10–2 100) | `05:Saerens10` Table 2 (wine ranges; medians at geometric midpoints, lower ends est. where the range starts at 0) |
| wine base (cont.) | 3-+2-methylbutanol 110 000 (85 000–145 000); 2-methylpropanol 55 000 (35 000–80 000); acetaldehyde 24 000 (14 000–34 000); 2-phenylethanol 40 000 (10 000–160 000); 2,3-butanediol 500 000 (100 000–1 500 000) | `05:Godillot23` Table 2; `05:LiMira17`; 2-phenylethanol = T1 b × 200 g/L (derived); 2,3-butanediol est. (a main wine by-product; no value opened) |
| fish → garum | lipid aldehydes: zero at t0, formed by T8; TMAO not curated | — |
| rice → koji, miso | 2-acetyl-1-pyrroline | P0 pending |
| caraway, dill, mint, lemongrass, citrus, ginger | carvone, limonene, geranial, neral | P0 pending (listed in `not_modelled_aroma.ingredients` when logged) |

## 7. Calibration tests to pin

**Mechanics** (as `test_sauerkraut`): run the forecast prior-only (no readings) under the stated inputs, take the weighted **median** trajectory of each tracer, and assert. "Peak in a–b" = the median's argmax lies in that window; "X / Y" = ratio of median values at those times; "a–b µg/kg" = the published value ×/÷ 3 (spec § 4.3), only where the anchor is absolute. Inputs not stated by a source use the type's profile defaults and are marked "(profile)". Every test cites the § 4 row it pins. Kept as one parametrised test file per type.

### Kombucha (sweet tea 70 g/kg sucrose, 10 % starter, tea 5 g/kg, profile organisms)

1. **3-methylbutanol**, 28 °C: D7 > 2 × D0; D12 in 233–6 000 µg/kg. (`02:K1`, `K2`, `K3`)
2. **2-methylpropanol** (reported), 28 °C: D12 in 233–6 000 µg/kg. (`02:K3`)
3. **2-phenylethanol**, 30 °C: D7 > 2 × D0; D14 / D7 in 0.67–1.5. (`02:K1`, `K2`)
4. **Fusel acids** (3-methylbutanoic, 2-methylpropanoic), 30 °C: D14 > D2. (`02:K1`, `K2`)
5. **Ethyl acetate**, 28 °C: (D14 − D7) > (D7 − D0); D12 in 17–21 000 µg/kg. (`02:K2`, `K3`, `K4`)
6. **Late esters**, 30 °C: isoamyl acetate and ethyl hexanoate D4 < 0.25 × D14; 2-phenylethyl acetate D14 > 3 × D2; ethyl decanoate D7 > D0 and D14 / D7 in 0.67–1.5. (`02:K1`, `K2`)
7. **MCFA** (hexanoic, octanoic, decanoic), 30 °C: D7 > D0; D14 / D7 in 0.5–1.5. (`02:K1`)
8. **Lipid aldehydes**, 30 °C: hexanal D9 < 0.3 × D0; nonanal D14 ≤ max(D2…D7). (`02:K1`, `K2`)
9. **Tea terpenes**, 30 °C: geraniol D14 / D0 in 0.3–1.0; methyl salicylate D4 / D0 < 0.1; β-ionone D4 / D0 < 0.2; limonene D11 / D2 < 0.5. (`02:K1`, `K2`)
10. **Linalool**, 28 °C: D14 in 1.4–34 µg/kg (no direction asserted). (`02:K4`)

### Vinegar (wine base, ethanol₀ 55 g/kg, § 6.2 base pools, still surface culture, 30 °C; "end" = ethanol < 5 g/kg or 60 d)

11. **AAB sink**: 3-methylbutanol, 2-methylbutanol, 2-methylpropanol and acetaldehyde end / start < 0.5; 2-phenylethanol end / start in 0.8–2.0. (`02:V1`, `V3`, `V4`)
12. **AAB products**: 3-methylbutanoic and 2-methylpropanoic acid end / start > 1.5; acetoin end / start > 1.5. (`02:V1`, `V3`, `V4`)
13. **Surface stripping**: ethyl acetate, ethyl hexanoate, ethyl octanoate, ethyl decanoate, ethyl 2-methylpropanoate end / start < 0.5; isoamyl and isobutyl acetate < 0.7. (`02:V3`, `V4`)

### Sourdough

14. **Flour → levain directions**, levain 26 °C, 24 h (profile): 3-methylbutanal, 3-methylbutanol and diacetyl end > start; hexanal and (E)-2-nonenal end < start. (`02:S1`, `S2`)
15. **Cool dough end points**, wheat dough, 15 °C, 120 h, *S. cerevisiae* + *L. brevis* (repeat with *L. plantarum*): 3-methylbutanol 274–38 500; hexanal 33–1 100 µg/kg (calibrated); reported end points 2-methylbutanol 42–6 100, 2-methylpropanol 56–10 700, ethyl acetate 450–171 000, ethyl hexanoate 1.4–1 800, ethyl octanoate 0.23–182; upper bounds isoamyl acetate ≤ 20, ethyl butanoate ≤ 21, ethyl decanoate ≤ 11, ethyl 2-methylbutanoate ≤ 1.8, ethyl 2-methylpropanoate ≤ 5.2, 2-phenylethanol ≤ 209 000; lower bound methional ≥ 10 µg/kg. (`02:S3`, `S2`)

### Koji (steamed rice, 30 °C, 48 h, profile inoculum)

16. **C8 and methyl ketones**: 1-octen-3-ol, 3-octanone, 3-octanol, 2-heptanone, 2-nonanone with 12 h < 24 h < 48 h. (`02:J1`)
17. **Transient acetate esters**: ethyl acetate and isoamyl acetate peak in 12–40 h; 48 h < peak. (`02:J1`)
18. **Hexanal on rice**: 48 h / 0 h ≤ 2. (`02:J2`)

### Lacto-ferment

19. **Kimchi glucosinolate** (napa cabbage, post-salting pools of § 6.2, 2.5 % salt, 15 °C, 15 d, profile organisms): 3-butenyl ITC peak in d5–d9; d15 / peak < 0.5. (`03:S10`)
20. **Kimchi sulfides** (same run): DMDS d3 / d0 < 0.1 and d15 / d3 > 1.5; DMTS d3 / d0 < 0.05 and d5…d15 within ×/÷ 2 of each other. (`03:S10`)
21. **Kimchi esters**: ethyl butanoate peak in d5–d9, d3 < 0.2 × peak, d15 / peak < 0.4; ethyl 2-methylbutanoate peak in d7–d12, d15 / peak < 0.5. (`03:S10`)
22. **Kimchi LOX volatiles**: hexanal d3…d15 within ×/÷ 3 of t0; (Z)-3-hexenal never above t0; (Z)-3-hexenol peak in d3–d7, peak ≥ 3 × t0, d15 / peak < 0.4. (`03:S10`)
23. **Kimchi amino-acid aldehydes**: methional d15 ≥ 2 × d0; phenylacetaldehyde within ×/÷ 2 of t0 on every day. (`03:S10`)
24. **Cucumber** (2 % NaCl + 53 mM acetic acid, *L. plantarum* only, 10⁶/mL, 20 °C (profile; T not stated), 21 d): (E)-2-nonenal d5 / d0 < 0.01; hexanal d21 in 4–114 µg/kg. Linalool d21 in 15–240 µg/kg: **deferred** until a cucumber bound-linalool pool exists. (`03:S13`)
25. **Sauerkraut end points** (white cabbage, 2 % dry salt, *Leuc. mesenteroides*, 18 °C, 9 months): AITC 18–256, DMDS 10–234, DMTS 7–92 µg/kg. (`03:S1`)

### Kefir (whole milk + 3 % grains, profile organisms, 22 °C (profile; "room temperature"), 48 h)

26. **Carbonyl end points**: acetaldehyde at 24 and 48 h in 1 270–71 000 µg/kg; acetoin at 24 and 48 h in 8 300–75 000 µg/kg. (`03:S19`, `S20`, `S18`, `S26`)
27. **C4 directions**: diacetyl and 2,3-pentanedione 8 h > 0 h; diacetyl at 24 h ≤ 5 600 µg/kg. (`03:S21`, `S18`)
28. **Esters**: ethyl acetate, ethyl butanoate, ethyl hexanoate, isoamyl acetate 24 h > 0 h; ethyl octanoate peak ≤ 36 h and 48 h / 24 h < 0.6; ethyl decanoate 24 h < 0.3 × 48 h. (`03:S21`, `S23`)
29. **MCFA**: hexanoic, octanoic, decanoic acid non-decreasing over 0–48 h, 48 h / 0 h ≥ 1.5 (octanoic, decanoic; hexanoic from ~0). (`03:S23`)
30. **Milk-derived**: δ-decalactone non-decreasing, 48 h / 0 h ≥ 3; δ-dodecalactone 48 h / 24 h ≥ 1.3; 2-nonanone (UHT milk) 24 h / 0 h < 0.5. (`03:S23`)
31. **Ehrlich**: 2-phenylethanol 48 h / 24 h ≥ 2; 3-methylbutanol, 2-methylbutanol, 2-methylpropanol, 3-methylbutanal, 2-methylbutanal 24 h > 0 h. (`03:S21`, `S23`)
32. **Hexanal** (reported, milk baseline): 48 h in 17–154 µg/kg. (`03:S34`, `S21`)
33. *Optional, if the test harness supports a temperature schedule:* 48 h at 22 °C then 21 d at 4 °C: acetaldehyde d21 / d0 ≥ 0.5; acetoin d21 / d0 in 0.4–1.0. (`03:S19`)

### Cheese (milk, *Lc. lactis* with the citrate-active share fixed at 1, 30 °C, 24 h)

34. **Citrate → α-acetolactate → diacetyl**: citrate < 10 % of P0 by 8 h; α-acetolactate peak in 4–8 h; 0 < diacetyl(12 h) < diacetyl(24 h) ≤ 41 000 µg/kg. (`03:S30`)
35. **Acetoin**: non-decreasing to 24 h; acetoin / diacetyl at 24 h > 3; acetoin(24 h) ≤ 690 000 µg/kg. (`03:S30`, `S28`)
36. **Citrate switch**: with the citrate-active share at 0, citrate-derived diacetyl and acetoin are 0 (invariant). (T4)
37. **Milk baselines** (reported): butanoic, octanoic, decanoic acid, δ-decalactone, δ-dodecalactone, hexanal at 24 h within ×/÷ 3 of the pasteurised-milk values of § 6.2. (`03:S34`)

### Miso

38. **HEMF base case** (rice koji, koji ratio 10, 12 % NaCl, 50 % moisture, *Z. rouxii* 10⁶/g, no *T. halophilus*, 30 °C, 75 d): peak in 30–60 d; peak 5 700–51 000 µg/kg; 75 d / peak in 0.5–1.0. (`04:M9`)
39. **HEMF needs yeast**: same without *Z. rouxii*: max < 1 % of test 38's peak. (`04:M9` Fig. 1, `04:M10`)
40. **HEMF vs temperature**: 35 °C peak ≤ 30 d and 75 d / peak < 0.4; 25 °C argmax over 0–75 d ≥ 60 d. (`04:M9` Fig. 4; `04:M8`)
41. **HEMF chemical loss** (14 610 µg/kg at t0, yeast removed): 40-day factor 0.15–0.45 at 30 °C and 0.55–0.95 at 20 °C. (`04:M9` Table 3)
42. **Furaneol** (barley koji + soybean, *Z. rouxii*, 4 weeks): increases across 15 < 20 < 30 < 37 °C; at 30 °C in 490–4 400 µg/kg. (`04:M1` Table 3)
43. **Norfuraneol** (barley, 30 °C, after a 2-week pre-age, *Z. rouxii* added at t0): d8 / d0 in 0.1–0.35. (`04:M1` Fig. 4)
44. **Maltol** (rice miso, 25 °C (profile)): 120 d / 0 d < 0.3. (`04:M2`)
45. **Ehrlich alcohols** (red rice miso, 25 and 30 °C, 180 d): 3-methylbutanol peak in 45–120 d, 180 d / peak in 0.4–0.8, peak at 25 °C ≥ peak at 30 °C, peak ≥ 5 700 µg/kg; 2-phenylethanol peak in 45–120 d, 180 d / peak 0.25–0.6; methionol peak in 45–150 d, 180 d / peak 0.4–0.9; 2-methylbutanol and 2-methylpropanol 90 d > 30 d and 120 d < 90 d; 2-phenylethyl acetate 30 d < 0.2 × 120 d. (`04:M2`, `M8`)
46. **Long barley miso** (28 °C, 365 d): the eleven `04:M3` compounds of § 4.8 have 365 d > 90 d; 1-octen-3-ol marked expected-to-fail (no non-growth source). (`04:M3`)
47. **Reported end points** (barley miso, 180 d): 3-methylbutanoic acid 2 000–18 000; acetoin 630–5 700; 2,3-butanediol 81 000–730 000; ethyl lactate 1 300–11 700 µg/kg. (`04:M1`)

### Garum (traditional recipe: fish + salt, no koji)

48. **Acids over 4 years** (22 °C, 48 months): 3-methylbutanoic 48 / 12 mo ≥ 5; 2-methylpropanoic ≥ 3; butanoic 1.0–2.5; hexanoic 48 / 24 mo ≥ 1.5; octanoic 48 / 12 mo in 0.67–1.5; decanoic 0.5–1.1. (`04:G1`)
49. **Alcohol and ester**: 2-phenylethanol 48 / 12 mo ≥ 3; ethyl octanoate 1.0–3.0. (`04:G1`)
50. **Rise-then-fall aldehydes**: phenylacetaldehyde peak < 24 mo and 48 mo < 0.2 × peak; nonanal 7 mo > 3 mo and 48 / 12 mo < 0.2. (`04:G1`, `G2`)
51. **First 7 months** (20 °C, natural recipe): 3-methylbutanal, 2-methylbutanal, 2-pentylfuran, 1-octen-3-ol 7 mo > 3 mo; hexanal 7 mo < 3 mo. (`04:G2`)

### Recorded, not run (inactive compounds)

52. Kombucha 4-ethylguaiacol rises to D4, D14 / D7 in 0.67–1.5; 4-ethylphenol rises to D3, then plateau (`02:K1`, `K2`): enable when a *Brettanomyces* organism exists.

### Unit and invariant tests added to spec § 9

- D5 neutral fraction: f = 0.5 at pH = pKa; trimethylamine's effective threshold at pH 6.9 within ×2 of 440 µg/kg (`01:LSB` row Mall & Schieberle 2017).
- Mass balance per precursor: citrate (0.5 mol α-acetolactate max per mol), sinigrin, gluconapin, SMCSO, bound terpenes, ferulic acid, HEMF precursor: products ≤ precursor consumed.
- Data lint: every `class`/`est.` threshold carries its badge; `none` compounds have no OAV; every † cell computes 0; every calibrated/reported cell cites a source tagged with that type.

## 8. Dropped and inactive compounds

**Rule.** A compound is **dropped** when it has no usable water threshold and is not needed for the mass balance of a modelled pool; **conc-only** when it has no threshold but is a branch of a modelled pool; **inactive** when its producer is not a model organism. A ferment-level "drop" (§ 4) is separate: the compound exists, the ferment has no route to it.

| compound | status | reason | what would revive it |
|---|---|---|---|
| 4-ethylguaiacol | inactive | needs *Brettanomyces/Dekkera* vinylphenol reductase (kombucha, wine), *Candida/Torula* (soy; `04:M2` p. 1096) or *C. versatilis* (`04:G7`); not *Z. rouxii* | a *Brettanomyces* or *Candida* organism; kombucha targets are recorded (test 52) |
| 4-ethylphenol | inactive | as above; *B. bruxellensis* the top kombucha producer (`02:K4`) | as above |
| trimethylamine | inactive | TMAO reduction by spoilage bacteria ("bacterial decay", `04:G2`); no model organism documented as a TMAO reducer (not checked for *T. halophilus*, `04:E`) | a TMAO-reducer organism and a fish TMAO prior; the pH correction (D5, pKa 9.8) is already specified |
| (E)-4-(methylthio)-3-butenyl ITC | drop | threshold "unknown" (`01:BvG93` Table II); no ferment concentration; a loss path to a yellow pigment in salted radish (`03:S12`, abs.) | a water threshold (Japanese daikon/takuan literature, `01:E`); the radish GSL prior is already recorded (§ 6) |
| diallyl disulfide | drop | no water threshold (air only, unverified); reported in garlic kimchi (`03:S11`, abs.) | van Gemert 2011 or garlic literature thresholds (`01:E`); alliin prior recorded (§ 6) |
| allyl methyl disulfide | drop | no water threshold; calibrated rise in plain kimchi cabbage (`03:S10`) with an unclear precursor | a threshold and a mechanism |
| zingiberene | drop | no threshold; low-volatility sesquiterpene; ginger add-in only, no ferment data | a threshold (ginger AEDA work, `01:E`) and a ginger P0 |
| S-methyl thioacetate | drop | only a beer flavour threshold (50 µg/L, retronasal, `01:Kelting20`); presence in canned kraut only (`03:S2`) | an orthonasal water threshold (`01:E`) |
| allyl cyanide | conc-only | no threshold; the nitrile branch of sinigrin, so AITC's mass balance needs it | a threshold (`01:E`: Buttery 1976) |
| 2,3-butanediol | conc-only | no threshold ("known to be weak"); the end of the C4 chain and the AAB acetoin source | a water threshold (`01:E`) |
| 3-butenyl ITC | active, drill-down only | threshold is the ITC class range, but the compound is not named in the opened abstract | the full text of `01:MJ20` |

Inactive compounds are not shown; they are listed in `sensory.not_modelled_aroma.organisms` as "*Brettanomyces* / *Candida* yeasts (smoky, phenolic notes)" and "TMAO-reducing bacteria (fishy notes)", with the spoilage caveat of spec § 7 for the latter.

## 9. Conflicts between sources

### 9.1 Thresholds (> 10× between opened determinations)

The first 14 rows are the ones `01` flagged; the rest are additional > 10× spans in the priors chosen in § 3. "lit" = CZ Table 1 literature column (secondary, excluded from the priors).

| compound | values µg/kg (source) | spread | prior in § 3 | consequence |
|---|---|---|---|---|
| (E)-β-ionone | 3.5 (`01:CZ`, procedure C); 0.021 (`01:LSB` basic = Sellami 2018, Flaig 2020); lit 0.007–23 | 170× | (0.27, 0.021, 3.5): the two Munich values at 5 % / 95 % | LSB value supersedes CZ in Munich papers since 2018; a kombucha β-ionone OAV spans two decades |
| acetic acid | 99 000 (CZ); 5 600 (LSB, Dunkel 2014); lit 22 000–320 000; orange juice pH 3.6: 1 500; wine model 41 000 | 18× | (24 000, 5 600, 99 000) | the vinegary series and kombucha's "vinegar note" are uncertain by ~1 decade |
| decanoic acid | 10 000 (`01:LEF`); 3.5 (LSB basic, no details row; its only row is water/EtOH 60/40, 2 800) | 2 900× | LSB 3.5 **excluded** as a probable unit error; (10 000, 2 000, 50 000) single-source floor | `03:S23`'s kefir OAVs used 1 000; ours will be ~10× lower |
| ethyl acetate | 12 000 (LSB basic); 5–5 000 (LEF) | 2 400× | (1 400, 5.0, 12 000), deliberately wide | P(noticeable) of ethyl acetate stays honestly uncertain |
| 2-methylpropanol | 550 (CZ); 19 000 (LSB = Dunkel 2014); 1 900 (LSB row Féchir 2021); 7 000 (LEF) | 35× | (3 600, 550, 19 000) | — |
| octanoic acid | 190 (LSB, Wagner 2017); 3 000 (LEF) | 16× | (750, 190, 3 000) | — |
| 1-octen-3-ol | 45 (LSB); 1 (LEF); enantiomer not stated | 45× | (6.7, 1.0, 45) | koji/miso mushroom note uncertain by ~1.5 decades |
| methanethiol | 0.59 (LSB); 0.02 (LEF) | 30× | (0.11, 0.020, 0.59) | — |
| (Z)-3-hexenol | 3.9 (CZ); 70 (LEF); lit 39–347 | 18× (90× with lit) | (17, 3.9, 70) | — |
| geraniol | 1.1 (CZ); 40 (LSB); 40–75 (LEF); 4–75 (HSDB/Fenaroli) | 35–70× | (40, 1.1, 120) | CZ is below every other value |
| 4-ethylguaiacol | 4.4 (CZ); 50 (LSB, Grosch 1995); 50 (LEF) | 11× | (50, 4.4, 150) | inactive anyway |
| 2,3,5-trimethylpyrazine | 11 (LSB, Mall 2017); 400–1 800 (LEF) | 36–160× | (97, 11, 1 800) | — |
| sotolon | 0.49 (CZ); 1.7 (LSB); 0.001 and 0.04 (LEF lists it twice) | 1 700× with LEF | LEF **excluded** as doubtful; median 0.91 (not `01`'s 0.14); (0.91, 0.30, 2.7) | P0 pending anyway |
| ethanol | 990 000 (CZ); 100 000 (LEF); lit 25 000–900 000 | 10× | (310 000, 100 000, 990 000) | — |
| (Z)-4-heptenal | 0.0087 (CZ); 0.06 (LSB); 0.8 (LEF) | 92× | (0.060, 0.0087, 0.80) | — |
| linalool | 0.087 (CZ, (R)); 0.58–0.82 (LSB, rac/(R)); 6 (LEF, unspecified); (S) 2.7–8.3 | 95× | (0.80, 0.087, 8.3) | enantiomer of tea or cucumber linalool unknown |
| dimethyl disulfide | 1.7 (LSB); 0.16–12 (LEF) | 75× | (1.5, 0.16, 12) | — |
| ethyl 2-methylbutanoate | 0.008–0.02 (LSB rows); 0.013 (CZ); 0.1–0.3 (LEF) | 37× | (0.016, 0.0053, 0.30) | — |
| 2-methylpropanal | 0.49 (CZ); 0.1–2.3 (LEF) | 23× | (0.48, 0.10, 2.3) | — |
| dimethyl trisulfide | 0.0099 (CZ); 0.099 (LSB row Schmidberger 2020, exactly 10×: possible slip); 0.005–0.01 (LEF) | 20× | (0.0099, 0.0033, 0.099) | kraut/kimchi sulfur note |
| HEMF | 17 (LSB); 43 (LEF, Givaudan data sheet); 0.04–21 (`01:Schwab13`, secondary); "< 20 ppb" (`04:M7` citing Huber 1992) vs "≤ 0.04 ppb" (`04:M2` citing its ref. 6) | ~10³ | secondary values excluded: (27, 9.0, 81) | miso HEMF is 10³–10⁴ µg/kg, so P(noticeable) ≈ 1 under every value |
| furaneol, ethyl butanoate, nonanal, 3-methylbutanol, 2-phenylethanol | lit/secondary ranges of 3–5 decades (e.g. ethyl butanoate lit 0.0032–450) against modern values within ×1.5–8 | — | modern values only | — |

**OAVs quoted inside the research files use other thresholds** and are not targets: `03:S23` (decanoic 1 000, δ-decalactone 2.5, δ-dodecalactone 4.6, 2-nonanone 5, ethyl octanoate 19.3, octanoic 3 000), `04:G1` (3-methylbutanoic 30, DMTS 0.36, nonanal 1, phenylacetaldehyde 5, butanoic 240), `02:K1` (thresholds printed in ppm, ~10³× literature). The model recomputes every OAV from § 3.

**pH caveat in `01`.** "A threshold in neutral water understates the threshold at ferment pH for acids" holds only above the pH of the water measurement (~4 for a dilute acid): at pH 2.5–3.5 (kombucha, vinegar) D5's correction is ≈ 1, at pH 5–6.5 (cheese, miso, garum) it raises the effective threshold. One formula covers both.

### 9.2 Concentrations, directions and parameters

| topic | disagreement | how the prior or test spans it |
|---|---|---|
| Kombucha ethyl acetate magnitude | 600–7 000 µg/L (`02:K3`, abs., 28 °C, D12) vs 51.3 µg/L (`02:K4`, abs., 3-strain co-culture, D14; pairs < 10): 12–140× | test window spans both ×/÷ 3: 17–21 000 µg/kg (§ 7) |
| Kombucha 3-methylbutanol direction | monotone rise ×5 (`02:K1`) vs peak D3–7 then ×0.36 (`02:K2`, *Komagataeibacter* 68–96 %) | test only the shared rise D0 → D7; c_AAB prior reaches ~0 so both late shapes are allowed |
| Kombucha linalool direction | dip then partial recovery (`02:K1`) vs ×4.7 rise to D7 then fall (`02:K2`); yeast-dependent production (`02:K4`) | no direction test; end-point magnitude from `02:K4` (abs.) |
| Kombucha methyl salicylate | declines to nd by D4 (`02:K1`, `02:K2`) vs *B. bruxellensis* monoculture the top producer (`02:K4`) | decline (two time courses); *Brettanomyces* production not modelled (organism absent) |
| Vinegar ethyl acetate | no significant change, submerged (`02:V1`) vs −99 % in open surface flasks (`02:V3`) | process-dependent k_surf; the vinegar profile is still surface culture, so the test uses `02:V3`'s direction |
| Vinegar ethyl lactate | consumed (`02:V1`) vs rises (`02:V3`) | no direction test; tier reported |
| Vinegar 3-methylbutanol | consumed with a wine base (`02:V1`, `V3`, `V4`) vs rises with juice + added ethanol and no yeast stage (`02:V5`) | test with a wine base only |
| `02:V6` Sherry vinegar ranges | printed mg/L, some rows evidently µg/L | order of magnitude only, never a test |
| Kefir diacetyl | max 1 870 µg/kg (`03:S18`, defined starter) vs not detected in grain kefir (`03:S19`) vs key odorant by OAV (`03:S22`) | upper-bound test only; yeast reduction in the prior can remove it |
| UHT-milk 2-heptanone | 1 810 µg/L (`03:S23`, semi) vs 23–44 µg/kg (`03:S34`, external standard; nd in raw and pasteurised): 40–80× | initial pool from `03:S34`; `03:S23` treated as presence |
| Sourdough 2-phenylethanol | 15 729–69 598 µg/kg (`02:S3`) = 0.4–1.6 % of its ethanol (0.7–4.3 g/kg) vs 0.033 % in kefir (`03:S23`: 1.7 mg/L / 5.17 g/L) and ≈ 0.07 % in rice miso (`04:M2` 8.2 mg/kg / `04:M10` ~12 g/kg ethanol) (derived): 10–50× | `02:S3` 2-phenylethanol is presence and an upper bound, not an anchor. `02:S3` 3-methylbutanol (0.1–0.3 % of ethanol) matches wine (≈ 0.12 %: 110 mg/L at 94 g/L ethanol, `05:Godillot23`, derived) and is kept |
| Miso HEMF vs temperature | 25 °C peak ≈ ⅓ of the 30 °C peak (`04:M8`, porous polymer) vs 25 °C still rising to ≈ 13 500 at 75 d against a 17 000 peak at 30 °C (`04:M9`, solvent) | magnitude tests use `04:M9`; at 25 °C test only "peak later than at 30 °C" (both agree) |
| Miso HEMF without yeast | none without yeast (`04:M9` Fig. 1, `04:M10`) vs a rise 14 610 → 19 500 at 5 °C with yeast stopped by 2.8 % ethanol (`04:M9` Table 3) | the loss test uses 20 and 30 °C only; low-temperature chemical conversion is a gap |
| Ester temperature slope | total ethyl hexanoate/octanoate falls 18 → 28 °C, −28 %/10 °C (`05:Godillot23`) vs higher T → more ethyl octanoate/decanoate (`05:Saerens08`, abs.) | T-slope prior centred on no effect (Q10 0.7–1.4) |
| Milk citrate | 1.6–1.8 g/L (brief) vs 1.9–2.2 g/L (`03:S35`) vs 1.74 g/L mean (`05:Grelet16`) | reconciled in D4 / § 6 |
| Garum nonanal | 1 022 → 57 (12 → 48 mo, `04:G1`) vs 18 → 477 (3 → 7 mo, natural, `04:G2`) | consistent with rise-then-fall; each window tested as a direction |
| Kimchi (Z)-3-hexenol at day 0 | n.d. (`03:S10` Table 1) vs 10.4 (Table 3) | Table 3 (the time-course table) |
| Cucumber ethyl acetate | rises, but the glacial acetic acid added to the brine carried ethyl acetate (`03:S13` p. 2119) | not a test target |

## 10. Gaps and unverified leads not used

**None of the values in the five research files' table E was used as data in this document.** Table E holds values the researchers recalled or saw in a snippet without opening the source: 14 rows in `01`, 12 in `02`, 18 in `03`, 15 in `04`, 20 in `05` (79 leads). Two near-misses, stated so the reviewer can check: (i) cabbage dry matter is **derived** from opened numbers in `05:Friedrich22` (the arithmetic `05:E10` describes), not taken from `05:E10`'s food-table value; (ii) the 185–2 218 ppm SMCSO range is quoted inside an opened paper (`03:S1`, secondary) and serves only as a cross-check, never as the prior.

### 10.1 Leads, by what they would unlock

| theme | leads (file: subject) | would unlock | priority |
|---|---|---|---|
| Thresholds for dropped or weak compounds | `01`: Marcinkowska & Jeleń 2020 full text (AITC, 3-butenyl ITC); van Gemert 2011 / garlic literature (diallyl and allyl methyl disulfide); Buttery 1976 (allyl cyanide); daikon literature (4-MTB-ITC); orthonasal S-methyl thioacetate; Guth 1997 (2,3-butanediol); ginger AEDA (zingiberene); Blank & Fay 1996 (HEMF, furaneol, norfuraneol). `04`: Huber 1992 (HEMF) | 5 dropped and 2 conc-only compounds; AITC's class threshold → measured; 3-butenyl ITC into series sums | high |
| Threshold conflicts | `01`: Flath 1967 / Takeoka 1996 (ethyl acetate); the Munich paper behind LSB's decanoic 3.5; Kobayashi 1989 (sotolon); Buttery 1971 / Sellami 2018 (β-ionone); Salo 1970 medium (ethyl lactate); primaries of LSB basic-table values (ethyl decanoate, 3-octanone, 3-octanol, 4-vinylphenol, 2,5-dimethylpyrazine, isobutyl acetate) | narrower priors for § 9.1 | medium |
| Absolute data behind semi or direction-only cells | `02`: Czerny & Schieberle 2002 and Kirchhoff & Schieberle 2002 tables (flour and sourdough, SIDA); Tran 2022 supplement (kombucha by consortium and day); Baena-Ruano 2010, Morales 2001, Chen 2025 and Román-Camacho 2024 supplements, Callejón 2008 (vinegar). `03`: Güzel-Seydim 2000 JFCA (kefir fermentation in hours); Beshkova 2003 and Lu 2026 full texts; Cogan 1975 and Drinan 1976 figures (wild-type citrate kinetics); Ciska 2021, Peñas 2012, Palani 2016 (sauerkraut ITC time courses); Kang 2003 (kimchi sulfides); Satora 2021; Mei 2023 (suancai). `04`: Sugawara 1994; Kumazawa 2013, Inoue 2016, Ohata 2009 (miso); Udomsil 2011, Wang 2020, Giri 2010, Yoshikawa 2010, Fu 2026 (fish sauce). `02`/`05`: Feng 2013 and Kataoka 2020 full text (rice-koji 1-octen-3-ol) | flour P0 for the 11 sourdough † cells; magnitudes for vinegar, koji and garum; wild-type cheese targets instead of an ALDC⁻ upper bound | high (sourdough SIDA, kefir hours, kraut ITC) |
| Template rate constants | `05`: E1 dilute-aqueous esterification K; E2 ethyl lactate formation; E3 α-acetolactate decarboxylation vs T, pH, ethanol; E4 diacetyl reduction (brewing models); E9 AITC half-life; E11 myrosinase kinetics, Fe²⁺ and nitriles; E12 SMCSO → sulfide yields; E13 allicin → diallyl disulfide; E18 Strecker Arrhenius, HEMF yield of *Z. rouxii*; E19 open-vessel mass transfer; E20 gas–liquid partition in must. `02`: Vermeulen 2007 (LAB reduction of nonenal and decadienal) | replace the est. rates in T4, T5, T6, T7, T8, T11, T12 | high for E3/E4 (cheese, kefir) and E19 (every open vessel) |
| Yields of the model's other yeasts | `05`: E8 (*K. humilis*, *Z. rouxii*, *Brettanomyces*); E6 (wine MCFA); E7 (wine 2-phenylethanol, ethyl acetate) | the non-*Saccharomyces* multiplier (×/÷ 3) and the MCFA yield (two decades) | high |
| Precursor priors | `05`: E10 (cabbage dry matter), E14 (dough hexanal), E16 (tea glycoside release), E17 (soybean HCA, 4-vinylguaiacol yields); `02`: rice 2-acetyl-1-pyrroline; `03`: milk citrate handbook value, Gouda DM conversion; `04`: TMAO reducers, garum TVB-N, fish-sauce pyrazines, (Z)-4-heptenal and sotolon | † cells in miso, koji, sourdough; TMA | medium |

### 10.2 Gaps found during this synthesis (not in any table E)

- **No temperature** for the cucumber time course (`03:S13`) and the Sendai miso series (`04:M2`); the tests use profile defaults.
- **Organism mismatches:** kombucha sources ferment with *Brettanomyces/Zygosaccharomyces* (model: *S. cerevisiae*); kefir sources credit *S. cerevisiae*, *Leuconostoc*, *Acetobacter* and *Lb. bulgaricus* (model: *K. marxianus* and three LAB); the default cheese *Lc. lactis* has an unknown citrate-positive share.
- **No absolute acetification time course** and no base-wine 2,3-butanediol value (vinegar acetoin rests on an est. base).
- **No cucumber bound-linalool pool** (test 24 deferred); **no fish-lipid or soy-lipid pool** (garum and miso lipid aldehydes use est. zero-order sources).
- **Miso 1-octen-3-ol** keeps rising for a year (`04:M3`) while the model's mould does not grow in the mash: a non-growth source is missing (test 46 expected to fail).
- **Table-D key odorants** (D16) need a threshold pass before they can join: kombucha α-farnesene (`02:K1` Tables 1 and 2 disagree), α-terpineol, linalool oxides, benzaldehyde, ethyl phenylacetate, methyl acetate, ethyl propanoate, propyl acetate, dodecanoic acid; vinegar ethyl propanoate, propanoic acid, 1,1-diethoxyethane, ethyl 3-methylbutanoate, ethyl phenylacetate, acetoin acetate, hydroxyacetone, guaiacol, vanillin; sourdough (E,E)-2,4-decadienal, vanillin, 1-hexanol, (E)-2-hexenal, isoamyl lactate, γ-decalactone; koji 3-octen-2-one, 2-methyl-3-buten-2-ol, 2-undecanone, 1-heptanol; sauerkraut MMTSO₂, MMTSO, hydrogen sulfide, carbon disulfide; kimchi dimethyl tetrasulfide, allyl methyl trisulfide, methyl (methylthio)methyl disulfide, diallyl trisulfide, 3-phenylpropanenitrile, 2-phenylethyl ITC, (E,Z)-2,6-nonadienal, (E,E)-2,4-decadienal; cucumber (E,Z)-2,6-nonadienal, (E)-2-heptenal, octanal; kefir γ-dodecalactone, 2-undecanone, acetone, 2-butanone, 2,3-hexanedione; cheese pentanoic and phenylacetic acid, γ-dodecalactone; miso 2-furanmethanethiol, (Z)-1,5-octadien-3-one, trans-4,5-epoxy-(E)-2-decenal, syringol, ethyl phenylacetate; garum 2-ethylpyridine, indole, (E,E)-2,4-heptadienal, benzaldehyde, 2-ethylfuran, ethyl heptanoate, 1-heptanol, octanal, decanal.

## 11. Implications for the increment-B plan

### 11.1 What to build

| piece | content | notes |
|---|---|---|
| `engine.make_rhs(p, max_evals, diagnostics=None)` | when a dict is passed, write per-organism growth μⱼXⱼ, substrate flux vⱼ (hexose-equivalent g/kg/h) and the CO₂ flux | D17: not on the branch yet. Default path byte-identical; no-regression test first |
| `derived.py` aroma pass | diagnostic pass on the output grid from `simulate(keep_states=True)`; exponential integrator per interval for ~77 tracers plus the internal states of D15 (citrate, α-acetolactate, sinigrin, gluconapin, SMCSO, burst/fermentation sulfide pools, bound terpenes, ferulic acid, HEMF precursor, lactone precursor); OAV with D5's neutral fraction and the shared matrix factor; series sums under the § 1 rule; P(noticeable) | `evaluate()` today receives only pools and pH: it also needs biomass per organism, temperature, the diagnostic drivers, ingredient names and the vessel class |
| aroma parameters | seeded N(0, I) columns drawn after inference (spec § 1 decision), one per Prior in § 3 and § 5 | nothing observes them: prior = posterior |
| `compounds.py` | 85 compound records (§ 3: IDs, descriptor, series, threshold Prior, basis, pKa, template, status, sources); template class parameters (§ 5) as `Prior`s; ingredient precursor map (§ 6); evidence cells (§ 4: tier, anchor, sources per type) | data only, as `organisms.py` |
| `profiles.py` | per-type precursor priors and initial pools (§ 6); kombucha tea dose; vinegar base pools; vessel class (open surface / closed jar / dough) for T12 | — |
| schema and API | spec § 8 plus, per compound: `threshold_basis` (`measured`/`class`/`est.`/`none`), `anchor`, `ph_corrected`, `in_series_sum`; `not_modelled_aroma.ingredients` filled from † cells | small extension of spec § 8 |
| tests | § 7 (51 run + 1 recorded) and the spec § 9 additions at the end of § 7 | one parametrised file per type |

### 11.2 Order

Templates by data quality, highest-evidence ferments first; each step ends with its § 7 tests green.

1. **Infrastructure:** diagnostics hook; tracer integrator against analytic and `solve_ivp` solutions; OAV with D5 and the matrix factor; **T12** volatility (measured Henry constants, `05:Sander23`), since every compound needs it.
2. **T1 Ehrlich, T2 esters, T3 acetaldehyde, T5 chemistry, T9 terpenes → kombucha** (tests 1–10: 3 absolute windows, 19 calibrated cells) **and kefir** (tests 26–33: 2 absolute windows, 22 calibrated cells). Measured yields (`05:Godillot23`, `05:Rollero17`, `05:RameyOugh80`).
3. **T4 citrate chain → cheese** (34–37) and kefir's C4 cells; this is where the α-acetolactate state first matters.
4. **T11 HEMF and furanones → miso** (38–47): the best absolute time course in the whole review (`04:M9`) and a derived loss Q10.
5. **T6 glucosinolates, T7 sulfur, T8 vegetable LOX → lacto-ferment** (19–25): semi shapes plus absolute sauerkraut end points.
6. **T8 flour aldehydes and LAB/yeast reduction, T10 → sourdough** (14–15), including the bake-phase carry-over of tracers (spec § 1).
7. **AAB sink and the vinegar base → vinegar** (11–13).
8. **Mould C8 and methyl ketones → koji** (16–18).
9. **Garum** (48–51).
10. **UI** (§ 11.4), palette checks, screenshots, then the review gates of spec § 9.

### 11.3 What stays exploratory

- Koji, miso and garum aroma (exploratory types); vinegar aroma (directions only on an est. base).
- Every est.-only parameter: T7 rates, T8 outside kimchi and cucumber, T10, T11 apart from HEMF and furaneol, the open-surface k_surf, the non-*Saccharomyces* multiplier, the MCFA yield. The curation tests pin shapes for these, nothing more.
- Inactive compounds (no producer) and † cells (no precursor): visible only in `not_modelled_aroma`.
- `sensory.validated` stays `false` (spec § 9): no sensory data validates aroma until sub-project 6.

### 11.4 UI notes (spec § 6 aroma strip)

- **Headline strip** rows = aromatic series with at least one compound passing the § 1 sum rule for this batch: calibrated cells, plus reported cells with an `abs` or `semi` anchor, with a `measured` or `class` threshold, and not †. Bar height = P(series sum > 1), shade = median sum in the four ×-threshold bins.
- **Drill-down** shows, in addition: reported (presence) compounds with a "reported" badge; 3-butenyl ITC with "threshold estimated"; AITC with "threshold from a class range"; allyl cyanide and 2,3-butanediol as concentrations with "no odour threshold known"; plausible compounds dashed behind "Show plausible compounds (n)".
- **pH-corrected compounds** (acids, trimethylamine) carry one line on their card: "odour activity at this batch's pH: only the un-ionised form is volatile".
- **Calibrated-from-shape** cells: the card says the timing follows a published time course while the amount is a model estimate.
- **Not modelled for aroma** note lists *Brettanomyces*/*Candida* yeasts, TMAO-reducing bacteria, and the logged ingredients whose precursors are not curated (tea and soy phenolic acids, flour sotolon and aldehydes, rice 2-acetyl-1-pyrroline, spices).
- The **matrix factor** is drawn once per member, so series bands do not narrow artificially when compounds are summed.
- Wording rules of spec § 7 are unchanged ("may be noticeable", never "smells like").
