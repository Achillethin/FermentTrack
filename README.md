# FermentTrack 🧫

**The open-source intelligence platform for fermentation.**

> Track every batch. Connect every sensor. Learn from every ferment.

FermentTrack is the first open-source platform that combines **batch journaling**, **sensor integration** (iSpindel, Tilt, GravityMon), and **knowledge-graph intelligence** — for every substrate, not just beer. Powered by [FermentGraph](https://github.com/Achillethin/fermentgraph).

**Primary distribution is a hosted PWA** (installable web app, works on mobile without an app-store build) — a free-tier managed backend + a GitHub Pages frontend, so anyone can use it via a link, not a server setup. Self-hosting via Docker remains supported for anyone who wants it, but it is not the primary way most users will run FermentTrack.

```bash
# Optional: self-host instead of using the hosted instance
docker compose up -d
```

## Why

| Problem | FermentTrack Solution |
|---------|----------------------|
| Forgot to feed my starter | Stage-aware reminders (feed, burp, bottle, flip) |
| "What did I do differently?" | Batch comparison with photos + notes |
| Scattered notes across apps | One place for all ferments |
| No tools for kombucha/koji/cheese | Purpose-built for non-beer fermentation |
| "What should I try next?" | [Ideas](#ideas--fermentation-recommender): recipes and a fermentation window from a curated, cited library, plus model-guided variants (not validated) |
| Sensors log to generic Grafana | Fermentation-native sensor hub with domain context |
| No data standard beyond beer | FermentJSON — open format for all fermentation data |

## Three Pillars

### 🌐 FermentJSON — The Open Data Standard
The universal exchange format for fermentation data beyond beer. Kombucha gets `scoby_weight` and `pellicle_health`. Koji gets `spore_coverage` and `humidity`. BeerJSON only serves beer — FermentJSON serves everyone.

### 🔌 Sensor Hub — "Home Assistant for Fermentation"
Plugin-based sensor integration. iSpindel, Tilt, GravityMon, Pioreactor — all normalized into one timeline. HACS-style plugin store. Docker self-hosted.

### 🛡️ Safety Advisory — real today
Cited food-safety rules (EFSA/ANSES/CDC) evaluated against your batch's own logged measurements — e.g. flags a low-salt lacto-ferment held too warm before it becomes a botulism risk. Vendored from a tested digital-twin/safety-rule engine, not a research promise.

### 📈 Fermentation Forecast — model estimate, clearly labelled
A mechanistic kinetic model (Monod growth, cardinal temperature/pH/salt models, charge-balance pH) compiled from each batch's organisms, recipe (USDA) and estimated fermentation temperature, with literature priors and uncertainty bands, re-calibrated on the pH/gravity readings you log. Forecasts pH, sugars, acids, ethanol, populations and milestones ("pH below 4.6 in ~3 days"), with a what-if temperature slider. Not validated against real batches yet and never a safety decision — see [`docs/superpowers/specs/2026-09-24-fermentation-prediction-design.md`](docs/superpowers/specs/2026-09-24-fermentation-prediction-design.md).

### 🧠 Knowledge Engine — deferred, research-stage
Originally scoped as a FermentGraph-powered compound knowledge graph ("similar batches reached target pH by day 7"). An audit (2026-09-17) found the suggestion/analog API this depended on doesn't exist yet and the underlying ranker doesn't beat a trivial baseline — see [`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md). Not marketed as a current feature; revisit once FermentGraph's ranking actually works.

## Ideas — fermentation recommender

The **Ideas** page (`#/ideas`) starts from what you have and what you'd like to notice, and returns recipes with a fermentation time. Give any of:
- **ingredients**, which every recipe must include (salt, water, sugar, flour, tea and starter cultures are always allowed);
- **1–3 target aromas or tastes**, from the 16 aroma series plus sour, sweet, umami and alcohol;
- or both.

Results come in up to three sections of at most 3 cards each, one card per parent recipe:

- **Proven:** a curated, cited recipe from the library, kept inside its documented envelope. The library has 20 active recipes over 9 ferment types; 7 of them are sourdough styles.
- **Experimental:** a library recipe, one of your own batches or a community recipe, changed by up to 3 operators:
  - add a flavouring at a sourced use level;
  - swap an ingredient for one with the same role;
  - move the temperature within the model's range;
  - add a USDA food, labelled "aroma effect unknown".
- **Community — not proven:** recipes other users published from their own finished batches, after an admin's review.

**On each card:**
- a full recipe, scaled to your batch size;
- a **time window** (taste from / peak / stop by) at a stated temperature, with a slider that re-runs the forecast live;
- **Start batch**, which creates the culture, the batch, its ingredients and its reminders in one step. Sourdough cards open the levain planner instead.

**Search deeper** queues a background job of up to 20 live forecasts, which takes a few minutes. You can leave the page; the results are kept.

**Labels and limits:**
- Every card says "Model-guided idea" and "model estimate, not validated". Cards rank by the model's probability that a compound family is noticeable, and the wording is "likely noticeable", never "tastes like".
- **Scores show as Low / Med / High.** Numbers, labelled "calibrated on *n* batches", appear only while the calibration gate passes. It needs at least 30 tasted batches started from cards, and the model has to beat a per-type baseline on what tasters noticed (Brier score) and tell noticed from not noticed within each type and series (AUC). It runs weekly, and the numbers turn off again if it fails or its last pass is more than 14 days old. The Ideas page shows the gate's state, for example "Not calibrated yet: 12 of 30 tasted batches", with the reason when the gate fails for something other than too few batches (such as "no type and series has both noticed and not-noticed ratings yet"). Moving a card's slider or confirming it drops its numbers and the "calibrated" label, since they belong to the card as served.
- **Every card carries the safety lines of its type's barrier:**
  - pH lines for ferments made safe by acidity (lacto, kombucha, kefir, cheese, vinegar);
  - the bed-temperature line for koji;
  - "do not reduce the salt" for miso and garum;
  - none for sourdough, where baking is the barrier.
- **A recipe that fails a rule checkable from the recipe** (salt %, temperature limits) is never shown, in any mode.
- **It is never a safety decision:** a predicted pH is not clearance. Measure pH.

**Tasting feedback:**
- Start batch adds a reminder at the stop-by time to fill in a tasting form: 0–3 per aroma or taste, liking 1–5, "make again" and notes. The form asks first about the targets of the card the batch was started from.
- Any batch can be tasted.
- Tastings feed the calibration gate, and the community cards' "made *n*×" and mean liking. A mean liking shows only once 3 people have given one.

**Frontend routes:**

| route | page |
|---|---|
| `#/ideas` | inputs, the three sections, Search deeper |
| `#/batch/<id>/tasting` | the batch page with its tasting form open |
| `#/admin/community` | the community review queue (admins) |

A finished, successful batch can be published from its Recipe tab. Your published recipes are listed on `#/account`.

**API** (all need a signed-in user, the hosted frontend's anonymous sessions included, unless marked otherwise):

| endpoint | what |
|---|---|
| `GET /recipes?type=&status=active`, `GET /recipes/{key}` | the recipe library; **no token needed** |
| `POST /recommendations` | the cards; `mode` is `proven`, `experimental` or `both` |
| `POST /recommendations/forecast` | one card's live 64-member forecast (the slider; confirming a screened variant) |
| `POST /recommendations/deep-search` | queue a search: 202 `{job_id}`; 200 for your finished job of the same request; 409 while one of yours is queued or running |
| `GET /recommendations/jobs`, `GET /recommendations/jobs/{id}` | your 10 newest searches; one search's progress and cards (yours only) |
| `GET /recommendations/calibration` | the latest calibration report, aggregates only: scores are hidden below 30 batches, and a reliability bin's values until its ratings come from 3 distinct batches; 404 before the first one |
| `POST /batches/from-recommendation` | Start batch: 201; 409 with a `planner_link` for sourdough |
| `POST /batches/{id}/tastings`, `GET /batches/{id}/tastings`, `DELETE /batches/{id}/tastings/{tasting_id}` | a batch's tastings (its owner only) |
| `POST /community-recipes` | publish a finished, successful, tasted batch; it waits for review |
| `GET /me/community-recipes` | your published recipes, every status (the export path for them) |
| `GET /admin/community-recipes?status=pending`, `POST /admin/community-recipes/{id}/approve`, `POST /admin/community-recipes/{id}/reject` | the review queue (admins) |
| `GET /admin/calibration`, `POST /admin/calibration/recompute` | the full calibration report; recompute now (admins) |

`GET /me/export` includes each batch's tastings.

**Configuration:**
- `FERMENTTRACK_ADMIN_USER_IDS`: comma-separated Supabase user ids (the JWT `sub`) that may review community recipes and read the full calibration report. The same list gives read-only access to every account's logbook. `GET /me` shows your id and whether you are an admin.
- `FERMENTTRACK_CANDIDATES_PATH=<file>` (optional): appends each fresh live forecast of an Experimental variant to that file, one JSON object per line, as candidates for the next recommender grid or emulator training set. That covers a confirmed screened card, a search-deeper step, and a variant of your batch or of a community recipe. Records carry no ids. Unset (the default), nothing is written; a write failure is logged and never fails the request.

The job worker, the startup re-forecast of community recipes and the weekly calibration all run inside the API process, which assumes a single process (Render's free plan).

**Browser storage:**
- The recommender keeps one key in the browser: `ft.deep-search.hidden`, the finished search you hid, so it isn't offered again. The levain planner keeps its own `ft.levain.form.v1` and `ft.levain.pro`.
- Tasting targets are not stored in the browser. The batch preview (`GET /batches/{id}/preview`) carries `recommendation_targets`, the target keys of the card the batch was started from: `[]` when the card had none, `null` when the batch wasn't started from a card. The tasting form asks about those first.
- Signing out clears every `ft.*` key on the device. So does starting a session for a different account than the one that left the keys, which `ft.owner` records (`frontend/src/storage.js`: `clearAppKeys`, `claimAppKeys`). A guest who adds an email keeps the same account and keeps their keys.

**Rebuilding the library and the grid:** the library (`src/fermenttrack/recommender/recipes_v1.csv`, `recipe_ingredients_v1.csv`) and the precomputed grid (`recommender_grid_v1.npz` and its manifest) are committed artefacts.

```bash
python scripts/build_recipes.py                      # rewrite the library from the research drafts and the curation decisions
python scripts/build_recipes.py --check              # exit 1 if the committed library differs from a fresh build
python scripts/build_recommender_grid.py --workers 4 # rebuild the grid (188 entries, ~178 kB, ~8.5 min on 4 workers)
```

`tests/test_recommender_grid.py::test_grid_is_current` fails with that last command when any grid input changes: the profiles, the aroma catalogue and data, the recipe files or the use levels. `test_a_rebuilt_entry_matches_the_committed_one` re-solves one entry per ferment type, to catch engine changes. Commit the rebuilt grid with the change; approved community recipes are re-forecast at the next startup. To add an ingredient, see [`docs/ADDING_AN_INGREDIENT.md`](docs/ADDING_AN_INGREDIENT.md).

**Migrations 0019–0023** add, in order:
- `recommendation_links` (and `reminders.kind`);
- `recommendation_jobs`;
- `community_recipes` and `community_recipe_forecasts`;
- `tastings` (and `recommendation_links.p_series`);
- `calibration_reports`.

`alembic upgrade head` applies them.

**Specs:**
- [design](docs/superpowers/specs/2026-10-07-fermentation-recommender-design.md), whose § 17 holds the implementation notes and measured results;
- [recipe curation](docs/superpowers/specs/2026-10-07-recipe-curation.md);
- [adding an ingredient](docs/ADDING_AN_INGREDIENT.md).

## Target Users

1. **Serious home fermenters** — 3+ active cultures (kombucha, sourdough, koji, cheese, miso, kefir)
2. **Micro-producers** — small batch consistency, light compliance records
3. **Fermentation educators** — workshop tracking, student batches

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              FERMENTTRACK PLATFORM                            │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐ │
│  │  Batch   │  │ Reminder │  │  Sensor   │  │  Plugin   │ │
│  │  Logger  │  │  Engine  │  │   Hub     │  │   Store   │ │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └─────┬─────┘ │
│       │              │              │              │          │
│  ┌────▼──────────────▼──────────────▼──────────────▼───────┐ │
│  │           Core Data Layer (FermentJSON native)           │ │
│  │  PostgreSQL + TimescaleDB | MQTT Broker | Plugin SDK     │ │
│  └────────────────────────────┬────────────────────────────┘ │
└───────────────────────────────┼──────────────────────────────┘
                                │ intelligence enrichment
┌───────────────────────────────▼──────────────────────────────┐
│              FERMENTGRAPH ENGINE                               │
│  - Compound knowledge graph (Bronze→Silver→Gold pipeline)     │
│  - Context-based analog retrieval                             │
│  - Evidence-ranked experiment suggestions                     │
│  - Graph ML directions (KGE, GNN, foundation models)          │
└───────────────────────────────────────────────────────────────┘
```

## MVP Scope (8 weeks)

### Ships ✅
- **Multi-substrate batch logger** — kombucha, sourdough, koji, cheese all have stage-aware reminders from v1 (not kombucha-only — see `docs/superpowers/specs/2026-09-18-experiment-logging-design.md`); kefir/miso/vinegar get recipe logging without stage automation until their state machines are documented
- Recipe logging (`Ingredient`/`BatchIngredient`) — structured record of what went into a batch, across all substrates above
- Batch creation wizard (substrate, starter, vessel, target)
- Stage-aware reminders (per-substrate progressions, e.g. kombucha's 1F → 2F → bottling → ready)
- Photo timeline per batch
- pH / temperature / tasting notes logging
- Estimated fermentation temperature per batch, and a fermentation forecast (`GET /batches/{id}/prediction`)
- **Ideas: a fermentation recommender** (Proven / Experimental / Community cards with a time window, tasting feedback; see [below](#ideas--fermentation-recommender))
- **iSpindel/GravityMon webhook** (live sensor data → batch timeline)
- **FermentJSON v0.1 export** (kombucha + koji extensions)
- Compare two batches side-by-side
- Hosted PWA (web + mobile-installable) — primary distribution; Docker Compose self-hosting supported as an alternative
- Simple export (PDF / CSV / FermentJSON)

### Phase 2 (Month 3-6)
- Miso/kefir/vinegar stage-aware reminders (recipe logging for these already works in v1; only the stage-reminder automation is deferred)
- Tilt Hydrometer plugin (BLE bridge container)
- Plugin SDK + HACS-style plugin store
- FermentGraph "What's in my ferment?" (free intelligence)
- "Similar batches" analog retrieval (pro feature)
- JOSS paper submission

### Phase 3 (Month 6-12)
- Experiment suggestions from FermentGraph (pro)
- Mobile PWA polish
- Commercial hosted tier
- Community-contributed plugins
- Full FermentGraph intelligence layer (v2.0)

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | Python (FastAPI) | Shared ecosystem with FermentGraph |
| Database | PostgreSQL + TimescaleDB | Time-series batch + sensor data |
| Messaging | Embedded Mosquitto (MQTT) | Sensor push protocol |
| Frontend | React + TailwindCSS (PWA) | Mobile-friendly, installable |
| Plugin SDK | `fermenttrack.plugin_sdk` | Home Assistant-inspired |
| Hosting | Managed host (Render/Fly.io) + GH Pages frontend | Primary — shareable via a link, no setup required; Docker Compose self-hosting remains supported as an alternative |
| Storage | S3-compatible (photos) | Cheap, scalable |
| Payments | Stripe | Standard for SaaS |
| Intelligence | FermentGraph (Python pkg) | Direct library dependency |

## Revenue Model

```
Open Source:    Batch journal, 3 cultures, sensor plugins, FermentJSON export
Pro (€9/mo):    Unlimited cultures, FermentGraph intelligence, analog retrieval
Team (€29/mo):  Multi-user, compliance records, API access, priority support
Hosted (€5/mo): Cloud instance for non-self-hosters (Nabu Casa model)
```

**Path to €500/mo:** ~55 Pro users or ~17 Team users or ~100 Hosted

## How FermentGraph Would Add Value (once it works)

FermentTrack works standalone as a journal. The plan was for FermentGraph to enrich it — this is not built yet (see [`docs/DEPENDENCIES.md`](docs/DEPENDENCIES.md) for the audit):

1. **"What's happening in my ferment?"** — Compound suggestions based on substrate + time + temperature
2. **"What should I try next?"** — Evidence-ranked experiment suggestions from the knowledge graph (FermentTrack now answers a model-guided version of this question without FermentGraph: [Ideas](#ideas--fermentation-recommender))
3. **"Is this normal?"** — Analog retrieval: "similar batches typically reach pH 3.5 by day 7"
4. **Confidence scores** — Every suggestion shows provenance and evidence quality

What ships in Phase 1 instead: a **Safety Advisory** built on a vendored, tested, literature-cited rule engine (see Direction 4 in [`docs/STRATEGY.md`](docs/STRATEGY.md)) — real value from day 1 without waiting on FermentGraph's ranker to clear its promotion bar.

## Data Flywheel

```
User logs batch data
    → Aggregate anonymized patterns
        → Improve FermentGraph predictions
            → Better suggestions for all users
                → More trust → more logging → repeat
```

## Development Roadmap

| Phase | Timeline | Focus |
|-------|----------|-------|
| 0 | Week 1-2 | FermentJSON v0.1 spec + batch logger MVP |
| 1 | Week 3-4 | iSpindel/GravityMon plugin + Docker stack |
| 2 | Month 2 | 🚀 **LAUNCH** — Show HN + r/fermentation + r/selfhosted |
| 3 | Month 3-4 | Tilt plugin, koji/cheese support, docs site |
| 4 | Month 4-6 | FermentGraph intelligence (free + pro features) |
| 5 | Month 6-8 | Plugin SDK + store, JOSS paper, PWA polish |
| 6 | Month 9-12 | Commercial hosted tier, v2.0 full intelligence |

## Kill Criteria

Stop if:
- Users won't log for 2-3 consecutive batches
- <3 users prepay after seeing the workflow demo
- Retention drops below 30% at day 14

## Getting Started (Development)

The app targets Postgres in production, but for local development a SQLite file works with zero setup — no database server needed:

```bash
# Clone
git clone git@github-personal:Achillethin/FermentTrack.git
cd FermentTrack

# Setup
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Point at a local SQLite file instead of Postgres (skip this to use the
# Postgres default — you'd need a server running at the URL in config.py)
export FERMENTTRACK_DATABASE_URL="sqlite:///./fermenttrack.db"   # Windows: set FERMENTTRACK_DATABASE_URL=...

# Create tables and seed the 20 reference ingredients
alembic upgrade head

# Run
uvicorn fermenttrack.main:app --reload
```

Every non-health endpoint requires a Supabase Auth bearer token (see "Auth" below) — the Swagger UI's "Authorize" button accepts one. There's no frontend yet against a local backend (the deployed frontend at `docs/superpowers/specs/2026-09-24-biochemistry-ui-design.md` talks to the hosted API) — this is API-only for local dev.

## Auth

Cultures (and everything under them — batches, measurements, reminders) are scoped to a Supabase Auth user id (`Culture.owner_id`, the JWT `sub`). The backend needs to know how to verify the Supabase access token:

- `FERMENTTRACK_SUPABASE_URL=https://<project-ref>.supabase.co` — required for current Supabase projects, which sign access tokens with an asymmetric key (ES256/RS256). The public keys are read from `<url>/auth/v1/.well-known/jwks.json` and cached. This is the project URL, not the Postgres connection string.
- `FERMENTTRACK_SUPABASE_JWT_SECRET` — optional; only for projects still signing with the legacy HS256 secret (Project Settings → API → JWT Secret).

On Render, set `FERMENTTRACK_SUPABASE_URL` on the API service; the JWT secret can stay unset. With neither set every request gets `503 Auth not configured`. The hosted frontend signs visitors in anonymously (`frontend/src/auth.js`) — no signup wall — so get a token for local API testing the same way: a Supabase anonymous sign-in returns `session.access_token`.

## Related

- [FermentGraph](https://github.com/Achillethin/fermentgraph) — Intelligence engine (knowledge graph, compound ranking, experiment suggestions)
- [Dependency Decisions](docs/DEPENDENCIES.md) — Audited use-now/use-later/don't-use verdicts for fermentgraph, the digital twin, and the control POC
- [Strategic Plan](docs/STRATEGY.md) — 5 directions for open-source dominance (full research synthesis)
- [Architecture](docs/ARCHITECTURE.md) — Technical domain model, API design, database schema
- [Ideation Sprint](docs/IDEATION_CONTEXT.md) — How this idea was validated through 10-loop multi-agent research

## License

Apache-2.0
