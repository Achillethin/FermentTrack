# Experiment Logging, Ingredient Reference Data & Preview UI — Design

**Revised 2026-09-18** after a 3-agent review panel (product/vision, technical pragmatism, cross-repo sequencing). Original version bundled four independent increments into one design with two real blockers (unbounded sync mechanism, premature compound/microbial UI exposure). Both fixed below — see "What changed" at the end.

## Purpose

Phase 1's domain model (`Culture`/`Batch`/`Measurement`/`Reminder`) supports batch journaling and reminders but has no structured way to record *what went into* a batch (a recipe) — and `README.md`'s own second use case, *"What did I do differently?"*, is unanswerable without one; you can't diff free-text notes. This design adds recipe logging and a minimal preview UI. It does **not** add a compound/microbial knowledge panel yet — see section 2.

Three independently-shippable increments, in this order:
1. **`Ingredient`/`BatchIngredient` domain model** (FermentTrack backend, kombucha-scoped, zero cross-repo dependency — start immediately)
2. **`GET /batches/{id}/preview` endpoint** (depends on 1; presentation-shaped, no compound/microbial data)
3. **Minimal React/Vite PWA frontend + deployment** (depends on 2)

A fourth item — the FermentGraph compound/microbial export — is **deferred**, not an increment of this spec. See "Deferred" section.

## 1. `Ingredient` / `BatchIngredient` — Domain Model

### `Ingredient` (new table, FermentTrack-owned, no FermentGraph dependency)

```python
class Ingredient(Base):
    id: UUID
    canonical_id: str | None    # nullable for now — populated only once/if the deferred
                                 # FermentGraph export lands (section "Deferred"); a v1
                                 # hand-seeded ingredient has no upstream ID yet.
    name: str
    default_role: str           # "base" | "starter" | "flavoring" | "additive"
                                 # FermentTrack-curated — "role in a recipe" is a culinary
                                 # concept, not a food-science one.
    fermentation_systems: list[str]   # e.g. ["kombucha"] — substrates this is used in
    is_active: bool = True      # soft-deprecation flag; see "Deferred" for why deletes
                                 # are never hard in this table
```

### Seed data — kombucha only for v1

MVP substrate scope (`STRATEGY.md`) is kombucha. Seeding six substrates' worth of ingredients now, before sourdough/koji/cheese stage machines exist, is scope ahead of the phase gate — trimmed to what v1 actually uses:

| Ingredient | `default_role` |
|---|---|
| Black/green tea | `base` |
| Water | `base` |
| Cane sugar | `base` |
| SCOBY / starter liquid | `starter` |
| Fresh ginger, fruit, herbs, spices | `flavoring` |

The broader multi-substrate table (sourdough, koji, cheese, kefir, miso, vinegar) from the original draft is preserved as reference for whoever picks up Phase 2 multi-ferment support — not seeded now:

<details>
<summary>Phase 2 reference (not implemented in this increment)</summary>

| Ingredient | `default_role` | Substrate(s) |
|---|---|---|
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

</details>

### `BatchIngredient` (new table — the "recipe")

```python
class BatchIngredient(Base):
    id: UUID
    batch_id: UUID              # FK -> batches.id
    ingredient_id: UUID         # FK -> ingredients.id
    quantity: float | None
    unit: str | None            # "g", "ml", "tsp", ...
    role: str                   # copied from Ingredient.default_role AT INSERT TIME,
                                 # editable per batch. Never re-derived on Ingredient
                                 # update/sync — a later edit to Ingredient.default_role
                                 # must not retroactively change historical batches'
                                 # displayed role. This is a genuine override column,
                                 # not a duplicate of Ingredient state (e.g. sugar as
                                 # `flavoring` in a second-ferment rather than the
                                 # primary `base`).
```

### `Measurement` — unchanged

No schema break, no new result-type enum. Existing `type`/`value_numeric`/`value_text`/`notes` already covers pH, temperature, brix, gravity, sensory notes.

## 2. `GET /batches/{id}/preview` — Aggregate Endpoint

Returns, in one payload: batch header (culture, current stage, days in stage), recipe (`BatchIngredient` list), results timeline (`Measurement` history), and the safety advisory report (existing `/batches/{id}/safety` logic, already built and tested — reused, not duplicated).

**No compound/microbial data in this endpoint.** `STRATEGY.md` already states the rule this would otherwise violate: *"Do not market 'knowledge-graph intelligence' as a current feature."* A labeled "unvalidated" panel on FermentTrack's first-ever UI screen is still a panel a user notices — that's marketing it as a current feature regardless of the disclaimer. This gets revisited only when Direction 3's trigger fires (fermentgraph's ranker beats the popularity baseline by ≥+0.05 Recall@50, per `docs/DEPENDENCIES.md`).

**Scope ceiling, stated explicitly so this doesn't grow unbounded:** `preview` is presentation-shaped, owned by this one frontend page's needs. Any future consumer that isn't this page uses the underlying `/timeline` and `/safety` endpoints directly — it does not get a new field bolted onto `preview`.

## 3. Frontend — Minimal React/Vite PWA

One page: Batch Preview, consuming `GET /batches/{id}/preview` in a single call.

Tech: Vite + React + TailwindCSS (per `STRATEGY.md`), `vite-plugin-pwa` for manifest + service worker from day one. API base URL via build-time env var.

**Deployment:**
- Frontend: `npm run build` → static assets → GitHub Pages via GitHub Actions.
- Backend: managed free-tier host (Render, or Fly.io as an alternative) running FastAPI + Postgres.
- Backend CORS allows the GH Pages origin.

Cross-origin (GH Pages + separate host) was chosen over same-origin (serving the SPA build as static files from FastAPI itself, which would need zero CORS config) because GH Pages gives a stable public URL under your existing GitHub identity without tying the frontend's availability to the backend host's uptime — worth the one extra CORS line for that decoupling.

## Testing

- `Ingredient`/`BatchIngredient`: CRUD tests, role-copy-at-insert-then-override test (create with default, PATCH to override, confirm it persists independent of later `Ingredient.default_role` edits) — matching the existing `test_mark_reminder_done_and_snooze`-style pattern in `tests/`.
- `preview` endpoint: 404 case; empty-recipe case (batch with zero `BatchIngredient` rows); populated case. No compound/microbial case, since that data doesn't exist in this endpoint.
- Frontend: component test for the preview page against a mocked API response — no e2e infra for this first slice.

## Deferred: FermentGraph compound/microbial export

**Not part of this spec's implementation plan.** Gated on the same Direction 3 trigger as the rest of FermentGraph's Knowledge Engine (`STRATEGY.md`): fermentgraph's ranker beating the popularity baseline by ≥+0.05 Recall@50.

When that trigger fires, the actual build is cheaper than originally scoped — verified against fermentgraph's real code: `associated_microbes` is **pure composition of two already-existing methods**, `FermentationPriors.systems_for_food()` (`fermentation.py:222`) and `system(name).microbes` (`:241`, populated from `fermentation_systems.yaml` at `:189` — real per-system microbe data with NCBI taxon IDs, not a stub). No new curation work needed in fermentgraph. This means: when the trigger fires, building the export is a thin serialization script, not a modeling task.

At that point: `Ingredient.canonical_id` gets populated from the export (currently nullable, unused). Sync is an explicit upsert-by-`canonical_id`, never a delete — a renamed/merged upstream ID gets a new row; the old `Ingredient` row is marked `is_active = False`, never removed, so historical `BatchIngredient` rows never orphan. `docs/specs/fermentgraph-evolution.md` carries the full requirement and this same deferral note.

## Out of scope

- Logging real sequencing/lab results for microbial communities (reference knowledge only, per earlier decision — and now deferred entirely, see above).
- Multi-page frontend, auth, payments, Docker Compose self-host packaging of the frontend.
- Native mobile app (PWA install covers "installable on mobile" for now).
- Sourdough/koji/cheese/kefir/miso/vinegar ingredient seeding (Phase 2, reference table preserved above).

**Open question for the product owner, raised by review but not resolved here:** `STRATEGY.md`'s MVP scope lists FermentJSON v0.1 export and Docker Compose self-hosting as "Ships" items still not built (iSpindel webhook and Safety Advisory *are* already shipped). This spec's UI work is legitimate — nothing else in the product is visible without any frontend at all — but whether it should ship before or after those two MVP items is a priority call, not a design-quality one. Flagging it; not blocking on it.

## What changed in this revision

- Cut the FermentGraph export + compound/microbial UI panel from "now" work to "deferred" — was risking the exact overclaiming `docs/DEPENDENCIES.md` already caught once.
- Trimmed ingredient seed data from six substrates to kombucha-only, matching the actual MVP phase gate; preserved the rest as Phase 2 reference.
- Split the original four bundled sub-projects into three independent increments plus one deferred item, instead of one monolithic design.
- Specified the sync mechanism precisely (upsert by `canonical_id`, never delete, `is_active` soft-deprecation) instead of leaving it for implementation to improvise.
- Added an explicit scope ceiling on the `preview` endpoint.
- Clarified `role` is copied at insert time, never re-derived.
- Expanded the testing section from one line per area to specific cases.
- Verified (not assumed) that the deferred FermentGraph export needs zero new curation — it's composition of existing methods.
