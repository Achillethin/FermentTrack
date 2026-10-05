# Aroma literature review — shared brief for the research agents

**Project:** FermentTrack, a fermentation tracker whose forecast is a Bayesian ensemble of mechanistic kinetic models (Monod/Luedeking–Piret growth, charge-balance pH, enzymes) for kombucha, vinegar, sourdough (dough before baking), koji, lacto-ferments (sauerkraut and other vegetables), kefir, cheese (curd/acidification stage only, no ripening), miso and garum (fish sauce, traditional and koji-based). Increment A (nutrition + taste) shipped. **Increment B adds aroma**: ~85 odorants computed as passive tracers on each ensemble member's trajectory. Design: `docs/superpowers/specs/2026-10-02-flavour-nutrition-design.md` § 4–5 (read it).

**Tracer form each compound will use** (so collect parameters that fit it):

```
dC/dt = Σj ( a_ij·μjXj  +  b_ij·vj )                       growth-linked (per g biomass made) + per g substrate fermented by organism j
      + r_i(T)·P_i                                         release from a precursor pool P_i (plant, milk, fish, free amino acids)
      + chem_i(T, pools)                                   chemistry (esterification, Strecker/Maillard)
      − [ k0_i·Q10^((T−25)/10) + Σj c_ij·Xj ]·C            loss: evaporation/chemical + conversion by organism j
```

Organisms in the model: *Saccharomyces cerevisiae*, *Kazachstania humilis*, *Zygosaccharomyces rouxii*, *Kluyveromyces marxianus*, *Lactobacillus plantarum*, *L. brevis*, *L. sanfranciscensis*, *L. reuteri*, *L. kefiri*, *L. kefiranofaciens*, *Leuconostoc mesenteroides*, *Lactococcus lactis*, *Tetragenococcus halophilus*, *Acetobacter aceti*, *A. pasteurianus*, *Gluconacetobacter (Komagataeibacter) xylinus*, *Aspergillus oryzae*. Pools the engine already tracks: sucrose, glucose+fructose, lactose, maltose, starch, protein, peptides, free amino acids, ethanol, lactic, acetic, gluconic acid, CO₂.

**Evidence tiers** (per compound × ferment type): **calibrated** = a published *time course* in that ferment; **reported** = reported present (end-point concentration, AEDA/OAV key-odorant study) but no time course; **plausible** = pathway/precursor present, not reported in that ferment; **drop** = no defensible mechanism or no threshold.

**Aromatic series** (assign 1–2 per compound): fruity, floral, green, buttery, malty, sulfurous, pungent, vinegary, cheesy, solvent, mushroom, caramel, roasty, fishy, phenolic, herbal.

## Rules (non-negotiable)

1. **Every number must come from a source you actually opened** (full text or at least the abstract that states the number). Record the full citation — authors, year, title, journal, volume, pages, DOI — and *where* in the source (Table 2, Fig. 3, p. 5). Values read off a figure are marked "read from figure, ±~10 %".
2. **Never fabricate or reconstruct a citation from memory.** If you recall a value but cannot open a source for it, list it under "Unverified leads" with what you would search; the spec writer will not use it as data.
3. Prefer primary studies; reviews are fine as pointers (follow them to the primary paper when you can).
4. Normalise units: concentrations in µg/kg (≈ µg/L), thresholds in µg/kg **in water** (say so if the only threshold is in another matrix — beer, wine, oil, air), times in hours or days, temperatures in °C.
5. Report the **spread** (ranges across studies or replicate SD), not just one value: the model uses priors (median + 90 % range).
6. Public literature only. Do not paste repository code anywhere; search only on compound, organism and food names. **Never put any personal identifier (email address, name, account id) into a web request** — skip services that ask for one (e.g. the Unpaywall API); use publisher pages, PubMed/PMC, Europe PMC or DOI landing pages.
7. Write your findings to the file named in your task (Markdown, the tables below). Your final chat reply is a ≤ 200-word summary: counts by tier, the strongest sources, and the biggest gaps.

## Output tables (use the ones your task asks for)

**A. Identity & threshold** — `key | name | CAS | PubChem CID | ChEBI | KEGG | odour descriptor(s) | series | threshold in water µg/kg (median) | range across sources | sources (where) | notes`

**B. Evidence per ferment** — `ferment | compound key | tier proposed | time course? (times → µg/kg) | end-point range µg/kg | key-odorant data (FD/OAV) | producer(s) / mechanism | conditions (T, organisms, matrix) | source (where)`

**C. Template parameters** — `template | parameter | value | units | spread | organism / conditions | source (where) | maps to (a_ij, b_ij, r_i, k0_i, c_ij, chem)`

**D. Missing key odorants** — compounds that are key odorants in a ferment but not on the candidate list, with evidence (same columns as B).

**E. Unverified leads** — value, why you believe it, what to search.

## Candidate compounds (spec § 4.2)

Ehrlich (yeast): 3-methylbutanal, 2-methylbutanal, 2-methylpropanal, phenylacetaldehyde, methional; 3-methylbutanol, 2-methylbutanol, 2-methylpropanol, 2-phenylethanol, methionol; 3-methylbutanoic, 2-methylbutanoic, 2-methylpropanoic acid.
Esters & MCFA: ethyl acetate, isoamyl acetate, 2-phenylethyl acetate, isobutyl acetate, ethyl butanoate, ethyl hexanoate, ethyl octanoate, ethyl decanoate, ethyl 2-methylbutanoate, ethyl 2-methylpropanoate; hexanoic, octanoic, decanoic acid.
Pyruvate overflow: acetaldehyde, diacetyl, 2,3-pentanedione, acetoin, 2,3-butanediol. Chemical esterification: ethyl lactate (and ethyl acetate's chemical share).
Lipid oxidation / LOX / mould: hexanal, (Z)-3-hexenal, (Z)-3-hexenol, (E)-2-nonenal, nonanal, 2-pentylfuran, (Z)-4-heptenal, 1-octen-3-ol, 1-octen-3-one, 3-octanone, 3-octanol.
Glucosinolates: allyl isothiocyanate, allyl cyanide, 3-butenyl isothiocyanate, 4-methylthio-3-butenyl isothiocyanate.
Sulfur: methanethiol, dimethyl sulfide, dimethyl disulfide, dimethyl trisulfide, S-methyl thioacetate, diallyl disulfide, allyl methyl disulfide.
Terpenoids (tea, spices, herbs): linalool, geraniol, citronellol, methyl salicylate, β-damascenone, β-ionone, geranial, neral, zingiberene, carvone, limonene.
Phenolics: 4-vinylguaiacol, 4-vinylphenol, 4-ethylguaiacol, 4-ethylphenol.
Slow Maillard/Strecker: HEMF, furaneol (HDMF), norfuraneol, maltol, sotolon, 2,5-dimethylpyrazine, 2,3,5-trimethylpyrazine.
Milk-derived: δ-decalactone, δ-dodecalactone, butanoic acid, 2-heptanone, 2-nonanone. Fish/rice: trimethylamine; 2-acetyl-1-pyrroline.
Already in the engine (thresholds only): acetic acid, ethanol.
