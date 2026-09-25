# Biochemistry v4 — the pathway enzymes the fermentation forecast relies on — curation record

**Date:** 2026-09-25
**Status:** implemented (snapshot `kegg_biochem_v4.json.gz`, migration 0013)
**Builds on:** `2026-09-23-fermentation-biochemistry-design.md` (data model, frozen-snapshot pattern), `2026-09-24-biochemistry-v2-curation-draft.md` (curation conventions), `2026-09-24-fermentation-prediction-design.md` § 8.2 (the gaps this closes).

## Why

The forecast (`src/fermenttrack/prediction/`) reports, for each organism pathway it models, whether a marker enzyme is linked to that organism in the KEGG reference graph (`organisms[].pathways[].in_reference_graph`). With v3, about 20 pathway rows had no backing because six pathway enzymes were missing and a few existing enzymes lacked organism links. v4 adds them.

## Method

- Enzyme names, compound ids and canonical names come from the KEGG REST API at build time (`scripts/build_kegg_biochem.py`), as for v1–v3.
- **New rule for v4:** every organism–enzyme link has a KEGG gene annotation in that organism's KEGG genome (`https://rest.kegg.jp/link/<org>/ec:<EC>`, checked 2026-09-25). KEGG annotates more than listed: only links the fermentation uses are curated (typical, not exhaustive).
- KEGG genomes used: *S. cerevisiae* S288c `sce`, *A. oryzae* RIB40 `aor`, *L. lactis* Il1403 `lla` (plus dairy SK11 `llc`, KLDS 4.0325 `lld`), *T. halophilus* NBRC 12172 `thl`, *L. plantarum* WCFS1 `lpl`, *K. xylinus* E25 `gxl`, *F. sanfranciscensis* TMW 1.1304 `lsn`, *Leuconostoc mesenteroides* ATCC 8293 `lme`, *K. marxianus* DMKU3-1042 `kmx`, *Z. rouxii* CBS 732 `zro`, *A. pasteurianus* IFO 3283-01 `apt`, *A. aceti* TMW2.1153 `aace`, *L. kefiranofaciens* ZW3 `lke`, *Lentilactobacillus kefiri* DH5 `lkf`.

## The six missing enzymes (plus one)

| EC | KEGG name | Role in the forecast | Linked organisms (KEGG genes) | Reaction rows |
|---|---|---|---|---|
| 3.2.1.26 | beta-fructofuranosidase (invertase) | sucrose split in kombucha and sourdough; LAB sucrose use | *S. cerevisiae* (YIL162W, SUC2), *L. plantarum* (lp_0187), *Leuconostoc mesenteroides* (LEUM_0289), *T. halophilus* (TEH_02990, TEH_12010) | Sucrose → D-Glucose, Sucrose → D-Fructose |
| 4.1.2.9 | phosphoketolase | the defining step of heterolactic fermentation | *Leuconostoc mesenteroides* (LEUM_1456, _1961), *L. sanfranciscensis* (LSA_02300), *L. kefiri* (DNL43_06655, _07335) | D-Xylulose 5-phosphate → Acetyl phosphate |
| 1.1.5.2 | glucose 1-dehydrogenase (PQQ, quinone) | gluconic acid in kombucha | *K. xylinus* (H845_1711), *A. aceti* (A0U92_03340, _05765, _16715), *A. pasteurianus* (APA01_06330, _14620) | D-Glucose → D-Glucono-1,5-lactone |
| 2.4.1.8 | maltose phosphorylase | sourdough LAB maltose use | *L. sanfranciscensis* (LSA_01510), *L. plantarum* (lp_0181, lp_1730), *T. halophilus* (TEH_01510) | Maltose → D-Glucose, Maltose → beta-D-Glucose 1-phosphate |
| 3.2.1.85 | 6-phospho-beta-galactosidase | lactose use by dairy lactococci (PTS) | *L. lactis* — plasmid-borne in dairy strains: present in SK11 (LACR_D39) and KLDS 4.0325 (P620_14810), absent from plasmid-free Il1403 and MG1363 | Lactose 6'-phosphate → D-Galactose 6-phosphate |
| 2.4.1.12 | cellulose synthase (UDP-forming) | the SCOBY pellicle | *K. xylinus* (H845_2022, _2352, _451) | UDP-glucose → Cellulose |
| 3.2.1.10 | oligo-1,6-glucosidase | yeast maltose use: KEGG files the maltase MAL32 (YBR299W, orthology K01182) under this EC | *S. cerevisiae* (YBR299W and 6 paralogues) | none: the EC's reference reaction is isomaltose hydrolysis, not the maltose split MAL32 performs |

**Deliberately not linked:** phosphoketolase on *L. plantarum*, *L. lactis*, *T. halophilus*, *A. oryzae*, *K. xylinus* and *L. kefiranofaciens* — KEGG annotates it, but there it serves pentose use, not hexose fermentation; linking it would misreport them as heterofermentative.

## New links on existing enzymes

| EC | Organism | KEGG genes |
|---|---|---|
| 1.1.1.27 L-lactate dehydrogenase | *L. kefiranofaciens* | WANG_0270, _0755, _1884 |
| 3.2.1.23 beta-galactosidase | *L. kefiranofaciens*, *L. kefiri* | WANG_0292–0296; DNL43_02260, _02265 |
| 1.1.5.5 alcohol dehydrogenase (quinone) | *K. xylinus* | H845_603, _604, _1126 |
| 1.2.1.3 aldehyde dehydrogenase (NAD+) | *K. xylinus* | H845_1157 |

## Result

- Snapshot v4: 14 organisms (unchanged), 23 enzymes (+7), 23 compounds (+10), 21 new organism–enzyme links, 8 new reactions. Strictly additive over v3 (`snapshot_delta` refuses otherwise).
- Migration 0013 inserts exactly that delta (idempotent; downgrade removes only rows it added, by natural key and the `kegg_biochem_v4` tag). No organisms or fermentation-type defaults change; batch overrides are untouched.
- Forecast provenance: every modelled pathway is now backed by the graph except *Z. rouxii*'s maltose step (KEGG annotates no maltase in `zro`).

## How to add more (for the next curator)

1. Check the enzyme and each organism in KEGG: `https://rest.kegg.jp/get/ec:<EC>` and `https://rest.kegg.jp/link/<org>/ec:<EC>` (organism codes via `https://rest.kegg.jp/find/genome/<name>`).
2. Edit the curated dicts in `src/fermenttrack/biochem.py` (`ENZYME_ORGANISMS`, `COMPOUNDS`, `ENZYME_REACTIONS`), bump `SCHEMA_VERSION` and the snapshot path to the next version.
3. `python scripts/build_kegg_biochem.py` writes the new frozen snapshot; add a migration applying `snapshot_delta(previous, new)` (0013 is the template) and a round-trip test.
