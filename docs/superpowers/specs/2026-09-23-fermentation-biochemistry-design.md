# Fermentation Biochemistry — Organisms, Enzymes, Compounds — Design

**Date:** 2026-09-23
**Status:** approved by Achille, 2026-09-23
**Builds on:** `models.py`'s `Culture`/`Batch`/`Ingredient`/`BatchIngredient`, `stages.py`'s fermentation-type vocabulary, the frozen-snapshot pattern from `2026-09-23-usda-food-catalog-design.md`.
**Reverses:** `docs/STRATEGY.md` Direction 3's deferral and part of `docs/DEPENDENCIES.md` §2 — see "Reversing the Direction 3 deferral" below.

## Problem

FermentTrack logs *what went into* a batch (`Ingredient`/`BatchIngredient`) and *what was measured* (`Measurement`), but has no structured record of the biochemistry driving a fermentation: which organisms are active, which enzymes they express, which compounds those enzymes produce. Achille wants this added so a later predictive model can use organism/enzyme/compound presence as features alongside measurement history, not just free-text ingredient names.

## Reversing the Direction 3 deferral

`docs/STRATEGY.md` "Direction 3: Knowledge-Powered Intelligence" and `docs/specs/fermentgraph-evolution.md` recorded a 2026-09-18 decision to defer any compound/microbial data reaching FermentTrack's UI until `fermentgraph`'s ranker beats a popularity baseline by ≥+0.05 Recall@50 — because a 3-agent review found that surfacing unvalidated compound/microbial data, even labeled "unvalidated," repeats the project's earlier overclaiming mistake (the fictional `generate_suggestions`/`query_analogs` API).

**This spec reverses that deferral**, on the basis that the original objection was about *sourcing*: presenting `fermentgraph`'s unvalidated, null-result heuristic priors as if they were intelligence. Sourcing instead from **KEGG** — a curated, citable, versioned public database, frozen into an offline snapshot exactly like the USDA FDC data — is a different, defensible provenance. The data is real biochemistry (KEGG pathway/enzyme/compound entries), not a heuristic ranking model, and is presented as reference data, not a prediction.

**What does not change:** `docs/DEPENDENCIES.md` §2's verdict on `fermentgraph` itself ("don't use yet" — dirty main, no CI, no versioning, null ranker result) is untouched. This spec does not depend on `fermentgraph` at all. Implementation must update:
- `docs/STRATEGY.md` Direction 3 — mark the UI-deferral condition as superseded for the KEGG-sourced reference layer specifically, not lifted for any future `fermentgraph` integration.
- `docs/DEPENDENCIES.md` — add a dated note cross-referencing this spec, clarifying the fermentgraph verdict is unaffected.
- `docs/specs/fermentgraph-evolution.md` — note that FermentTrack no longer needs its `associated_microbes`/`associated_compounds` export to get this feature, since KEGG covers it; the export stays deferred on its original trigger if `fermentgraph` ever wants to reconcile against these tables via `canonical_id` later (see "Alternatives" below).

## Decisions (made with Achille)

| Question | Decision |
|---|---|
| Data source | **KEGG** (REST API, public, free for this use), frozen into an offline snapshot — not a live dependency. BRENDA/FooDB/fuller NCBI Taxonomy sync are noted as future expansions, not built now. |
| Reference vs per-batch | **Both.** A static default per fermentation type (`fermentation_type_organisms`), with an optional per-batch override/addition (`batch_organisms`) for e.g. a specific commercial yeast strain. |
| Fermentation type as a concept | Stays a free-text key (`kombucha`, `sourdough`, ... — the existing `Culture.type`/`STAGE_MACHINES` vocabulary), **not** a new lookup table. Matches the existing convention; no source of drift is introduced since ingestion validates against the known set. |
| UI this increment | **None.** This increment ships the data model, KEGG ingestion, and a read endpoint. A frontend panel is a natural next increment, not bundled here (keeps this increment reviewable on its own, and the reversal above is scoped to what's actually being built now). |

## Design

### Data model (migration 0008)

```
organisms                 id UUID PK, name TEXT NOT NULL, kingdom TEXT NOT NULL (bacteria|yeast|mold),
                           ncbi_taxon_id TEXT NULL, kegg_organism_code TEXT NULL,
                           source_version TEXT NOT NULL

enzymes                    id UUID PK, ec_number TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                           kegg_entry_id TEXT NULL, source_version TEXT NOT NULL

compounds                  id UUID PK, kegg_compound_id TEXT NULL UNIQUE, name TEXT NOT NULL,
                           category TEXT NOT NULL (acid|alcohol|gas|flavor|other),
                           source_version TEXT NOT NULL

organism_enzymes           id UUID PK, organism_id FK->organisms, enzyme_id FK->enzymes,
                           UNIQUE(organism_id, enzyme_id)
                           -- "this organism expresses this enzyme"

enzyme_reactions           id UUID PK, enzyme_id FK->enzymes,
                           substrate_id FK->compounds, product_id FK->compounds,
                           UNIQUE(enzyme_id, substrate_id, product_id)
                           -- "this enzyme converts substrate to product" (from a KEGG reaction)

fermentation_type_organisms
                           id UUID PK, fermentation_type TEXT NOT NULL, organism_id FK->organisms,
                           is_default BOOLEAN NOT NULL DEFAULT true,
                           UNIQUE(fermentation_type, organism_id)
                           -- fermentation_type validated at ingestion time against
                           -- stages.STAGE_MACHINES.keys() | {"kefir", "vinegar"} —
                           -- the same set BatchIngredient/Ingredient already use.

batch_organisms            id UUID PK, batch_id FK->batches (cascade delete, matches
                           Batch.measurements/reminders/batch_ingredients), organism_id FK->organisms,
                           source TEXT NOT NULL DEFAULT 'custom', notes TEXT NULL,
                           created_at TIMESTAMPTZ DEFAULT now
                           -- a row here for a batch overrides/extends that batch's
                           -- organism set; a batch with zero rows uses the
                           -- fermentation_type_organisms default for its culture.type.
```

`source_version` on the three reference tables tracks which frozen snapshot loaded the row (e.g. `"kegg_biochem_v1"`), the same provenance discipline as `IngredientNutrient.source_version` — so a future re-ingest is traceable and reversible.

### KEGG ingestion (offline, frozen — mirrors `scripts/build_fdc_catalog.py`)

`scripts/build_kegg_biochem.py` calls KEGG's public REST API (`https://rest.kegg.jp`, no key required) for the fermentation-relevant pathways and writes a frozen snapshot `src/fermenttrack/kegg_biochem_v1.json.gz` (gzip, `mtime=0`, byte-reproducible — same discipline as the FDC snapshot):

- **Pathways pulled:** glycolysis (`ko00010`), ethanol/alcoholic fermentation, lactic acid fermentation, acetate/acetic acid fermentation, starch/amylase pathways (koji), and proteolysis/rennet-relevant enzymes (cheese). This covers kombucha, sourdough, koji, cheese, kefir, miso, vinegar, lacto-ferment, and garum's dominant pathways — not KEGG's full pathway catalog.
- **Per pathway:** enzymes (EC number, name), the compounds each enzyme's reaction consumes/produces, and — where KEGG's organism-linked ortholog data resolves one — the organism(s) known to express that enzyme.
- **Fermentation-type mapping:** a hand-maintained table in the build script (not KEGG data) mapping each of the 9 fermentation types above to its dominant organism(s) — e.g. `kombucha -> [Saccharomyces cerevisiae, Acetobacter aceti, Gluconacetobacter xylinus]`, `sourdough -> [Saccharomyces cerevisiae, Lactobacillus sanfranciscensis]`, `koji/miso -> [Aspergillus oryzae]`, `cheese -> [Lactococcus lactis]`. This mapping is domain knowledge, not something KEGG exposes directly — it's the one hand-curated piece, kept small and explicit in one place.
- Loaded in a single migration data step (this dataset is small — dozens of rows, not thousands — no chunking needed unlike the FDC snapshot).

**As built (v1):** the script fetches only canonical identity from KEGG for a curated set of 5 EC numbers (enzyme names) and 5 compound names (ids and canonical names), not whole pathways. All relations (organism-enzyme, enzyme-reaction, fermentation-type-organism) are hand-curated in `fermenttrack/biochem.py`. The per-pathway and ortholog-derived text above was aspirational and is deferred to a v2 snapshot.

### Read endpoint: `GET /batches/{id}/biochemistry`

Returns, for one batch:
```json
{
  "organisms": [{"id", "name", "kingdom", "source": "default" | "custom"}],
  "enzymes": [{"id", "ec_number", "name"}],
  "compounds": [{"id", "name", "category"}]
}
```
Resolution: if `batch_organisms` has any rows for this batch, those are `organisms`, each tagged `source="custom"` (the column's value on every row inserted via the override endpoint). Otherwise, `organisms` is `fermentation_type_organisms` where `fermentation_type = batch.culture.type` and `is_default`, each tagged `source="default"` in the response (a label added at read time — no `batch_organisms` rows are materialized for the default case). `enzymes` is every `organism_enzymes` row for those organisms; `compounds` is every substrate/product reachable from those enzymes via `enzyme_reactions`, deduplicated.

### Custom organism override: `GET /organisms?q=` and `POST /batches/{id}/organisms`

- `GET /organisms?q=<text>` — same shape as the existing `GET /foods` search (case-insensitive substring match on `name`, limit default 20/max 50) — lets the frontend (next increment) look up an organism already in the reference table (e.g. a specific commercial strain already seeded) to attach to a batch.
- `POST /batches/{id}/organisms` — body `{organism_id, notes}`. Inserts a `batch_organisms` row with `source="custom"`. 404 if `organism_id` doesn't exist.
- **Out of scope for this increment:** adding a brand-new organism that isn't already in the `organisms` table (e.g. a commercial strain KEGG doesn't catalog). That needs its own small reference-data-entry path, deferred until there's a real case for it — YAGNI until Achille actually buys a strain not already seeded.

### Testing

- **Snapshot sanity** (reading the real gz): every `fermentation_type` in the hand-maintained mapping resolves to at least one organism; every organism referenced by the mapping exists in `organisms`; no orphan `enzyme_reactions` (both `substrate_id`/`product_id` exist).
- **Pure build function:** unit test on a small synthetic KEGG response fixture, covering EC-number parsing and the fermentation-type-to-organism mapping.
- **`/batches/{id}/biochemistry`:** default case (no `batch_organisms` rows) returns the fermentation-type defaults; override case (one `batch_organisms` row) returns only that; 404 for unknown batch.
- **`/organisms` search + `POST /batches/{id}/organisms`:** search match/limit, successful override insert, 404 for unknown `organism_id`.
- **Migration 0008:** SQLite round-trip (upgrade, downgrade to 0007, upgrade); Postgres check through the deployed API after the Render deploy, per the existing pattern (Docker unavailable locally).

### Out of scope

- Frontend UI panel — next increment, once this data exists and is stable.
- Adding organisms not already in the seeded reference table (see above).
- BRENDA enzyme kinetics (Km, optimal pH/temp) — noted below as a future feature-enrichment source, not built now.
- FooDB flavor/volatile compound data — richer than KEGG's compound set for flavor prediction specifically; future expansion.
- Full NCBI Taxonomy sync — `ncbi_taxon_id` is stored per organism for future compatibility (matches the taxon-ID convention `fermentgraph`'s own microbe data already uses) but nothing consumes it yet.
- Reconciling with `fermentgraph`'s `FermentationPriors` if its own trigger ever fires — would join via a future `canonical_id`, same pattern as `Ingredient`, not built now.

### Alternatives considered / later expansion

Recorded here so a future session doesn't have to re-derive them:

- **BRENDA** — deepest per-enzyme data (kinetics, EC number, organism specificity, optimal pH/temp). A dedicated `brenda-database` skill is already available in this environment. Worth adding once the predictive model wants enzyme-*activity* features (e.g. "how fast does this amylase work at this temperature"), not just presence/absence.
- **FooDB** (foodb.ca) — food-specific flavor/volatile compound data, richer than KEGG for "what does this actually taste/smell like." No skill wraps it here; would need a plain bulk download, evaluated separately.
- **NCBI Taxonomy** — canonical taxon IDs, already reserved as a column (`organisms.ncbi_taxon_id`) but not synced yet.
- **`fermentgraph`** — remains a "don't use yet" dependency per `DEPENDENCIES.md`, independent of this spec. If its hygiene/trigger conditions are ever met, its `associated_microbes`/`associated_compounds` export (already scoped in `fermentgraph-evolution.md`) could reconcile against these same tables via a `canonical_id`, mirroring how `Ingredient.canonical_id` is reserved today.
- **v2 curation (2026-09-24)** — additive second snapshot (koji/miso/kefir/vinegar/CO2 gaps, LDH correction): see `2026-09-24-biochemistry-v2-curation-draft.md`, shipped as `kegg_biochem_v2.json.gz` + migration 0009.

### Outbound calls

`scripts/build_kegg_biochem.py` makes read-only HTTP calls to KEGG's public REST API (`rest.kegg.jp`) at build time only — no API key, no data sent, same category as the FDC bulk download already approved for the USDA catalog work. No Nestlé or batch data is involved; this is a one-time offline fetch of public reference biochemistry data, frozen into the repo.
