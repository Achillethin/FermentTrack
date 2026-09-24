# Biochemistry v2 — Curation Record

**Date:** 2026-09-24
**Status:** FINAL — implemented (v2). Snapshot `kegg_biochem_v2.json.gz` + migration 0009.
**Scope (your call, 2026-09-24):** option A only — curation gaps in koji, miso, plus the adjacent low-risk kefir/vinegar/CO2 gaps. Garum's ingredient-driven enzymes (fish digestive proteases; option B, the ingredient→enzyme table) are still out of scope, but garum's biochemistry is no longer empty because *T. halophilus* gained lactate dehydrogenase. Cheese protease/rennet is also out for the same reason.
**Builds on:** `2026-09-23-fermentation-biochemistry-design.md`; v1 data in `src/fermenttrack/biochem.py`.

## How v2 shipped (structural, no app-code or API change)

- New frozen snapshot `kegg_biochem_v2.json.gz` = all of v1 **plus** the additions below. v1 stays frozen (migration 0008 still loads it).
- Migration **0009 is additive by natural key** (organism name, EC number, KEGG compound id): existing rows keep their UUIDs, so any `batch_organisms` override rows stay valid. New rows are tagged `source_version = "kegg_biochem_v2"`. Downgrade deletes exactly the rows in `v2 − v1` (computed from the two frozen files), including new links between two v1 rows, and any `batch_organisms` rows pointing at v2 organisms (they would dangle).
- One code change: `ENZYME_REACTIONS` allowed one reaction per enzyme; it is now `list[tuple[substrate, product]]` per enzyme (needed for CO2 and lactose below). The snapshot JSON shape is unchanged, so migration 0008 stays valid.
- Same verification as v1: exact-name match against live KEGG at build time, snapshot-sanity tests extended (v1 ⊂ v2), SQLite round-trip (`tests/test_migration_0009.py`), Postgres check after deploy.

## 1. New organisms

| Organism | Kingdom | Default for | Why | Confidence |
|---|---|---|---|---|
| *Zygosaccharomyces rouxii* | yeast | miso | Salt-tolerant yeast of miso and soy-sauce fermentations; source of ethanol and flavor esters. Missing today. | high |
| *Leuconostoc mesenteroides* | bacteria | lacto_ferment | Classic heterolactic starter of kimchi/sauerkraut; lacto_ferment had only *L. plantarum*. | high |
| *Acetobacter pasteurianus* | bacteria | vinegar | Added on research advice. | see section 8 |
| *Lactobacillus kefiri* | bacteria | kefir | Added on research advice (organism only, no enzyme links). | see section 8 |
| *Lactobacillus kefiranofaciens* | bacteria | kefir | Added on research advice (organism only, no enzyme links). | see section 8 |

Names keep the widely used pre-reclassification form, consistent with v1; no v1 organism is renamed.

## 2. New enzymes (EC numbers all verified in KEGG 2026-09-24; name = KEGG's)

| EC | KEGG name | Attach to | Evidence / caveat | Confidence |
|---|---|---|---|---|
| 3.2.1.3 | glucan 1,4-alpha-glucosidase (glucoamylase) | *A. oryzae* | Core koji saccharifying enzyme | high |
| 3.2.1.20 | alpha-glucosidase | *A. oryzae* | Maltose → glucose in koji | high |
| 3.4.21.63 | oryzin | *A. oryzae* | KEGG: "predominant extracellular alkaline endopeptidase of the mold *Aspergillus oryzae*" | high |
| 3.4.24.39 | deuterolysin | *A. oryzae* | KEGG lists *A. oryzae* explicitly (neutral protease) | high |
| 3.4.23.18 | aspergillopepsin I | *A. oryzae* | KEGG: "found in a variety of *Aspergillus* species"; *A. oryzae* acid protease (pepA) is this family | high (PEPA_ASPOR Q06902) |
| 3.5.1.2 | glutaminase | *A. oryzae* | Glutamine → glutamate, the umami step in koji/miso | high |
| 1.1.1.1 | alcohol dehydrogenase | *Z. rouxii*, *K. marxianus* (already on *S. cerevisiae*) | Yeast ethanol fermentation | high |
| 4.1.1.1 | pyruvate decarboxylase | *Z. rouxii*, *K. marxianus* | same | high |
| 1.1.1.27 | L-lactate dehydrogenase | *T. halophilus* (L only for this genus) | Lactic acid production in miso. | medium (genus-level evidence) |
| 1.1.1.28 | D-lactate dehydrogenase | *L. plantarum*, *L. sanfranciscensis*, *L. mesenteroides* | LDH correction, see section 8. | medium-high |
| 3.4.16.5 | carboxypeptidase C | *A. oryzae* | Added on research advice; linked to glutamate release. | high (UniProt Q2TYA1, reviewed) |
| 3.2.1.23 | beta-galactosidase | *K. marxianus* | Lactose-fermenting kefir yeast. Deliberately NOT attached to *L. lactis* (it uses phospho-beta-galactosidase, EC 3.2.1.85, a different enzyme). | high |
| 1.1.5.5 | alcohol dehydrogenase (quinone) | *A. aceti*, *A. pasteurianus* | KEGG: "only described in acetic acid bacteria where it is involved in acetic acid production". This is the real ethanol→acetaldehyde step, and fixes vinegar showing no ethanol. | high |
| 1.2.5.2 | aldehyde dehydrogenase (quinone) | *A. aceti*, *A. pasteurianus* | KEGG: PQQ-dependent, the acetaldehyde→acetate route (old EC 1.2.99.3). Added **alongside** 1.2.1.3 (kept; additive migration cannot remove it). | high |

*Proteases and amylase have no reaction row: their substrates (protein, starch) are not KEGG compounds. They still show up as enzymes.*

## 3. New compounds (each resolved by exact name against live KEGG)

| Compound | KEGG id | Category | Used by |
|---|---|---|---|
| Maltose | C00208 | other | 3.2.1.20 |
| D-Glucose | C00031 | other | 3.2.1.20, 3.2.1.23 |
| L-Glutamine | C00064 | other | 3.5.1.2 |
| L-Glutamate | C00025 | other | 3.5.1.2 (umami) |
| CO2 (curated search name "Carbon dioxide"; KEGG's canonical name is "CO2") | C00011 | gas | 4.1.1.1. Carbonation matters for kombucha bottling safety. |
| Lactose | C00243 | other | 3.2.1.23 |
| D-Galactose | C00124 | other | 3.2.1.23 |
| D-Lactic acid (KEGG canonical "(R)-Lactate"; "D-Lactic acid" is an exact KEGG synonym) | C00256 | acid | 1.1.1.28 |

Categories reuse v1's set (`acid|alcohol|gas|flavor|other`). `flavor` stays unused in v2 (no aroma compounds yet).

## 4. New reactions (enzyme: substrate → product)

- 3.5.1.2: L-Glutamine → L-Glutamate
- 3.2.1.20: Maltose → D-Glucose
- 4.1.1.1: Pyruvate → CO2 *(second row; existing Pyruvate → Acetaldehyde stays)*
- 1.1.5.5: Ethanol → Acetaldehyde
- 1.2.5.2: Acetaldehyde → Acetate
- 1.1.1.28: Pyruvate → D-Lactate
- 3.2.1.23: Lactose → D-Glucose, and Lactose → D-Galactose

## 5. Resulting mapping changes (fermentation type → organisms)

- miso: + *Z. rouxii* (so [*A. oryzae*, *T. halophilus*, *Z. rouxii*])
- lacto_ferment: + *L. mesenteroides*
- vinegar: + *A. pasteurianus*
- kefir: + *L. kefiri*, *L. kefiranofaciens*
- all other types unchanged (kombucha, sourdough, koji, cheese, garum change only through the new enzymes/compounds above, if at all).

## 6. Expected `/biochemistry` output after v2 (for sanity-checking the list)

| Type | Enzymes | Compounds |
|---|---|---|
| kombucha | alcohol dehydrogenase, pyruvate decarboxylase, alcohol dehydrogenase (quinone), aldehyde dehydrogenase (NAD+), aldehyde dehydrogenase (quinone) | Ethanol, Acetaldehyde, Pyruvate, Acetate, CO2 |
| sourdough | alcohol dehydrogenase, pyruvate decarboxylase, L-lactate dehydrogenase, D-lactate dehydrogenase | Ethanol, Acetaldehyde, Pyruvate, (S)-Lactate, CO2, (R)-Lactate |
| koji | alpha-amylase, glucan 1,4-alpha-glucosidase, alpha-glucosidase, oryzin, deuterolysin, aspergillopepsin I, carboxypeptidase C, glutaminase | Maltose, D-Glucose, L-Glutamine, L-Glutamate |
| cheese | L-lactate dehydrogenase | Pyruvate, (S)-Lactate |
| kefir | alcohol dehydrogenase, pyruvate decarboxylase, L-lactate dehydrogenase, beta-galactosidase | Ethanol, Acetaldehyde, Pyruvate, (S)-Lactate, D-Glucose, CO2, Lactose, D-Galactose |
| miso | alcohol dehydrogenase, pyruvate decarboxylase, L-lactate dehydrogenase, alpha-amylase, glucan 1,4-alpha-glucosidase, alpha-glucosidase, oryzin, deuterolysin, aspergillopepsin I, carboxypeptidase C, glutaminase | Ethanol, Acetaldehyde, Pyruvate, (S)-Lactate, Maltose, D-Glucose, L-Glutamine, L-Glutamate, CO2 |
| garum | L-lactate dehydrogenase | Pyruvate, (S)-Lactate |
| vinegar | alcohol dehydrogenase (quinone), aldehyde dehydrogenase (NAD+), aldehyde dehydrogenase (quinone) | Ethanol, Acetaldehyde, Acetate |
| lacto_ferment | L-lactate dehydrogenase, D-lactate dehydrogenase | Pyruvate, (S)-Lactate, (R)-Lactate |

## 7. Explicitly not in v2

- Garum (all of it) and cheese protease/chymosin: need the ingredient→enzyme table (option B).
- Starch, protein and peptides as compounds (not KEGG compounds); aroma/flavor compounds (esters, pyrazines); *A. oryzae* lipases/cellulases/phytase; *T. halophilus* enzymes beyond LDH; NCBI taxon ids.

## 8. Research verification (2026-09-24)

1. **LDH correction.** v1 attached only the L-lactate dehydrogenase (1.1.1.27) to *L. plantarum* and *L. sanfranciscensis*; that was incomplete: both also carry D-LDH. *Leuconostoc mesenteroides* is D-only, *T. halophilus* L-only, *L. lactis* L-only. Fixed in v2 via EC 1.1.1.28 and D-lactate (C00256): 1.1.1.28 is linked to *L. plantarum*, *L. sanfranciscensis* and *L. mesenteroides*; 1.1.1.27 gains *T. halophilus*; *L. lactis* stays L-only.
2. **Confirmed by UniProt/KEGG.** All six *A. oryzae* enzymes (aspergillopepsin I = PEPA_ASPOR Q06902; oryzin P12547; deuterolysin P46076; glutaminase Q2U4L7; glucoamylase P36914; alpha-glucosidase Q12558); 1.1.5.5 (P18278 adhA, *A. aceti*); *Z. rouxii* ADH/PDC (KEGG zro genes); *K. marxianus* reviewed ADH/PDC.
3. **Added on research advice.** Carboxypeptidase C 3.4.16.5 for *A. oryzae* (UniProt Q2TYA1, reviewed; linked to glutamate release); *A. pasteurianus* for vinegar; *Lactobacillus kefiri* and *L. kefiranofaciens* for kefir (organisms only, no enzyme links: LDH not checked).
4. **Deliberately not done.**
   - Kombucha mapping unchanged: evidence that *Komagataeibacter*/*Brettanomyces* are more typical than *A. aceti*/*S. cerevisiae* is only medium-confidence; revisit in v3.
   - No organism renames: pre-reclassification names kept for consistency. Current names: *Lactiplantibacillus plantarum*, *Fructilactobacillus sanfranciscensis*, *Komagataeibacter xylinus*, *Lentilactobacillus kefiri*.
   - Leucine aminopeptidase skipped: KEGG EC unverified for *A. oryzae* LapA.
   - 1.2.1.3 on *Acetobacter* kept but low weight: it is a cytoplasmic NAD+ ALDH; the PQQ route 1.2.5.2 is the main one.
5. **Still open, needs a domain expert.** *T. halophilus* L-only rests on genus-level evidence and unreviewed annotations; *F. sanfranciscensis* DL rests on unreviewed entries and a 1984 species description; *L. mesenteroides* "predominantly D" (genome has 3 D-LDH and 1 L-LDH).

## 9. As shipped

`kegg_biochem_v2.json.gz` holds 14 organisms, 16 enzymes, 13 compounds, 27 organism-enzyme links, 12 enzyme reactions and 19 fermentation-type defaults; the delta over v1 is 5 organisms, 11 enzymes, 8 compounds, 20 organism-enzyme links, 8 reactions and 5 fermentation-type defaults. All new enzyme names and compound ids resolved against live KEGG by exact name at build time (the search name "D-Lactic acid" matched C00256 directly). Migration 0009 applies and reverses on SQLite (`tests/test_migration_0009.py`, plus a manual upgrade head / downgrade 0007 / upgrade head round trip); Postgres is still to be checked after deploy.

