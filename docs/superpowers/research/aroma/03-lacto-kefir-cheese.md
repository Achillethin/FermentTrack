# Aroma evidence — lacto-ferments, kefir, fresh cheese (research slice 03)

Scope: tables B (evidence per ferment) and D (missing key odorants) for LAB ferments of vegetables (sauerkraut, kimchi/radish, brined pickles) and milk (kefir; cheese curd/acidification stage and fresh cheeses). Table E (unverified leads) and Sources at the end. Rules of `BRIEF.md` apply: every number below comes from a source opened during this session (full text or abstract); "abstract only" is stated where the full text was not reachable. Relative peak areas are reported as presence only.

Status: done (2026-10-05). Ready for the curation pass.

Tier counts (table rows; one row can cover 2–3 compounds; engine pools excluded):

| ferment | B calibrated | B reported | B plausible | B drop | D rows |
|---|---|---|---|---|---|
| sauerkraut | 0 | 12 | 5 | 1 (4-methylthio-3-butenyl ITC) | 4 reported |
| kimchi cabbage | 11 (one semi-quantitative time course, [S10]) | 5 | 4 | 0 | 5 calibrated, 4 reported |
| radish | 0 | 1 (qualitative) | 1 | 0 | — |
| cucumber pickle | 4 ([S13]) | 4 | 0 | 0 | 1 calibrated, 1 reported |
| kefir | 17 = 2 true concentrations (acetaldehyde, acetoin; storage) + 9 semi-quantitative ([S23]) + 6 direction-only areas ([S21]) | 6 | 1 | 0 | 2 calibrated, 2 reported |
| cheese curd | 2 (diacetyl, acetoin; ALDC⁻ strain = upper bound) | 11 | 4 | 0 | 3 reported (+ α-acetolactate state variable) |

Biggest gaps: no concentration time course for any glucosinolate product or sulfide in **sauerkraut** (white cabbage) — only end points; no fresh-cheese (quark/cottage) time course; no garlic/ginger/dill add-in quantitation; no MTBITC numbers for radish; no dimethyl sulfide data for milk ferments.

## 1. Sauerkraut (white cabbage, *Brassica oleracea* var. *capitata*)

Conventions: "µg/kg" ≈ ppb as printed in the source. "brine" = value measured in sauerkraut brine/juice, not in the solid. "presence (area)" = only relative peak areas were reported; no concentration is implied. Source keys [Sx] → Sources list.

Precursor kinetics that apply to all glucosinolate (GLS) products below (for `r_i` of the GLS → product chain):
- GLS "degraded dramatically between Day 2 and 5 of fermentation and by Day 7 there was no detectable amount of glucosinolates left" (20 °C fermentation, then 4 °C storage) — [S5] abstract.
- Raw cabbage total GLS 3.71 µmol/g DW; "totally decomposed in both fermentations during two weeks"; ITCs and allyl cyanide the predominant breakdown products (starter vs spontaneous) — [S4] abstract.
- Cabbage fermented 7 d at 25 °C (0.5 or 1.5 % NaCl, spontaneous, *L. plantarum* or *Leuc. mesenteroides*) contained "only traces of some GLS"; dominant GLS in raw cabbage: glucoiberin, sinigrin, glucobrassicin — [S17] abstract.
- Yield: relative contents of degradation products, as % of native GLS: >70–96 % for glucoraphanin products, **< 5 % for sinigrin products** (i.e. AITC + allyl cyanide recovered from sinigrin); ITCs and cyanides each "did not exceed 2.5 µM" (units as printed in the abstract) — [S6] abstract.
- S-methyl-L-cysteine sulfoxide (SMCSO, precursor of methanethiol → DMDS/DMTS/MMTSO/MMTSO₂) in cabbage: 185–2218 ppm FW, as reviewed in the introduction of [S1] (secondary; primary refs Morris & Thompson 1956, Synge & Wood 1956, Bradshaw & Borzucki 1982, Marks et al. 1992 not opened).

### Table B — sauerkraut

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions (T, organisms, matrix) | source (where) |
|---|---|---|---|---|---|---|---|---|
| sauerkraut | allyl isothiocyanate | reported | no (precursor GLS depletion d 2–5 at 20 °C, see above) | 54.6 (commercial canned) – 85.2 (LA81) µg/kg brine; 78.6 (LA10); non-fermented sulfite/pH 3.5 control 352.1; up to **9 800 µg/kg FW** (980 µg/100 g FW) with *L. sakei* starter, "2–3 ×" the other starters' total GLS products | AITC correlated with *raw-cabbage* flavour (r² = 0.919), not with kraut sulfur note | plant myrosinase on sinigrin (released by shredding); low yield (< 5 % of sinigrin, [S6]); declines in fermented vs acidified-only cabbage | 18 °C, 9 months, 2 % NaCl dry-salted, *Leuc. mesenteroides* LA81/LA10 at 10⁶ CFU/g; brine extract, GC-MS SIM, standard additions [S1]. [S3]: starters *L. plantarum*, *L. sakei*, *Leuc. mesenteroides*, *P. pentosaceus*, *Lc. lactis* | [S1] Table 5 + p. S347; [S3] abstract; presence: [S2] Fig. 2/Table 3, [S8] Table 2 (area), [S7] abstract |
| sauerkraut | allyl cyanide | reported | no | no concentration opened | — | sinigrin → nitrile branch (epithiospecifier / low pH, Fe²⁺; mechanism not quantified in opened sources) | [S4]: starter vs spontaneous, 2 weeks; [S7]: cv. Bronco/Megaton, 0.5 / 1.5 % NaCl, natural, *L. plantarum*, *Leuc. mesenteroides*, mixed; absent in raw cabbage and in 4 commercial krauts | [S4] abstract ("predominant breakdown products" with ITCs); [S7] abstract |
| sauerkraut | 3-butenyl isothiocyanate | reported (presence) | no | presence (area) in 2 traditional + 3 commercial krauts | — | myrosinase on gluconapin | spontaneous, 18 °C, cv. Brgujski/Žminjski, stored 52 d at 4 or 18 °C; HS-SPME areas | [S8] Table 2 ("4-isothiocyanatobut-1-ene") |
| sauerkraut | 4-methylthio-3-butenyl isothiocyanate | drop (for cabbage) | — | — | — | precursor glucoraphasatin is a radish GLS; not among the dominant cabbage GLS (sinigrin, glucoiberin, glucobrassicin) in [S3], [S17] | — | [S3], [S17] abstracts (GLS lists) |
| sauerkraut | methanethiol | reported (presence) | no | presence (headspace FPD area; 8 US brands) | — | C-S lyase on SMCSO; LAB amino-acid catabolism suggested | canned commercial kraut, 1.4–2.0 % salt, juice headspace at 90 °C injection | [S2] Fig. 2, Table 3; [S9] (presence, loading plot) |
| sauerkraut | dimethyl sulfide | reported (presence) | no | presence (headspace area) | — | SMCSO / methionine | as above; [S9]: DMS and DMDS "most dominant sulfur compounds", 18–20 °C, 30 d, Weissella-dominated household ferments | [S2] Fig. 2; [S9] Discussion |
| sauerkraut | dimethyl disulfide | reported | no | 30.3 (commercial) – 77.9 µg/kg brine (LA10 > LA81 51.2, P < 0.05); acidified non-fermented 2.3 | no correlation with kraut-sulfur score (r² = 0.374) | methanethiol oxidation; C-S lyase products; fermentation raises it vs acidified control | as for AITC row [S1] | [S1] Table 5, Fig. 1; presence [S2], [S8] |
| sauerkraut | dimethyl trisulfide | reported | no | 21.7–30.6 µg/kg brine; acidified non-fermented 0.5 | **kraut sulfur flavour correlated linearly with DMTS (P ≤ 0.01)** | as DMDS | [S1] | [S1] Table 5, Fig. 8a; presence [S2], [S8] |
| sauerkraut | S-methyl thioacetate | reported (presence) | no | presence (purge-and-trap GC-MS, "ethane thiotic-S-methyl ester") | — | methanethiol + acetyl-CoA (mechanism not in source) | commercial canned kraut | [S2] Table 3 |
| sauerkraut | acetaldehyde | reported (presence) | no | presence (headspace FID) | — | heterofermentative LAB / yeasts | commercial canned kraut | [S2] Fig. 1, Table 3 |
| sauerkraut | ethyl acetate | reported (presence) | no | presence (headspace; GC-MS); area data [S8] | — | yeast/LAB esterase + chemical (ethanol + acetic) | [S2] commercial; [S8] spontaneous 18 °C | [S2] Table 3; [S8] Table 2; [S9] ("dominant esters" ethyl acetate and ethyl lactate, citing Wu 2015) |
| sauerkraut | ethyl lactate | reported (presence) | no | presence (area; highest in household #3) | — | chemical / enzymatic esterification ethanol + lactic | 18–20 °C, 30 d, Chinese NE sauerkraut | [S9] Results (loading plot) |
| sauerkraut | diacetyl | plausible | — | none opened for sauerkraut | — | *Leuc. mesenteroides* / *Lc. lactis* citrate & pyruvate overflow (cabbage citrate low) | — | (see kimchi row: GC-O presence in salted cabbage [S10]) |
| sauerkraut | acetoin | plausible (lead in E) | — | none opened (abstract of [S14] mentions "acetoin derivatives" without values) | — | as diacetyl | — | [S14] abstract |
| sauerkraut | 2,3-butanediol | plausible | — | none opened | — | — | — | — |
| sauerkraut | hexanal | reported (presence) | no | presence (area) | — | LOX on linoleic acid at shredding | [S9] household #1 highest | [S9] Results |
| sauerkraut | (Z)-3-hexenal / (Z)-3-hexenol | plausible | — | not reported in opened sauerkraut sources ((E)-3-hexenyl acetate and 1-hexanol present by area [S8]) | — | LOX/HPL at shredding; salting inactivates LOX (see kimchi) | — | [S8] Table 2 |
| sauerkraut | carvone | plausible (only with caraway/dill) | — | — | caraway-spiced kraut had no DMTS and lower DMDS (25 vs 63 ppb) — secondary, see E | spice terpenoid, add-in | — | [S1] p. S348 citing Chin & Lindsay 1994b (secondary) |
| sauerkraut | acetic acid (engine pool) | (engine) | — | 31–83 mM (mean 46) commercial; 37.6–66.0 mM after 9 mo | — | heterofermentative LAB | [S2] 8 US brands; [S1] 18 °C 9 mo | [S2] Table 2; [S1] Table 6 |
| sauerkraut | ethanol (engine pool) | (engine) | — | 15–82 mM (mean 41) | — | heterofermentative LAB, yeasts | [S2] | [S2] Table 2 |

### Table D — sauerkraut (key odorants not on the candidate list)

| ferment | compound key | tier proposed | time course? | end-point range µg/kg | key-odorant data | producer / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| sauerkraut | methyl methanethiosulfonate (MMTSO₂) | reported | no | 0–1.6 µg/kg brine (commercial 1.6 highest) | kraut sulfur flavour correlated linearly with MMTSO₂ (P ≤ 0.01); all values below the 5 ppm threshold reported by Chin & Lindsay 1994a (secondary) | C-S lyase on SMCSO → MMTSO → MMTSO₂ | [S1] | [S1] Table 5, Fig. 8b, p. S349 |
| sauerkraut | S-methyl methanethiosulfinate (MMTSO) | reported (transient) | no (max 24 h after juice preparation, Kyung & Fleming 1994 — secondary) | 0 (fermented) – 1.5 (acidified) µg/kg brine; 1.3 commercial | threshold 550 ppb (Chin & Lindsay 1994a, secondary) | C-S lyase product, unstable | [S1] | [S1] Table 5, p. S349 |
| sauerkraut | hydrogen sulfide | reported (presence) | no | presence (headspace area) | — | cysteine / sulfate reduction | commercial canned | [S2] Fig. 2 |
| sauerkraut | carbon disulfide | reported (presence) | no | presence (headspace area) | — | — | commercial canned | [S2] Fig. 2 |

## 2. Kimchi / radish / brined pickles

### 2a. Kimchi cabbage (*Brassica rapa* subsp. *pekinensis*) — the time-course source

[S10] is the best time course found: kimchi cabbage quartered, brined in 10 % NaCl for 20 h at 8 °C (final salinity 2.5 %), then **fermented alone (no garlic, pepper, ginger) at 15 °C for 15 d**; spontaneous LAB (organisms not identified); SAFE extraction of juice; GC-MS **semi-quantitative** (internal standard 3-heptanol, response factor assumed 1, "ppb" per kg juice — treat as ±×2–3, not true concentrations); AEDA on raw (RC) and salted (SC) cabbage. Titratable acidity 0.27–0.79 % lactic over 15 d. Note: [S10] Table 1 lists (Z)-3-hexenol as n.d. in SC but Table 3 gives 10.4 at day 0.

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| kimchi | 3-butenyl isothiocyanate | calibrated | raw n.d. → salted d0 212.0 → d3 202.0 → d5 253.0 → **d7 553.1** → d9 403.8 → d15 147.6 | 147.6 (d15) | log₃FD 2 (RC), 3 (SC); "plastic" | myrosinase on gluconapin, activated by salting (cell disruption) | [S10] conditions above | [S10] Tables 1–3 |
| kimchi | allyl isothiocyanate | plausible | — | not reported in [S10] (cabbage-only) | — | sinigrin (mustard greens / radish in full kimchi) | — | — |
| kimchi | allyl cyanide | plausible | — | — | — | — | — | — |
| kimchi | dimethyl disulfide | calibrated | raw 63.3 → salted d0 **204.6** → d3 6.7 → d5 27.2 → d7 24.4 → d9 26.4 → d15 31.2 | 31.2 | — | SMCSO → methanethiol → DMDS during salting; falls when fermentation starts | [S10] | [S10] Table 1, Table 3 |
| kimchi | dimethyl trisulfide | calibrated | raw 21.6 → salted d0 **425.4** → d3 4.3 → d5 2.3 → d7 2.8 → d9 3.6 → d15 3.2 | 2.3–3.6 (d5–15) | log₃FD 1 (RC) → **5 (SC, highest)**; "sulfury, kimchi-like"; OI ≥ 4 in full kimchi [S11] | as DMDS | [S10]; [S11] kimchi ± fish sauce (V-SDE, GC-O) | [S10] Table 1–3, Fig. 1; [S11] abstract |
| kimchi | methanethiol | plausible | — | not detected by SAFE (too volatile for the method) | — | SMCSO | — | [S10] Discussion (proposed precursor of the sulfides) |
| kimchi | allyl methyl disulfide | calibrated | raw n.d. → d0 5.7 → d3 2.1 → d5 3.2 → d7 6.5 → d9 4.9 → **d15 28.8** | 28.8 | OI ≥ 4 ("methylallyl disulfide") in garlic-containing kimchi [S11] | rises late even without garlic in [S10] | [S10]; [S11] | [S10] Table 3; [S11] abstract |
| kimchi | diallyl disulfide | reported | no | — | OI ≥ 4.0 (isomers) in kimchi with garlic | garlic alliin → allicin → DADS | [S11] | [S11] abstract |
| kimchi | diacetyl | reported | no | — | log₃FD 0 (RC) → 1 (SC); OI ≥ 3.5 in full kimchi | LAB citrate / pyruvate | [S10]; [S11] | [S10] Table 2; [S11] abstract |
| kimchi | acetoin | reported | no | 74.1 ± 19.4 in salted cabbage (d0); n.d. raw | — | LAB / plant | [S10] | [S10] Table 1 ("3-hydroxy-2-butanone") |
| kimchi | 2,3-butanediol | reported | no | 3.7 ± 1.4 salted (d0); n.d. raw | — | — | [S10] | [S10] Table 1 |
| kimchi | ethyl butanoate | calibrated | d0 n.d. → d3 n.d. → d5 6.5 → **d7 22.8** → d9 16.3 → d15 3.1 | 3.1 | — | LAB/yeast esterification | [S10] | [S10] Table 3 |
| kimchi | ethyl 2-methylbutanoate | calibrated | d0 n.d. → d3 2.0 → d5 10.0 → d7 20.8 → **d9 35.3** → d15 8.2 | 8.2 | — | from isoleucine (Ehrlich) + ethanol | [S10] | [S10] Table 3 |
| kimchi | hexanal | calibrated (flat) | raw 11.7 → salted 1.9 → d3 5.0 → d5 1.7 → d7 1.3 → d9 2.1 → d15 1.5 | 1.5 | log₃FD **5 in RC** (most intense raw odorant) → 1 in SC | LOX; salting inactivates LOX (Kim et al. 1997, cited) | [S10] | [S10] Tables 1–3 |
| kimchi | (Z)-3-hexenal | calibrated (loss only) | raw 12.9 → n.d. after salting; not detected during fermentation | n.d. | — | LOX/HPL at cutting; lost on salting | [S10] | [S10] Table 1 |
| kimchi | (Z)-3-hexenol | calibrated | raw 1489.7 → salted d0 10.4 → d3 32.0 → **d5 111.8** → d7 25.8 → d9 11.7 → d15 17.4 | 17.4 | log₃FD 3 (RC), n.d. (SC) | LOX/ADH; transient rise d3–5 | [S10] | [S10] Tables 1–3 |
| kimchi | methional | calibrated (low) | d0 0.3 → d3 0.2 → d5 0.5 → d7 0.4 → d9 0.6 → d15 1.6 | 1.6 | log₃FD 2 (RC and SC), baked potato | methionine Strecker/Ehrlich | [S10]; OI ≥ 3.5 in full kimchi [S11] | [S10] Tables 1–3; [S11] |
| kimchi | phenylacetaldehyde | calibrated (flat) | d0 6.6 → 6.3 → 7.6 → 9.5 → 6.5 → d15 7.1 | 7.1 | log₃FD 1; OI ≥ 3.5 in full kimchi [S11] | phenylalanine | [S10]; [S11] | [S10] Tables 1–3; [S11] |
| kimchi | linalool | reported | no | — | OI ≥ 3.5 | plant / ingredient terpenoid | [S11] | [S11] abstract |
| kimchi | acetic acid (engine pool) | (engine) | d0 n.d. → 3.8 → 15.8 → 44.9 → 148.8 → d15 1709.4 (SAFE badly under-recovers acetic acid: shape only) | — | — | heterofermentative LAB | [S10] | [S10] Table 3 |
| kimchi | zingiberene, geranial, neral (ginger) | plausible | — | none opened | — | ginger add-in | — | — |

#### Table D — kimchi

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point µg/kg | key-odorant data | producer / mechanism | conditions | source |
|---|---|---|---|---|---|---|---|---|
| kimchi | dimethyl tetrasulfide | calibrated (loss) | raw n.d. → d0 38.6 → n.d. from d3 | n.d. | log₃FD 2, "sulfury, kimchi-like" | SMCSO sulfides | [S10] | [S10] Tables 1–3 |
| kimchi | S-methyl methanethiosulfinate | calibrated (loss) | d0 344.1 → d3 n.d. → 0.8 → 1.8 → 1.3 → d15 0.4 | 0.4 | — | C-S lyase on SMCSO | [S10] | [S10] Table 3 |
| kimchi | allyl methyl trisulfide | calibrated (loss) | d0 9.4 → n.d. from d3 | n.d. | log₃FD 2, "fresh kimchi-like" | — | [S10] | [S10] Tables 1–3 |
| kimchi | methyl (methylthio)methyl disulfide | calibrated (loss) | d0 26.5 → n.d. from d3 | n.d. | log₃FD 0, garlic/spicy | — | [S10] | [S10] Tables 1–3 |
| kimchi | diallyl trisulfide | reported | no | — | OI ≥ 4.0 | garlic | [S11] | [S11] abstract |
| kimchi | 3-phenylpropanenitrile (benzenepropanenitrile) | calibrated | raw 3824.7 → d0 2126.1 → 1638.3 → 1544.7 → 1269.9 → 1392.3 → d15 807.2 | 807.2 | log₃FD 3, "fresh kimchi cabbage-like" | gluconasturtiin → nitrile (myrosinase) | [S10] | [S10] Tables 1–3 |
| kimchi | 2-phenylethyl isothiocyanate | reported | no (not in Table 3) | 136.9 raw → 760.9 salted | — | gluconasturtiin → ITC | [S10] | [S10] Table 1 |
| kimchi | (E,Z)-2,6-nonadienal | reported | no | — | log₃FD 2 (RC), 0 (SC); OI ≥ 3.5 in full kimchi | LOX on linolenic acid (cucumber-like) | [S10]; [S11] | [S10] Table 2; [S11] abstract |
| kimchi | (E,E)-2,4-decadienal | reported | no | — | OI ≥ 3.5 | lipid oxidation | [S11] | [S11] abstract |

### 2b. Radish (kkakdugi, takuan, paocai)

No concentration or time-course source for 4-methylthio-3-butenyl isothiocyanate (MTBITC) in a fermented radish was opened. [S12] (abstract) confirms MTBITC as "the pungent component of radish roots" and that it is converted, in salted radish (takuan-zuke), into a yellow pigment (TPMT), faster with dehydration, higher salting temperature and time — i.e. a **loss path** for MTBITC during salting (rate not given in the abstract).

| ferment | compound key | tier proposed | time course? | end-point µg/kg | key-odorant data | producer / mechanism | conditions | source |
|---|---|---|---|---|---|---|---|---|
| radish lacto-ferment | 4-methylthio-3-butenyl isothiocyanate | reported (qualitative) | no | — | "pungent component of radish roots" | myrosinase on glucoraphasatin; consumed by reaction with tryptophan → TPMT (yellowing) | salted, sun-dried radish, long-term salting, temperature-dependent | [S12] abstract |
| radish lacto-ferment | 3-butenyl ITC, AITC, allyl cyanide | plausible | — | — | — | — | — | — |

### 2c. Brined cucumber pickles (fermented, not fresh-pack)

[S13] (full text): cucumbers (size 2B) in jars with cover brine equilibrated to **2 % NaCl + 53 mM acetic acid**, inoculated with *L. plantarum* MOP-3 at 10⁶ CFU/mL; sugars exhausted by day 13; sampling d 0, 3, 5, 7, 10, 14, 21; purge-and-trap GC-MS; 7 compounds calibrated with 3-level standards (Table 2), others relative area. Temperature not stated on the pages read.

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg (d 21) | key-odorant data | producer / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| cucumber pickle | linalool | calibrated | relative area: rose "rapidly from day 3 to day 10", then stable (Fig. 4, read from figure) | 4.6 fresh → 44 (fermented cucumber), 81 (brine) | "several times its odor threshold" in first 10 d | released from cucumber (glycoside hydrolysis plausible; not shown) | [S13] | [S13] Table 2, Fig. 4 |
| cucumber pickle | hexanal | calibrated | brine RA increases d0→d21 (Fig. 4); slurry vs fresh P/C 0.43 | 29 fresh → 12 fermented cucumber; 38 brine | — | LOX at disruption; LOX capacity falls in fermentation | [S13] | [S13] Tables 1–2, Fig. 4 |
| cucumber pickle | (E)-2-nonenal | calibrated (loss) | slurry RA high at d0, **not detected after day 5** (Fig. 4) | n.d. | "one of the two most important volatiles in fresh cucumber odor" | LOX/HPL on linolenic acid at disruption; capacity lost | [S13] | [S13] abstract, Fig. 4 |
| cucumber pickle | ethyl acetate | calibrated (confounded) | RA jump after d3 (from acetic-acid impurity), stable, then rises after d14 (Fig. 4) | 43 fresh → 345 fermented cucumber, 365 brine | — | added with glacial acetic acid + formed during fermentation | [S13] | [S13] Table 2, Fig. 4, p. 2119 |
| cucumber pickle | dimethyl disulfide / dimethyl trisulfide | reported (presence) | no | relative area only, P/C ≈ 1.1 / 1.3 | — | — | [S13] | [S13] Table 1 |
| cucumber pickle | ethyl butanoate | reported (presence) | no | relative area, P/C 1.03 | — | — | [S13] | [S13] Table 1 |
| cucumber pickle | 3-methylbutanol, 2-methylbutanol | reported (presence) | no | relative area, P/C ≈ 1.0 | — | present in fresh cucumber too | [S13] | [S13] Table 1 |
| cucumber pickle | nonanal, geraniol | reported (presence) | no | relative area | — | — | [S13] | [S13] Table 1 |

#### Table D — cucumber pickles

| ferment | compound key | tier proposed | time course? | end-point µg/kg | key-odorant data | producer / mechanism | conditions | source |
|---|---|---|---|---|---|---|---|---|
| cucumber pickle | (E,Z)-2,6-nonadienal | calibrated (loss) | slurry RA declines "rapidly during the first week" (Fig. 4) | 3093 fresh slurry → 22.3 fermented cucumber; 2.93 brine | "most important" fresh-cucumber odorant; threshold 0.01 ppb in water quoted in [S13] Table 2 (from Buttery 1981, secondary) | LOX/HPL on α-linolenic acid at tissue disruption; generating capacity lost during fermentation | [S13] | [S13] abstract, Table 2, Fig. 4 |
| cucumber pickle | (E)-2-heptenal, octanal | reported | no | 2-heptenal 11 → 10 (9.4 brine); octanal 3.8 → 3.4 (4.4 brine) | — | lipid oxidation | [S13] | [S13] Table 2 |

## 3. Kefir (milk + grains)

Data quality note. Three kinds of evidence: (i) true concentrations from headspace GC with standards, abstracts only ([S18] Beshkova 2003, [S19] Güzel-Seydim 2000, [S20] Kök-Taş 2013, [S26] Abou Ayana 2025); (ii) **semi-quantitative** time course 0 / 24 / 48 h with grains at room temperature ([S23] Outeiriño 2026, internal standard 3-octanol, mg/L, response factor not compound-specific → treat as ±×3); (iii) relative-abundance time course 0 / 8 / 24 h at 25 °C with three grains ([S21] Walsh 2016) — direction of change only. Lu et al. 2026 [S22] (sensomics, OAV + recombination/omission) is the only key-odorant study found; abstract only. "calibrated (direction)" below = a published time course exists but only in relative areas; magnitude must come from the end-point column.

Conditions per source: [S18] kefir starter (*Lb. delbrueckii* subsp. *bulgaricus* HP1 + *Lb. helveticus* MP12 + *Lc. lactis* subsp. *lactis* C15 + *S. thermophilus* T15 + *S. cerevisiae* A13) vs kefir grains, fermentation + storage (T not in abstract). [S19] grain kefir stored at 4 °C for 0–21 d (fermentation conditions not in abstract). [S20] grains or natural kefir starter, normal or 10 % CO₂ atmosphere, 21-d storage. [S21] pasteurised milk + 3 Irish/French/UK grains, 25 °C, 24 h; grains dominated by *L. kefiranofaciens*; milk shifts from *L. kefiranofaciens* (8 h) to *Leuc. mesenteroides* (24 h); *S. cerevisiae*, *Kazachstania*, *Acetobacter pasteurianus* present. [S23] UHT whole milk + 3 % (w/v) milk kefir grains (0.03 g/mL), room temperature, no agitation, 48 h; at 48 h lactic 10.58 g/L, ethanol 5.17 g/L, acetic 2.02 g/L, pH 4.99.

### Table B — kefir

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| kefir | acetaldehyde | calibrated | storage 4 °C: d0 → d21 "doubled", reaching **11 000** (i.e. ≈ 5 500 at d0, implied) | 3 800–23 600 over 21-d storage [S20]; max **18 300** in starter kefir (mainly *Lb. bulgaricus* HP1) [S18]; 4 910 fresh cow-milk kefir [S26] | — | LAB (threonine aldolase / pyruvate; *Lb. bulgaricus*) + yeast pyruvate decarboxylase | see conditions | [S19] abstract; [S20] abstract; [S18] abstract; [S26] abstract |
| kefir | diacetyl | calibrated (direction) | 0 → 8 → 24 h: rises after 0 h (areas, Fig. 4) | max **1 870** (starter kefir); single strains: *S. thermophilus* 1 620, *Lb. helveticus* 850, *Lc. lactis* 420 [S18]; **not detected** in grain kefir during fermentation or storage [S19] | key aroma compound of kefir by OAV + recombination/omission ("buttery") [S22] | citrate/pyruvate overflow (α-acetolactate → oxidative decarboxylation); correlated with *Leuc. mesenteroides* and *Acetobacter* [S21]; adding *Leuc. mesenteroides* 213M0 raised 2,3-butanediol 14.9 % | [S21] 25 °C grains; [S18] | [S21] Table 1, Fig. 4, Table 3; [S18], [S19], [S22] abstracts |
| kefir | 2,3-pentanedione | calibrated (direction) | rises after 0 h (areas) | presence | — | from 2-aceto-2-hydroxybutyrate (isoleucine pathway); correlated with *Kazachstania* | [S21] | [S21] Table 1, p. "Correlations" |
| kefir | acetoin | calibrated | storage 4 °C: d0 **25 000** → d21 **16 000** (decreasing) | 16 000–25 000 | key aroma compound by OAV ("creamy") [S22]; about 2× higher in lactose-free kefir than traditional (relative) [S25] | as diacetyl; reduction of diacetyl; consumed slowly in storage | [S19] | [S19] abstract; [S22] abstract; [S25] |
| kefir | 2,3-butanediol | reported (presence) | no | presence; +14.9 % when *Leuc. mesenteroides* 213M0 added | — | acetoin reductase | [S21] | [S21] Results (Table S4 cited) |
| kefir | ethyl acetate | calibrated (direction) | rises after 0 h (areas) | presence; +100 % when *L. kefiranofaciens* NCFB 2797 added [S21]; *Lc. lactis* C15 "synthesized ethyl acetate more actively" than other starter strains [S18] | — | yeast AATase / LAB esterase + ethanol | [S21], [S18] | [S21] Table 1, Fig. 4; [S18] abstract |
| kefir | ethyl butanoate, ethyl hexanoate, isoamyl acetate | calibrated (direction) | rise after 0 h (areas) | presence | — | *S. cerevisiae* (correlated with esters) | [S21] | [S21] Table 1, Fig. 4, Table 3 |
| kefir | ethyl octanoate | calibrated (semi-quant) | 0 h n.d. → 24 h 930 → 48 h 240 µg/L | 240–930 | OAV 12.7 at 48 h (threshold used 19.3 µg/L) | yeast | [S23] | [S23] Tables 3–4 |
| kefir | ethyl decanoate | calibrated (semi-quant) | 0 h n.d. → 24 h n.d. → 48 h 290 µg/L | 290 | — | yeast | [S23] | [S23] Table 3 |
| kefir | hexanoic acid | calibrated (semi-quant) | n.d. → 790 → 2 530 µg/L (0/24/48 h) | 790–2 530 | — | lipolysis of milk fat + yeast/LAB | [S23]; also rises in [S21] | [S23] Table 3; [S21] Fig. 4 |
| kefir | octanoic acid | calibrated (semi-quant) | 2 550 (milk) → 3 720 → 5 690 µg/L | 3 720–5 690 | OAV 1.9 at 48 h (threshold used 3 000 µg/L) | as above | [S23] | [S23] Tables 3–4 |
| kefir | decanoic acid | calibrated (semi-quant) | 2 830 (milk) → 4 990 → 11 470 µg/L | 4 990–11 470 | OAV 11.5 (threshold used 1 000 µg/L) | as above | [S23] | [S23] Tables 3–4 |
| kefir | butanoic acid | reported | no | none opened | key aroma compound by OAV ("cheesy") [S22] | milk-fat lipolysis | [S22] | [S22] abstract |
| kefir | 2-heptanone | reported (direction conflicting) | [S23]: 1 810 in UHT milk → n.d. at 24 and 48 h; [S21]: +65.9 % when *L. kefiranofaciens* added | n.d.–1 810 | — | milk-derived (heat; β-keto acid decarboxylation in UHT) | [S23] UHT milk; [S21] pasteurised milk | [S23] Table 3; [S21] Results |
| kefir | 2-nonanone | calibrated (semi-quant) | 2 200 (UHT milk) → 430 → 1 060 µg/L | 430–1 060 | OAV 213 at 48 h (threshold used 5 µg/L) | milk-derived | [S23] | [S23] Tables 3–4; presence [S21] |
| kefir | δ-decalactone | calibrated (semi-quant) | 240 (milk) → 730 → **1 540** µg/L | 730–1 540 | OAV 616 (threshold used 2.5 µg/L) | release from milk-fat hydroxy-acid precursors (mechanism not shown) | [S23] | [S23] Tables 3–4 |
| kefir | δ-dodecalactone | calibrated (semi-quant) | 740 → 750 → 1 440 µg/L | 750–1 440 | OAV 313 (threshold used 4.6 µg/L) | as δ-decalactone | [S23] | [S23] Tables 3–4 |
| kefir | 2-phenylethanol | calibrated (semi-quant) | n.d. → 300 → 1 700 µg/L | 300–1 700 | — | Ehrlich (yeast) | [S23]; presence [S21] | [S23] Table 3 |
| kefir | 3-methylbutanol, 2-methylbutanol, 2-methylpropanol | calibrated (direction) | rise after 0 h (areas) | presence | — | Ehrlich (yeast); 3-methylbutanol correlated with *Lactobacillus* | [S21] | [S21] Table 1, Fig. 4 |
| kefir | 3-methylbutanal, 2-methylbutanal | calibrated (direction) | rise after 0 h (areas) | presence | — | Ehrlich / LAB transamination | [S21] | [S21] Table 1, Fig. 4 |
| kefir | hexanal | reported | did **not** rise after 0 h (areas) | — | key aroma compound by OAV ("grassy") [S22] | milk lipid oxidation (pre-existing) | [S21], [S22] | [S21] p. "Volatile-compound profiling"; [S22] abstract |
| kefir | nonanal | reported (presence) | no | presence | — | lipid oxidation | [S21] | [S21] Table 1 |
| kefir | limonene | reported (semi-quant, origin unclear) | n.d. → 420 → 1 060 µg/L | — | — | not explained (feed-derived terpenes?) | [S23] | [S23] Table 3 |
| kefir | dimethyl sulfide, methional | plausible | — | not reported in opened kefir sources | — | milk methionine / heat | — | — |
| kefir | ethanol (engine pool) | (engine) | storage 0.08 % by d21 [S19] | 76.5–5 147 mg/L over 21-d storage [S20]; 3 975 µg/g with *S. cerevisiae* A13 [S18]; 5.17 g/L at 48 h [S23] | — | yeasts | — | [S18]–[S20], [S23] |
| kefir | acetic acid (engine pool) | (engine) | logistic rise 0–48 h [S23] | 2.02 g/L (48 h, grains) [S23]; not detected in stored kefir [S19] | — | heterofermentative LAB, *Acetobacter* | — | [S23] abstract, Fig. 1; [S19] |

### Table D — kefir

| ferment | compound key | tier proposed | time course? | end-point µg/kg | key-odorant data | producer / mechanism | conditions | source |
|---|---|---|---|---|---|---|---|---|
| kefir | γ-dodecalactone | calibrated (semi-quant) | 480 (milk) → 370 → 640 µg/L | 370–640 | "high OAVs across all samples" | milk fat | [S23] | [S23] Table 3, Discussion |
| kefir | 2-undecanone | calibrated (semi-quant) | 2 360 (UHT milk) → 960 → 1 240 µg/L | 960–1 240 | OAV 428.6 in UHT milk | milk-derived methyl ketone | [S23] | [S23] Tables 3–4 |
| kefir | acetone, 2-butanone | reported | no | presence; acetone produced by *Lb. bulgaricus* HP1 and *Lb. helveticus* MP12 (not by cocci); 2-butanone linked to *Lb. helveticus* MP12 | — | — | [S18] | [S18] abstract; [S21] Table 1 (did not rise after 0 h) |
| kefir | 2,3-hexanedione | reported (presence) | rises after 0 h (areas) | — | — | correlated with *Kazachstania* | [S21] | [S21] Table 1 |

## 4. Cheese — curd/acidification stage and fresh cheeses

No quantitative time course was found for a true fresh cheese (quark, cottage, fromage frais). The evidence comes from three directions: (i) **milk citrate → α-acetolactate → diacetyl/acetoin kinetics** in milk cultures of *Lc. lactis* biovar *diacetylactis* / *Leuconostoc*; (ii) **the youngest point of a cheese ripening series** — Gouda taken "immediately out of the brine" (week 0) quantified by stable-isotope dilution [S32]; (iii) **milk baseline** concentrations (initial condition of the milk pools) by external-standard / SIDA quantitation [S34].

Citrate kinetics (for the pyruvate-overflow template and the citrate precursor pool):
- Milk citrate **11.3, 9.7 and 10.1 mmol/L** in early, mid and late lactation (SED 0.64; 24 cows, same diet) [S35] abstract — ≈ 1.9–2.2 g/L as citric acid (my conversion, MW 192.1). Note: higher than the ~1.6–1.8 g/L in the task brief.
- In 10 % (w/v) reconstituted skim milk at 30 °C, *Lc. lactis* biovar *diacetylactis* MR3 reached its maximum α-acetolactate (2.5 mM) **at 6 h, "a time which corresponded to citrate exhaustion"**; α-acetolactate then decays (chemical decarboxylation; acetoin the major product) and diacetyl + acetoin keep rising to 24 h without a plateau [S30] p. 5519, Fig. 1. **Caveat: MR3 is itself an α-acetolactate-decarboxylase-negative mutant** (selected from strain MR), so diacetyl/α-acetolactate are upper bounds for wild-type starters.
- Citrate utilisation by *L. lactis* and *Leuconostoc* is pH dependent, maximal at **pH 5.5–6.0**; acetoin/butanediol fermentation via α-acetolactate appears with mild aeration and "excess pyruvate production from citrate" [S29] abstract.
- *Str. diacetilactis* (= *Lc. lactis* biovar *diacetylactis*) in milk produced diacetyl, acetoin **and acetaldehyde** concomitantly with citrate utilisation; with *Leuc. cremoris*, "destruction of diacetyl and acetoin occurred when the citric acid level fell to c. 1000 and 600 µg/g" (strains FR8-1, CAF1) [S27] abstract → a reductase loss term (`c_ij`) that switches on near citrate depletion.
- Acetoin is "quantitatively the more important" C4 compound; homofermentative streptococci start citrate use immediately; destruction of accumulated acetoin "coincide[s] with the disappearance of citrate" [S28] abstract.
- Wild-type *Lc. lactis* biovar *diacetylactis* CNRZ 483 grown aerobically converted 2.3 % of glucose to acetoin and made no diacetyl or 2,3-butanediol; none anaerobically [S31] abstract (medium not stated in abstract) → without citrate, the sugar-derived C4 yield is small.

Gouda conditions [S32]/[S33]: pilot-scale; milk pasteurised 72–74 °C 30 s (PM-G) or raw (RM-G); "defined starter cultures" including *Lc. lactis* subsp. *lactis* biovar *diacetylactis* ([S32] Discussion); pre-ripening 35 °C 35 min, coagulation 45 min, curd washed, pressed, **brined 28 h** ([S33] Methods, via full-text extraction); "0 week" = taken immediately out of the brine. **Values are µg/kg dry matter**; SD < 10 %; reproduced in a second batch a year later.

### Table B — cheese curd / fresh cheese

| ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions | source (where) |
|---|---|---|---|---|---|---|---|---|
| cheese (curd) | diacetyl | calibrated | milk culture, 30 °C (read from figure, ±~10 %; ALDC⁻ strain → upper bound): 0 h 0 → 6 h ≈ 0.10 mM (≈ 8 600) → 12 h ≈ 0.15 mM (≈ 12 900) → 24 h ≈ 0.16 mM (≈ 13 800) [S30]. Gouda (DM): week 0 **2 416** (PM) / 1 192 (RM) → max at 4–7 weeks → falls by 30 weeks [S32] | unripened Gouda 1 192–2 416 µg/kg DM; milk baseline 11.1 (raw), 9.7 (pasteurised) µg/kg [S34] | key odorant of Gouda (one of 16 quantitated key odorants) [S32]; OAV < 1 in raw milk [S34] | *Lc. lactis* biovar *diacetylactis* / *Leuconostoc* citrate → pyruvate → α-acetolactate → chemical oxidative decarboxylation | see above | [S30] Fig. 1; [S32] Tables 1–2 and text; [S34] Table 2 |
| cheese (curd) | acetoin | calibrated (upper-bound strain) | milk culture 30 °C: ≈ 0.2 mM (≈ 17 600) to 6 h → ≈ 1.2 mM (≈ 106 000) at 12 h → ≈ 2.6 mM (≈ 229 000) at 24 h (read from figure, ±~10 %) | no curd/fresh-cheese end point opened | — | from α-acetolactate (ALDC or chemical) and diacetyl reduction; destroyed once citrate is gone [S27], [S28] | [S30] 10 % RSM, 30 °C, partial anaerobiosis | [S30] Fig. 1; [S28], [S27] abstracts; qualitative: highest acetoin among *Lc. lactis* isolates came from the strain with the highest citrate consumption [S36] |
| cheese (curd) | acetaldehyde | reported (qualitative) | no | — | — | *Lc. lactis* biovar *diacetylactis* during citrate use; only one of two *Leuc. cremoris* strains | milk | [S27] abstract |
| cheese (curd) | 2,3-butanediol | plausible | — | — | — | acetoin reductase; seen with aeration / excess pyruvate [S29] and in LDH-attenuated mutants [S31] | lab media | [S29], [S31] abstracts |
| cheese (curd) | 2,3-pentanedione | plausible | — | — | — | α-aceto-α-hydroxybutyrate (isoleucine pathway) | — | — |
| cheese (curd) | butanoic acid | reported | ripening series only (×16 over 30 weeks) | unripened Gouda **5 345** (PM) / 10 471 (RM) µg/kg DM; milk 32 110 (raw) vs 1 094 (pasteurised) µg/kg | key odorant of Gouda [S32]; OAV 133.8 in raw milk [S34] | milk-fat lipolysis (milk lipase; raw ≫ pasteurised) | [S32]; [S34] | [S32] Tables 1–2; [S34] Table 2 |
| cheese (curd) | hexanoic acid | reported | ripening only | unripened Gouda 5 279 / 9 571 µg/kg DM | key odorant of Gouda | lipolysis | [S32] | [S32] Tables 1–2 |
| cheese (curd) | octanoic / decanoic acid | reported (milk) | — | milk: octanoic 16 835 (raw) / 1 037 (past.); decanoic 7 167 / 380 µg/kg | OAV 18.5 / 55.1 in raw milk | lipolysis | [S34] | [S34] Table 2 |
| cheese (curd) | δ-decalactone | reported | unripened → slight rise to 11 weeks → slight fall at 30 weeks | unripened Gouda **1 920** (PM) / 2 167 (RM) µg/kg DM; milk 292 (raw), 138 (past.) µg/kg | key odorant of Gouda; OAV 4.2 in raw milk | "already quite high in the unripened cheese"; direct lactonisation from intact triglycerides suggested (not in line with lipase activity) | [S32]; [S34] | [S32] Tables 1–2, Discussion; [S34] Table 2 |
| cheese (curd) | δ-dodecalactone | reported | as δ-decalactone | unripened Gouda 2 419 / 2 186 µg/kg DM; milk 2 388 (raw), 844 (past.) µg/kg | key odorant; OAV 45.1 in raw milk | as above | [S32]; [S34] | as above |
| cheese (curd) | ethyl butanoate / ethyl hexanoate | reported | ripening only | unripened Gouda 16 / 39 and 2 / 21 µg/kg DM (PM / RM) | key odorants of Gouda | esterification of free FA with ethanol (LAB) | [S32] | [S32] Tables 1–2 |
| cheese (curd) | 3-methylbutanal | reported | max at 7 weeks | unripened Gouda 215 / 76 µg/kg DM | key odorant | leucine → Ehrlich/transamination by LAB | [S32] | [S32] Tables 1–2 |
| cheese (curd) | 3-methylbutanol, 2-phenylethanol | reported | ripening only | 99 / 32 and 144 / 120 µg/kg DM | key odorants | as above | [S32] | [S32] Tables 1–2 |
| cheese (curd) | 3-methylbutanoic, 2-methylbutanoic, 2-methylpropanoic acid | reported | ×35–65 over ripening | 622 / 661; 90 / 67; 466 / 478 µg/kg DM | key odorants | branched-chain amino acid catabolism | [S32] | [S32] Tables 1–2 |
| cheese (curd) | hexanal | reported (milk) | — | milk 57.2 (raw), 51.3 (past.) µg/kg | OAV 11.4 in raw milk | milk lipid oxidation | [S34] | [S34] Table 2 |
| cheese (curd) | 2-heptanone, 2-nonanone | plausible | — | 2-heptanone n.d. in raw and pasteurised milk; 23–44 µg/kg only in UHT milk [S34] | — | heat-induced methyl ketones (UHT); mould ripening out of scope | [S34] | [S34] Table 2 |
| cheese (curd) | dimethyl sulfide | plausible | — | no source opened | — | milk / methionine | — | — |
| cheese (curd) | acetic acid (engine pool) | (engine) | "already quite high in the unripened curd" | unripened Gouda 712 539 / 416 299 µg/kg DM | key odorant | starter / citrate (acetate from citrate lyase) | [S32] | [S32] Tables 1–2 |

### Table D — cheese curd

| ferment | compound key | tier proposed | time course? | end-point µg/kg | key-odorant data | producer / mechanism | conditions | source |
|---|---|---|---|---|---|---|---|---|
| cheese (curd) | pentanoic acid | reported | ripening only | 121 / 179 µg/kg DM (unripened, PM / RM) | key odorant of Gouda | lipolysis | [S32] | [S32] Tables 1–2 |
| cheese (curd) | 2-phenylacetic acid | reported | ripening only | 624 µg/kg DM (unripened PM) | key odorant | phenylalanine catabolism | [S32] | [S32] Table 1 |
| cheese (curd) | γ-dodecalactone | reported (milk) | — | n.d. raw; 40.2 pasteurised; 123 INJ-UHT µg/kg | threshold used 0.43 µg/kg → high OAV once present | milk fat, heat | [S34] | [S34] Table 2 |
| cheese (curd) | α-acetolactate (non-odorous precursor, model state variable) | — | peak 2.5 mM at 6 h (citrate exhaustion), then decays to ≈ 0.4 mM by 24 h (read from figure) | — | — | the kinetic intermediate between citrate/pyruvate and diacetyl/acetoin | [S30] | [S30] text, Fig. 1 |

## E. Unverified leads

| value | why I believe it | what to search |
|---|---|---|
| DMTS 150 ppb in unspiced commercial sauerkraut, none in caraway-spiced; DMDS 63 vs 25 ppb | quoted in [S1] p. S348 (secondary) | Chin HW, Lindsay RC 1994, "Modulation of volatile sulfur compounds in cruciferous vegetables", in Mussinan & Keelan (eds.) *Sulfur Compounds in Foods*, ACS Symp. Ser., pp. 90–104 |
| Odour thresholds MMTSO ≈ 550 ppb, MMTSO₂ ≈ 5 ppm | quoted in [S1] p. S343 (secondary) | Chin HW, Lindsay RC 1994, J Agric Food Chem 42(7):1529–1536 |
| SMCSO in cabbage 185–2218 ppm FW (precursor prior) | quoted in [S1] p. S343 (secondary) | Marks HS et al. 1992, J Agric Food Chem 40:2098–2101; Bradshaw & Borzucki 1982 |
| MMTSO peaks ~24 h after cabbage juice preparation, then decays at 30 °C | quoted in [S1] p. S349 | Kyung KH, Fleming HP 1994, J Food Sci 59(2):350–355 |
| Time course of AITC / allyl cyanide / 3-butenyl ITC in sauerkraut **and** juice over fermentation and storage | abstract of [S15] says ITCs tracked through fermentation and long storage; numbers only in full text | Ciska E, Honke J, Drabińska N 2021, Food Chem 365:130498, tables |
| AITC, allyl cyanide, iberin, iberin nitrile concentrations by NaCl (0.5 / 1.5 %) and starter | abstract of [S7] | Peñas E et al. 2012, LWT 48:16–23, tables |
| Whether volatile ITCs were also quantified day-by-day (20 °C) | [S5] tracked GLS degradation daily; abstract reports only indoles | Palani K et al. 2016, Food Chem 190:755–762, full text |
| Sauerkraut volatiles (green C6, sulfur, "acetoin derivatives", alcohols) in mg/kg for 8 cultivars, 2-week fermentation | abstract of [S14] | Satora P et al. 2021, LWT 136, full text |
| Suancai key odorants (GC-O) across fermentation days | title/abstract listing in Europe PMC only | Mei Y et al. 2023, LWT 178, "Decoding the evolution of aromatic volatile compounds and key odorants in Suancai … SBSE–GC–O–MS" |
| Kimchi sulfides rise at the start then fall slowly | cited in [S10] Discussion | Kang JH et al. 2003 (Korean J Food Sci Technol); Hwang et al. 2019 |
| Kefir acetaldehyde / diacetyl / acetoin / ethanol / 2-butanone **time course during fermentation** (hours) | title and [S21] reference list; abstract not available in Europe PMC | Güzel-Seydim ZB, Seydim AC, Greene AK, Bodine AB 2000, *J Food Compos Anal* 13(1):35–43, doi:10.1006/jfca.1999.0842 |
| Beshkova kefir carbonyls (acetaldehyde, diacetyl, acetone, 2-butanone, ethyl acetate) through fermentation **and** storage | abstract of [S18] says both were followed; only maxima given | [S18] full text, figures/tables |
| 2,3-butanedione and ethanal kinetics in goat/sheep kefir (high-PUFA milk) | abstract of [S24] | [S24] full text |
| Concentrations/OAVs of 2,3-butanedione, hexanal, acetoin, butanoic acid in kefir | key-odorant conclusion in [S22] abstract | [S22] full text, OAV table |
| Wild-type *Lc. lactis* biovar *diacetylactis* / *Leuc. cremoris* diacetyl, acetoin, acetaldehyde vs citrate in milk (µg/g, hours) | [S27] abstract gives thresholds only (citric acid ≈ 1000 / 600 µg/g at C4 destruction) | Cogan TM 1975, *J Dairy Res* 42:139–146, figures; Drinan et al. 1976 [S28] figures (PMC PDF was not downloadable) |
| Fresh-cheese (cream cheese) volatiles by fermentation stage, OAV/ROAV | [S37] abstract (no numbers) | Zheng AR et al. 2024, *Curr Res Food Sci* 8:100772 (PMC11150910) |
| Milk citrate ≈ 1.6–1.8 g/L (task brief) vs 1.9–2.2 g/L from [S35] | value in the task brief | a dairy-chemistry handbook (e.g. Walstra, *Dairy Science and Technology*) or a bulk-milk survey |
| Gouda production details (starter composition, brine strength, cheese water content to convert DM → fresh weight) | extracted by an automated page summary of [S33]; starter species not given there | [S33] full text / supporting information |

## Sources

- **[S1]** Johanningsmeier SD, Fleming HP, Thompson RL, McFeeters RF (2005). Chemical and sensory properties of sauerkraut produced with *Leuconostoc mesenteroides* starter cultures of differing malolactic phenotypes. *J Food Sci* 70(5):S343–S349. doi:10.1111/j.1365-2621.2005.tb09989.x. Full text (USDA-ARS PDF, ars.usda.gov/ARSUserFiles/60701000/Pickle Pubs/p336.pdf).
- **[S2]** Trail AC, Fleming HP, Young CT, McFeeters RF (1996). Chemical and sensory characterization of commercial sauerkraut. *J Food Qual* 19(1):15–30. doi:10.1111/j.1745-4557.1996.tb00402.x. Full text (USDA-ARS scanned PDF p258).
- **[S3]** Tolonen M, Rajaniemi S, Pihlava JM, Johansson T, Saris PEJ, Ryhänen EL (2004). Formation of nisin, plant-derived biomolecules and antimicrobial activity in starter culture fermentations of sauerkraut. *Food Microbiol* 21(2):167–179. doi:10.1016/S0740-0020(03)00058-3. Abstract only.
- **[S4]** Tolonen M, Taipale M, Viander B, Pihlava JM, Korhonen H, Ryhänen EL (2002). Plant-derived biomolecules in fermented cabbage. *J Agric Food Chem* 50(23):6798–6803. doi:10.1021/jf0109017. Abstract only.
- **[S5]** Palani K, Harbaum-Piayda B, Meske D, Keppler JK, Bockelmann W, Heller KJ, Schwarz K (2016). Influence of fermentation on glucosinolates and glucobrassicin degradation products in sauerkraut. *Food Chem* 190:755–762. doi:10.1016/j.foodchem.2015.06.012. Abstract only.
- **[S6]** Ciska E, Pathak DR (2004). Glucosinolate derivatives in stored fermented cabbage. *J Agric Food Chem* 52(26):7938–7943. doi:10.1021/jf048986+. Abstract only.
- **[S7]** Peñas E, Pihlava JM, Vidal-Valverde C, Frias J (2012). Influence of fermentation conditions of *Brassica oleracea* L. var. *capitata* on the volatile glucosinolate hydrolysis compounds of sauerkrauts. *LWT* 48(1):16–23. doi:10.1016/j.lwt.2012.03.005. Abstract only.
- **[S8]** Major N, Bažon I, Išić N, Kovačević TK, Ban D, Radeka S, Goreta Ban S (2022). Bioactive properties, volatile compounds, and sensory profile of sauerkraut are dependent on cultivar choice and storage conditions. *Foods* 11(9):1218. doi:10.3390/foods11091218. Full text (PMC9101451); volatiles as peak areas.
- **[S9]** Yang X, Hu W, Xiu Z, Jiang A, Yang X, Saren G, Ji Y, Guan Y, Feng K (2020). Microbial community dynamics and metabolome changes during spontaneous fermentation of northeast sauerkraut from different households. *Front Microbiol* 11:1878. doi:10.3389/fmicb.2020.01878. Full text (PMC7419431); volatile values in Suppl. Table S1 (not opened) — presence only.
- **[S10]** Seo WH, You Y, Baek HH (2024). Changes in volatile flavor compounds of Kimchi cabbage (*Brassica rapa* subsp. *pekinensis*) during salting and fermentation. *Food Sci Biotechnol* 33(7):1623–1632. doi:10.1007/s10068-023-01469-w. Full text (PMC11016023).
- **[S11]** Cha YJ, Kim H, Cadwallader KR (1998). Aroma-active compounds in Kimchi during fermentation. *J Agric Food Chem* 46(5):1944–1953. doi:10.1021/jf9706991. Abstract only.
- **[S12]** Takahashi A, Yamada T, Uchiyama Y, Hayashi S, Kumakura K, Takahashi H, Kimura N, Matsuoka H (2015). Generation of the antioxidant yellow pigment derived from 4-methylthio-3-butenyl isothiocyanate in salted radish roots (takuan-zuke). *Biosci Biotechnol Biochem* 79(9):1512–1517. doi:10.1080/09168451.2015.1032881. Abstract only.
- **[S13]** Zhou A, McFeeters RF (1998). Volatile compounds in cucumbers fermented in low-salt conditions. *J Agric Food Chem* 46(6):2117–2122 (PII S0021-8561(97)00472-X as printed; DOI not verified). Full text (USDA-ARS scanned PDF p277).
- **[S14]** Satora P, Skotniczny M, Strnad S, Piechowicz W (2021). Chemical composition and sensory quality of sauerkraut produced from different cabbage varieties. *LWT* 136 (article number not retrieved). Abstract only.
- **[S15]** Ciska E, Honke J, Drabińska N (2021). Changes in glucosinolates and their breakdown products during the fermentation of cabbage and prolonged storage of sauerkraut: focus on sauerkraut juice. *Food Chem* 365:130498. doi:10.1016/j.foodchem.2021.130498. Abstract only (no numbers).
- **[S17]** Martinez-Villaluenga C, Peñas E, Frias J, Ciska E, Honke J, Piskula MK, Kozlowska H, Vidal-Valverde C (2009). Influence of fermentation conditions on glucosinolates, ascorbigen, and ascorbic acid content in white cabbage (*Brassica oleracea* var. *capitata* cv. Taler) cultivated in different seasons. *J Food Sci* 74(1):C62–C67. doi:10.1111/j.1750-3841.2008.01017.x. Abstract only.
- **[S18]** Beshkova DM, Simova ED, Frengova GI, Simov ZI, Dimitrov ZP (2003). Production of volatile aroma compounds by kefir starter cultures. *Int Dairy J* 13(7):529–535. doi:10.1016/S0958-6946(03)00058-X. Abstract only.
- **[S19]** Guzel-Seydim Z, Seydim AC, Greene AK (2000). Organic acids and volatile flavor components evolved during refrigerated storage of kefir. *J Dairy Sci* 83(2):275–277. doi:10.3168/jds.S0022-0302(00)74874-0. Abstract only.
- **[S20]** Kök-Taş T, Seydim AC, Özer B, Guzel-Seydim ZB (2013). Effects of different fermentation parameters on quality characteristics of kefir. *J Dairy Sci* 96(2):780–789. doi:10.3168/jds.2012-5753. Abstract only.
- **[S21]** Walsh AM, Crispie F, Kilcawley K, O'Sullivan O, O'Sullivan MG, Claesson MJ, Cotter PD (2016). Microbial succession and flavor production in the fermented dairy beverage kefir. *mSystems* 1(5):e00052-16. doi:10.1128/mSystems.00052-16. Full text (PMC5080400); volatiles as relative abundance (Fig. 4).
- **[S22]** Lu K, Zhang J, Ma R, Li M, Chai J, Blank I, Chen YP, Liu Y (2026). Characterization and comparative analysis of the key aroma compounds in selected kefir and yogurt samples by sensomics. *J Agric Food Chem* 74(8):7013–7023. doi:10.1021/acs.jafc.5c16188. Abstract only.
- **[S23]** Outeiriño EB, Justel MA, Novo CP, Couñago AA, Guerra NP (2026). Production and characterization of kefir beverages by fermentation of whole milk with milk or water kefir grains. *Foods* 15(10):1616. doi:10.3390/foods15101616. Full text (PMC13205963); Table 3 "Concentrations (mg/L) of VOCs", semi-quantitative vs 3-octanol.
- **[S24]** Cais-Sokolińska D, Wójtowski J, Pikul J, Danków R, Majcher M, Teichert J, Bagnicka E (2015). Formation of volatile compounds in kefir made of goat and sheep milk with high polyunsaturated fatty acid content. *J Dairy Sci* 98(10):6692–6705. doi:10.3168/jds.2015-9441. Abstract only (no numbers; lead in E).
- **[S25]** Rutkowska J, Antoniewska-Krzeska A, Żbikowska A, Cazón P, Vázquez M (2022). Volatile composition and sensory profile of lactose-free kefir, and its acceptability by elderly consumers. *Molecules* 27(17):5386. doi:10.3390/molecules27175386. Full text (PMC9457958), semi-quantitative relative abundance; abstract: lactose-free kefir had "two times more ketones, especially 3-hydroxy-2-butanone and 2,3-butanedione".
- **[S26]** Abou Ayana IAA, Al-Otibi FO, Elgarhy MR, Omar MM, El-Abbassy MZ, Khalifa SA, Helmy YA, Saber WIA (2025). Chemical, physical, microbial, and sensory properties of innovative sesame milk kefir, focusing on the ultrastructure of kefir grains. *ACS Omega* 10(8):7752–7769. doi:10.1021/acsomega.4c08044. Abstract only (cow-milk kefir acetaldehyde 4.91 mg/L).
- **[S27]** Cogan TM (1975). Citrate utilization in milk by *Leuconostoc cremoris* and *Streptococcus diacetilactis*. *J Dairy Res* 42(1):139–146. doi:10.1017/S0022029900015168. Abstract only.
- **[S28]** Drinan DF, Robin S, Cogan TM (1976). Citric acid metabolism in hetero- and homofermentative lactic acid bacteria. *Appl Environ Microbiol* 31(4):481–486. doi:10.1128/aem.31.4.481-486.1976. Abstract only (PMC169808 PDF not retrievable).
- **[S29]** Starrenburg MJ, Hugenholtz J (1991). Citrate fermentation by *Lactococcus* and *Leuconostoc* spp. *Appl Environ Microbiol* 57(12):3535–3540. doi:10.1128/aem.57.12.3535-3540.1991. Abstract only.
- **[S30]** Monnet C, Aymes F, Corrieu G (2000). Diacetyl and α-acetolactate overproduction by *Lactococcus lactis* subsp. *lactis* biovar *diacetylactis* mutants that are deficient in α-acetolactate decarboxylase and have a low lactate dehydrogenase activity. *Appl Environ Microbiol* 66(12):5518–5520. doi:10.1128/AEM.66.12.5518-5520.2000. Full text (PMC92495); Fig. 1 read by eye.
- **[S31]** Boumerdassi H, Monnet C, Desmazeaud M, Corrieu G (1997). Isolation and properties of *Lactococcus lactis* subsp. *lactis* biovar *diacetylactis* CNRZ 483 mutants producing diacetyl and acetoin from glucose. *Appl Environ Microbiol* 63(6):2293–2299. doi:10.1128/aem.63.6.2293-2299.1997. Abstract only.
- **[S32]** Duensing PW, Hinrichs J, Schieberle P (2024). Formation of key aroma compounds during 30 weeks of ripening in Gouda-type cheese produced from pasteurized and raw milk. *J Agric Food Chem* 72(19):11072–11079. doi:10.1021/acs.jafc.4c01814. Full text (PMC11100003); SIDA, µg/kg dry matter.
- **[S33]** Duensing PW, Hinrichs J, Schieberle P (2024). Influence of milk pasteurization on the key aroma compounds in a 30 weeks ripened pilot-scale Gouda cheese elucidated by the sensomics approach. *J Agric Food Chem* 72(19):11062–11071. doi:10.1021/acs.jafc.4c01813. Full text (PMC11100000); production details taken from an automated summary of the Methods (verify).
- **[S34]** Xu K, Han H, Wang X, Zhang X, Yang X, Lu X, Han Z, Wang S, Wang Y, Wang B (2026). Elucidation of key aroma-active compounds and sensory profiles in raw and thermally sterilized milks: perspective from molecular sensory science. *Food Chem X* 34:103696. doi:10.1016/j.fochx.2026.103696. Full text (PMC12950439), Table 2 (external-standard calibration, µg/kg).
- **[S35]** Garnsworthy PC, Masson LL, Lock AL, Mottram TT (2006). Variation of milk citrate with stage of lactation and de novo fatty acid synthesis in dairy cows. *J Dairy Sci* 89(5):1604–1612. doi:10.3168/jds.S0022-0302(06)72227-5. Abstract only.
- **[S36]** Silva LF, Sunakozawa TN, Monteiro DA, Casella T, Conti AC, Todorov SD, Barretto Penna AL (2023). Potential of cheese-associated lactic acid bacteria to metabolize citrate and produce organic acids and acetoin. *Metabolites* 13(11):1134. doi:10.3390/metabo13111134. Full text (PMC10673126); values only in figures (qualitative use).
- **[S37]** Zheng AR, Wei CK, Wang MS, Ju N, Fan M (2024). Characterization of the key flavor compounds in cream cheese by GC-MS, GC-IMS, sensory analysis and multivariable statistics. *Curr Res Food Sci* 8:100772. doi:10.1016/j.crfs.2024.100772. Abstract only (lead in E).

Not used as data but consulted: Wolkers-Rooijackers JCM, Nout MJR, Thomas SM (2013), *LWT* 54(2):383–388, doi:10.1016/j.lwt.2013.07.002 (sauerkraut at 15 g/kg NaCl dominated by *Lc. lactis* and *Leuc. mesenteroides* — supports adding *Lc. lactis* as a sauerkraut organism); Satora P et al. (2020), *Int J Mol Sci* 21(24):9699, doi:10.3390/ijms21249699 (yeast isolates from sauerkraut fermented at 2.5 % NaCl; volatiles semi-quantitative in synthetic medium).
