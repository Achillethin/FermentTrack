# Architecture & Design

## System Design

FermentTrack is a **web-first PWA** (Progressive Web App) with a Python backend. It is designed to work standalone but can optionally integrate with FermentGraph for intelligent suggestions.

## Core Domain Model

```
Culture (long-lived entity)
├── name: "Jun SCOBY #3"
├── type: kombucha | sourdough | koji | cheese | kefir | miso | custom
├── born_from: Culture (genealogy)
├── status: active | dormant | retired | shared
└── batches: [Batch, ...]

Batch (one fermentation cycle)
├── culture: Culture
├── started_at: datetime
├── stage: Stage (current)
├── target: "fizzy, tart, ginger-forward"
├── measurements: [Measurement, ...]
├── photos: [Photo, ...]
├── notes: [Note, ...]
└── outcome: success | partial | failed | in_progress

Stage (state machine per ferment type)
├── name: "1F" | "2F" | "bottling" | "conditioning" | "ready"
├── entered_at: datetime
├── expected_duration: timedelta
├── reminders: [Reminder, ...]
└── next_stage: Stage | null

Measurement
├── timestamp: datetime
├── type: pH | temperature | brix | gravity | taste | smell
├── value: float | str
└── notes: str (optional)
```

## Stage State Machines

Each ferment type has a predefined stage progression:

### Kombucha
```
brew_sweet_tea → 1F (7-14 days) → 2F_flavoring (2-4 days) → bottling → conditioning (2-5 days) → ready
```

### Sourdough
```
feed_starter → bulk_ferment (4-12h) → shape → cold_retard (8-24h) → bake → done
```

### Koji
```
soak → steam → inoculate → incubate (36-48h) → harvest → done
```

### Cheese (generic)
```
heat_milk → culture → rennet → cut_curd → cook → press → salt → age → ready
```

## Reminder Engine

Reminders are **stage-aware** and **time-sensitive**:

```python
class Reminder:
    batch: Batch
    stage: Stage
    action: str          # "burp bottles", "check pH", "taste test"
    due_at: datetime     # computed from stage entry + expected duration
    repeat: timedelta    # optional recurring (e.g., "feed every 12h")
    urgency: low | medium | high | critical
```

**Critical reminders** (e.g., "bottling kombucha — over-carbonation risk after day 5") use push notifications.

## API Design (FastAPI)

```
POST   /cultures              Create a new culture
GET    /cultures              List all cultures
GET    /cultures/{id}         Get culture with batches

POST   /batches               Start a new batch
PATCH  /batches/{id}/stage    Advance to next stage
POST   /batches/{id}/measure  Add a measurement
POST   /batches/{id}/photo    Upload a photo
POST   /batches/{id}/note     Add a note
GET    /batches/{id}/timeline Full batch timeline
GET    /batches/compare       Compare two batches side-by-side

GET    /reminders             Upcoming reminders (next 48h)
PATCH  /reminders/{id}/done   Mark reminder complete
PATCH  /reminders/{id}/snooze Snooze reminder

# FermentGraph integration (phase 3)
GET    /suggestions/{batch_id}  Get experiment suggestions for current context
GET    /insights/{batch_id}     Get compound/outcome insights
```

## FermentGraph Integration Layer — DEFERRED

**Correction (2026-09-17):** `generate_suggestions`/`query_analogs` below do not exist in `fermentgraph`'s codebase — they were assumed during the strategy sprint, never verified, and an audit confirmed zero occurrences in `src/`. The evaluated ranker also regresses vs. a popularity baseline and the fermentation-knowledge-prior channel shows a null (0.0000) effect — see [`DEPENDENCIES.md`](DEPENDENCIES.md#2-fermentgraph--dont-use-yet). This layer is **not built** and should not appear in the MVP. Kept here as the target shape for when the trigger in `DEPENDENCIES.md` fires:

```python
# ASPIRATIONAL — not implemented, not available in fermentgraph today.
from fermentgraph.suggestions import generate_suggestions
from fermentgraph.gold import query_analogs

def get_batch_suggestions(batch: Batch) -> list[Suggestion]:
    """Translate batch state into FermentGraph context query."""
    context = {
        "substrate": batch.culture.substrate,
        "organism": batch.culture.organism_type,
        "temperature": batch.latest_temperature,
        "pH": batch.latest_pH,
        "duration_days": batch.days_in_current_stage,
    }
    return generate_suggestions(context)

def get_analog_batches(batch: Batch) -> list[Analog]:
    """Find similar contexts in the knowledge graph."""
    return query_analogs(
        substrate=batch.culture.substrate,
        product_type=batch.culture.type,
        top_k=5,
    )
```

## Safety Advisory Layer — Phase 1, real today

Vendored from the `fermentation` digital-twin repo (Monod twin + AST-based, literature-cited safety rule engine — both tested, both real; see [`DEPENDENCIES.md`](DEPENDENCIES.md#1-fermentation-digital-twin--use-now)). This is more concretely shippable than the FermentGraph layer above and uses data the batch logger already stores:

```python
from fermenttrack.safety.rule_engine import SafetyRuleEngine
from fermenttrack.safety.state import TwinState

def get_safety_report(batch: Batch) -> SafetyReport:
    """Evaluate cited food-safety rules against the batch's latest measurements."""
    state = TwinState(
        scheme=batch.culture.type,
        temperature_c=batch.latest_temperature,
        salt_pct=batch.latest_salt_pct,
        ph=batch.latest_pH,
    )
    return SafetyRuleEngine().evaluate(state.state_vars(), scheme=batch.culture.type)
```

`SafetyReport` carries `.safe`, `.hard_stops`, `.warnings`, and bilingual summaries. Hard-stop findings (e.g. botulism risk) should use the same critical-reminder push-notification path as stage reminders.

## Industrial Control Module — Phase 2+, gated

Soft-sensor biomass estimation from `fermentation-control-poc`, **not** the MPC controller (self-validated against its own simulator, not a real closed-loop result — see [`DEPENDENCIES.md`](DEPENDENCIES.md#3-fermentation-control-poc--use-later-soft-sensor-only)). Blocked on two independent things: (1) the soft sensor being validated on a real fermentation-domain dataset — today it's only validated on industrial penicillin fermentation (IndPenSim), not wine or any beverage/food ferment — and (2) a new dense sensor-stream ingestion path, since this needs online multi-sensor time series at short intervals, not the sparse manual measurements Phase 1's schema captures. Do not build a "control recommendation" UI until MPC is rebuilt on a real constrained solver (do-mpc/CasADi) and validated closed-loop against data it wasn't fit to.

## Database Schema (PostgreSQL)

```sql
CREATE TABLE cultures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    type TEXT NOT NULL,  -- kombucha, sourdough, koji, cheese, kefir, miso, custom
    born_from UUID REFERENCES cultures(id),
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    culture_id UUID NOT NULL REFERENCES cultures(id),
    started_at TIMESTAMPTZ DEFAULT now(),
    current_stage TEXT NOT NULL,
    target TEXT,
    outcome TEXT DEFAULT 'in_progress',
    ended_at TIMESTAMPTZ
);

CREATE TABLE measurements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES batches(id),
    measured_at TIMESTAMPTZ DEFAULT now(),
    type TEXT NOT NULL,  -- pH, temperature, brix, gravity, taste, smell
    value_numeric FLOAT,
    value_text TEXT,
    notes TEXT
);

CREATE TABLE photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES batches(id),
    taken_at TIMESTAMPTZ DEFAULT now(),
    storage_key TEXT NOT NULL,
    caption TEXT
);

CREATE TABLE reminders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES batches(id),
    action TEXT NOT NULL,
    due_at TIMESTAMPTZ NOT NULL,
    repeat_interval INTERVAL,
    urgency TEXT DEFAULT 'medium',
    completed_at TIMESTAMPTZ
);
```

## Non-Functional Requirements

- **Offline-first**: PWA with service worker, sync when online
- **Fast**: <200ms API responses, <3s page loads
- **Mobile-friendly**: Designed for phone-in-kitchen use (wet hands, quick glances)
- **Privacy**: All data per-user, no sharing without explicit opt-in
- **Backup**: Daily automated exports available to user
