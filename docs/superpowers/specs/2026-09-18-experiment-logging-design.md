# Experiment Logging, Ingredient Reference Data & Preview UI — Design

## Purpose

Phase 1's domain model (`Culture`/`Batch`/`Measurement`/`Reminder`) supports batch journaling and reminders but has no structured way to record *what went into* a batch (a recipe), no richer result types beyond flat measurements, and no way to preview a batch's compound/microbial context. This design adds those, defines the resulting contract FermentGraph must satisfy, and specifies a minimal preview UI — FermentTrack's first frontend.

Four sub-projects, in dependency order:
1. Domain model additions (FermentTrack backend)
2. FermentGraph export contract (new requirement on the `fermentgraph` sibling repo)
3. Minimal React/Vite PWA frontend (batch preview page)
4. Deployment (GH Pages + managed backend host)

## 1. Domain Model Additions

### `Ingredient` (new table, FermentTrack-owned)

A local reference table, **not** a live call into FermentGraph (FermentGraph is a Python library/pipeline today, not a running service — see `docs/DEPENDENCIES.md`; turning it into one is out of scope here). Populated by periodically importing FermentGraph's export (section 2).

```python
class Ingredient(Base):
    id: UUID
    canonical_id: str          # stable ID from FermentGraph's export, e.g. FoodOn-linked
    name: str
    foodon_id: str | None       # optional, for scientific users
    default_role: str           # "base" | "starter" | "flavoring" | "additive"
                                 # FermentTrack-curated, NOT sourced from FermentGraph —
                                 # "role in a recipe" is a culinary concept, not a
                                 # food-science one; FermentGraph's taxonomy won't encode it.
    fermentation_systems: list[str]   # e.g. ["kombucha", "kefir"] — which substrates this
                                       # ingredient is typically used in
```

Seed data at launch covers all documented substrates (not kombucha-only), matching `ARCHITECTURE.md`'s stage state machines:

| Ingredient | `default_role` | Substrate(s) |
|---|---|---|
| Black/green tea, water | `base` | Kombucha |
| Cane sugar | `base` | Kombucha, water kefir |
| SCOBY / starter liquid | `starter` | Kombucha |
| Fresh ginger, fruit, herbs, spices | `flavoring` | Kombucha, kefir |
| Flour, water | `base` | Sourdough |
| Starter/levain | `starter` | Sourdough |
| Rice/grain/soybean | `base` | Koji, miso |
| Koji spores (*A. oryzae*) | `starter` | Koji, miso |
| Milk | `base` | Cheese, kefir |
| Rennet, starter/cheese culture | `starter` | Cheese |
| Kefir grains | `starter` | Kefir |
| Wine/cider/base alcohol | `base` | Vinegar |
| Mother of vinegar (*Acetobacter*) | `starter` | Vinegar |
| Salt, calcium chloride | `additive` | Cheese, koji, miso, sourdough |

### `BatchIngredient` (new table — the "recipe")

```python
class BatchIngredient(Base):
    id: UUID
    batch_id: UUID              # FK -> batches.id
    ingredient_id: UUID         # FK -> ingredients.id
    quantity: float | None
    unit: str | None            # "g", "ml", "tsp", ...
    role: str                   # pre-filled from Ingredient.default_role at creation,
                                 # editable per batch (e.g. sugar as `flavoring` in a
                                 # second-ferment context rather than the primary `base`)
```

### `Measurement` — no schema break, one addition

Existing `type`/`value_numeric`/`value_text`/`notes` stays as-is (covers pH, temperature, brix, gravity, sensory notes already). No new "result type" enum needed — compound/microbial context is *not* stored per-measurement; it's computed at preview time from the batch's `BatchIngredient` list (section 3), since it's reference knowledge about the ingredients used, not an observed result.

## 2. FermentGraph Export Contract

**What FermentGraph must export**, per ingredient/substrate entry:

```json
{
  "schema_version": "1.0",
  "run_id": "curated-gold1",
  "ingredients": [
    {
      "canonical_id": "...",
      "name": "...",
      "foodon_id": "...",
      "fermentation_systems": ["kombucha"],
      "associated_compounds": [
        {"compound_id": "...", "compound_name": "...", "prior_weight": 0.0}
      ],
      "associated_microbes": [
        {"taxon_id": "...", "name": "..."}
      ]
    }
  ]
}
```

- `associated_compounds` sourced from `FermentationPriors.prior_for()` (already exists, already audited — see `docs/DEPENDENCIES.md` section 2).
- `associated_microbes` sourced from `fermentation_systems.yaml` / `FermentationPriors.systems_for_food()` — the accessor for this needs confirming/exposing explicitly in FermentGraph; FermentTrack should not have to infer microbe associations from system names.
- **Non-negotiable, carried over from `docs/DEPENDENCIES.md`:** every compound/microbe association here is a heuristic prior, not a validated prediction. The export's consumer (FermentTrack's UI) must label it "heuristic, unvalidated" wherever shown.

**Delivery:** FermentGraph adds an export script producing this as a versioned JSON artifact. FermentTrack imports it via a one-off/periodic sync script into `ingredients` (+ two join tables for compounds/microbes, or embed as JSON columns — implementation detail for the plan phase). No live network coupling.

This is a new requirement on top of `docs/specs/fermentgraph-evolution.md`'s already-completed hygiene work — to be appended there before implementation starts.

## 3. Frontend — Minimal React/Vite PWA

Scope: **one page**, not a full app — a Batch Preview.

Driven by one new aggregate endpoint: `GET /batches/{id}/preview`, returning:
- Batch header (culture, current stage, days in stage)
- Recipe (`BatchIngredient` list: ingredient, quantity, unit, role)
- Results timeline (`Measurement` history)
- Compound/microbial context — joined from the batch's ingredients against the locally-synced FermentGraph export, labeled "heuristic, unvalidated"
- Safety advisory — the existing `/batches/{id}/safety` report (already built, already tested), surfaced prominently

One call, one page — no client-side orchestration of multiple endpoints for this first slice.

Tech: Vite + React + TailwindCSS (per `STRATEGY.md`'s original plan), `vite-plugin-pwa` for manifest + service worker from day one (installable on mobile, cheap now vs. retrofitting later). API base URL via build-time env var.

## 4. Deployment

- Frontend: `npm run build` → static assets → GitHub Pages via GitHub Actions.
- Backend: managed free-tier host (Render, or Fly.io as an alternative) running FastAPI + Postgres.
- Backend CORS allows the GH Pages origin.
- Frontend's API base URL is a build-time env var pointing at the deployed backend.

## Testing

- Domain model: unit tests for `Ingredient`/`BatchIngredient` CRUD, role pre-fill/override behavior.
- Preview endpoint: integration test asserting the aggregate payload shape, including a case where compound/microbial context is present and correctly labeled unvalidated.
- Frontend: component test for the preview page rendering against a mocked API response (no e2e infra needed for this first slice).
- FermentGraph export: a test asserting the export script's output matches the documented schema (`schema_version`, required fields present) — lives in the `fermentgraph` repo, out of scope for FermentTrack's own test suite.

## Out of scope for this spec

- Logging real sequencing/lab results for microbial communities (deferred — reference knowledge only, per decision during brainstorming).
- Multi-page frontend, auth, payments, Docker Compose self-host packaging of the frontend.
- Native mobile app (PWA install covers "installable on mobile" for now).
