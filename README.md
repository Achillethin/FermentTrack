# FermentTrack 🧫

**The open-source intelligence platform for fermentation.**

> Track every batch. Connect every sensor. Learn from every ferment.

FermentTrack is the first open-source platform that combines **batch journaling**, **sensor integration** (iSpindel, Tilt, GravityMon), and **knowledge-graph intelligence** — for every substrate, not just beer. Powered by [FermentGraph](https://github.com/Achillethin/fermentgraph).

```bash
docker compose up -d  # Self-hosted. Your data, your hardware, forever.
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

### 🧠 Knowledge Engine — The FermentGraph Moat
A scientific compound knowledge graph underneath your batch tracker. "What's happening in my ferment?" → "Similar batches reached target pH by day 7" → "Try adjusting temperature by 2°C — evidence suggests..." No other tracker has this.

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
- **Kombucha batch logger** (clear stages, time-sensitive — best first substrate)
- Batch creation wizard (substrate, starter, vessel, target)
- Stage-aware reminders (1F → 2F → bottling → ready)
- Photo timeline per batch
- pH / temperature / tasting notes logging
- **iSpindel/GravityMon webhook** (live sensor data → batch timeline)
- **FermentJSON v0.1 export** (kombucha + koji extensions)
- Compare two batches side-by-side
- Docker Compose self-hosted deployment
- Simple export (PDF / CSV / FermentJSON)

### Phase 2 (Month 3-6)
- Multi-ferment: koji, cheese, miso, kefir, vinegar
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
| Hosting | Docker Compose (self-hosted) | Primary install method |
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

## How FermentGraph Adds Value

FermentTrack works standalone as a journal. FermentGraph enriches it:

1. **"What's happening in my ferment?"** — Compound suggestions based on substrate + time + temperature
2. **"What should I try next?"** — Evidence-ranked experiment suggestions from the knowledge graph
3. **"Is this normal?"** — Analog retrieval: "similar batches typically reach pH 3.5 by day 7"
4. **Confidence scores** — Every suggestion shows provenance and evidence quality

The integration is optional and progressive: users get value from day 1 (reminders), graph intelligence layers in over time.

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

```bash
# Clone
git clone git@github-personal:Achillethin/FermentTrack.git
cd FermentTrack

# Setup
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run
uvicorn src.fermenttrack.main:app --reload
```

## Related

- [FermentGraph](https://github.com/Achillethin/fermentgraph) — Intelligence engine (knowledge graph, compound ranking, experiment suggestions)
- [Strategic Plan](docs/STRATEGY.md) — 3 directions for open-source dominance (full research synthesis)
- [Architecture](docs/ARCHITECTURE.md) — Technical domain model, API design, database schema
- [Ideation Sprint](docs/IDEATION_CONTEXT.md) — How this idea was validated through 10-loop multi-agent research

## License

Apache-2.0
