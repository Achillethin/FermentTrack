# FermentTrack

**A batch journal and smart reminder app for serious fermenters.**

> Never lose or ruin a batch again.

FermentTrack helps fermenters managing 3+ active cultures track batches, get stage-aware reminders, compare outcomes, and learn what works — powered by [FermentGraph](https://github.com/Achillethin/fermentgraph) intelligence.

## Why

| Problem | FermentTrack Solution |
|---------|----------------------|
| Forgot to feed my starter | Stage-aware reminders (feed, burp, bottle, flip) |
| "What did I do differently last time?" | Batch comparison with photos + notes |
| Scattered notes across apps | One place for all ferments |
| No tools for kombucha/koji/cheese | Purpose-built for non-beer fermentation |
| "What should I try next?" | Experiment suggestions from FermentGraph knowledge |

## Target Users

1. **Serious home fermenters** — 3+ active cultures (kombucha, sourdough, koji, cheese, miso, kefir)
2. **Micro-producers** — small batch consistency, light compliance records
3. **Fermentation educators** — workshop tracking, student batches

## Architecture

```
┌─────────────────────────────────────────────────┐
│              FermentTrack App                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐ │
│  │  Batch   │  │ Reminder │  │  Comparison   │ │
│  │  Logger  │  │  Engine  │  │  & Insights   │ │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘ │
│       │              │                │          │
│  ┌────▼──────────────▼────────────────▼───────┐ │
│  │           Core Data Layer                   │ │
│  │  (batches, cultures, measurements, photos)  │ │
│  └────────────────────┬───────────────────────┘ │
└───────────────────────┼─────────────────────────┘
                        │ optional enrichment
┌───────────────────────▼─────────────────────────┐
│            FermentGraph Engine                    │
│  - Compound knowledge graph                      │
│  - Context-based analog retrieval                │
│  - Evidence-ranked experiment suggestions        │
└─────────────────────────────────────────────────┘
```

## MVP Scope (8 weeks)

### Ships ✅
- **One ferment type first** (kombucha — clear stages, time-sensitive)
- Batch creation wizard (substrate, starter, vessel, target)
- Stage-aware reminders (1F → 2F → bottling → ready)
- Photo timeline per batch
- pH / temperature / tasting notes logging
- Compare two batches side-by-side
- Simple export (PDF / CSV)

### Doesn't ship yet ❌
- Multi-ferment platform (koji, cheese, miso — phase 2)
- ML predictions or FermentGraph integration (phase 3)
- Sensors / IoT integration
- Community features / recipe sharing
- Mobile app (web-first, PWA)

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | Python (FastAPI) | Shared ecosystem with FermentGraph |
| Database | PostgreSQL + TimescaleDB | Time-series batch data |
| Frontend | React + TailwindCSS (PWA) | Mobile-friendly, installable |
| Auth | Supabase Auth or Auth0 | Fast to implement |
| Storage | S3-compatible (photos) | Cheap, scalable |
| Hosting | Railway / Render | Easy deploy, low ops |
| Payments | Stripe | Standard for SaaS |
| FermentGraph | Python package import | Direct library dependency |

## Revenue Model

```
Free tier:     3 active cultures, basic reminders
Pro (€9/mo):   Unlimited cultures, batch comparison, export, insights
Team (€29/mo): Multi-user, batch sharing, compliance records
```

**Path to €500/mo:** ~55 Pro users or ~17 Team users

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
| 0 | Week 1-2 | Validate: mock report + interviews with 10 fermenters |
| 1 | Week 3-8 | MVP: kombucha tracker with reminders + comparison |
| 2 | Month 3-4 | Expand: koji, sourdough, cheese support |
| 3 | Month 4-6 | Intelligence: FermentGraph integration for suggestions |
| 4 | Month 6+ | Growth: community, batch sharing, micro-producer features |

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
- [Ideation Sprint Results](docs/IDEATION_CONTEXT.md) — How this idea was validated through 10-loop multi-agent research

## License

MIT
