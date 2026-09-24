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
| "What should I try next?" | FermentGraph-powered experiment suggestions |
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
2. **"What should I try next?"** — Evidence-ranked experiment suggestions from the knowledge graph
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

Then open `http://127.0.0.1:8000/docs` for the interactive API explorer (FastAPI's auto-generated Swagger UI) — create a culture, start a batch, log a measurement, and hit `/batches/{id}/safety` to see the Safety Advisory in action. There's no frontend yet (see the [experiment-logging design spec](docs/superpowers/specs/2026-09-18-experiment-logging-design.md) for the planned minimal UI) — this is API-only for now.

## Related

- [FermentGraph](https://github.com/Achillethin/fermentgraph) — Intelligence engine (knowledge graph, compound ranking, experiment suggestions)
- [Dependency Decisions](docs/DEPENDENCIES.md) — Audited use-now/use-later/don't-use verdicts for fermentgraph, the digital twin, and the control POC
- [Strategic Plan](docs/STRATEGY.md) — 5 directions for open-source dominance (full research synthesis)
- [Architecture](docs/ARCHITECTURE.md) — Technical domain model, API design, database schema
- [Ideation Sprint](docs/IDEATION_CONTEXT.md) — How this idea was validated through 10-loop multi-agent research

## License

Apache-2.0
