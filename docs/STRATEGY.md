# FermentTrack Strategic Plan

> **3 Synergistic Directions for Open-Source Dominance**

---

## The Opportunity

FermentTrack sits at the intersection of three massive tailwinds:

1. **Fermentation renaissance** — $3.25B kombucha market (13.7% CAGR), 48.6% CAGR precision fermentation
2. **Developer-fermenter archetype** — 4,137⭐ on "baking the programmer way," 867⭐ iSpindel
3. **Zero unified tooling** — 89 fermentation-tagged repos, zero cross-substrate platforms

The timing is analogous to the **pre-LangChain era for LLMs**: the cultural wave is mature (kombucha in every Whole Foods, Stanford 2021 microbiome study), but the developer tooling layer is nascent and fragmented.

---

## Three Directions (Mutually Reinforcing)

```
FermentJSON (standard) → attracts ecosystem
     ↓                        ↑
Sensor Hub (data)    → feeds → Knowledge Engine (intelligence)
     ↑                        ↓
     └── differentiates ← ────┘
```

---

## Direction 1: 🌐 FermentJSON — The Open Data Standard

**Vision:** Create the universal exchange format for fermentation data beyond beer.

### Why

BeerJSON (160⭐, MIT) exists for beer but provides **zero domain-specific fields** for kombucha, koji, cheese, miso, vinegar, or kefir. Its culture types list yeast strains but have no `Aspergillus`, no SCOBY, no acetobacter. Kombucha gets the exact same schema as beer.

### Schema Architecture

```
FermentJSON
├── Core (universal: temperature, duration, pH, organism, substrate)
├── Extensions (type-specific: kombucha, koji, cheese, vinegar, beer)
├── Sensor Streams (time-series from hardware devices)
├── Outcomes (tasting notes, measurements, success/failure)
└── Ontology Links (optional FoodOn IDs for scientific users)
```

### Type-Specific Extensions (The Key Innovation)

**Kombucha:** `scoby_weight`, `pellicle_health`, `starter_ratio`, `tea_type`, `f2_duration`
**Koji:** `spore_coverage`, `humidity`, `enzyme_targets`, `temperature_profile`
**Cheese:** `rennet_type`, `pressing_weight`, `aging_humidity`, `rind_treatment`
**Vinegar:** `mother_weight`, `starting_alcohol`, `target_acidity`, `oxygenation`

### Strategic Value

- Every tool that adopts FermentJSON links back to FermentTrack's GitHub org
- Hardware vendors (iSpindel, Tilt) who adopt need the reference implementation
- University food science labs who reference it in papers cite FermentTrack
- Scientific users get optional `organism.ncbi_taxon_id` + `substrate.foodon_id` links to FermentGraph

### "Show HN" Launch Angle

> "Show HN: FermentJSON — An open data standard for fermentation beyond beer (kombucha, koji, cheese, miso)"

---

## Direction 2: 🔌 Sensor Hub — "Home Assistant for Fermentation"

**Vision:** Become the canonical self-hosted data destination for fermentation sensors.

### Why

Today's fermentation IoT stack: `Sensor → MQTT → InfluxDB → Grafana (generic dashboards)`. Nobody provides **fermentation-domain context** — knowing it's "German Lager batch #12 at diacetyl rest" not just "sensor ID 2E6753."

### Plugin Architecture

Modeled on Home Assistant's manifest + DataUpdateCoordinator + HACS registry:

```python
# Example: iSpindel plugin — entire implementation
from fermenttrack.plugin_sdk import FermentTrackPlugin, webhook_handler

class iSpindlePlugin(FermentTrackPlugin):
    @webhook_handler(path="/ispindel")
    async def handle_post(self, data: dict) -> FermentationReading:
        return FermentationReading(
            gravity_sg=data.get("gravity"),
            temperature_c=data.get("temperature"),
            battery_v=data.get("battery"),
        )
```

### Verified Sensor Ecosystem

| Sensor | Protocol | Difficulty |
|--------|----------|-----------|
| **iSpindel** (867⭐) | HTTP POST JSON | Easy |
| **GravityMon** (93⭐) | HTTP POST + MQTT | Easy |
| **Tilt Hydrometer** | BLE iBeacon | Medium (needs bridge) |
| **Pioreactor** (140⭐) | MQTT native | Medium |
| **Inkbird/Govee** | BLE advertising | Hard (per-vendor) |

### CraftBeerPi4's Gap We Fill

CraftBeerPi4 has plugins but **no marketplace UI** — users must SSH in and run pip commands. FermentTrack ships a HACS-style one-click plugin store from day one.

### Self-Hosted Positioning

```yaml
# One command to run everything
docker compose up -d
```

Target: r/selfhosted (1.5M subscribers). Tandoor Recipes reached 8,375⭐ through this channel.

---

## Direction 3: 🧠 Knowledge-Powered Intelligence (The FermentGraph Moat)

**Vision:** Layer FermentGraph's compound knowledge graph underneath the tracker for intelligence no competitor can replicate.

### Why This Is Unreplicable

FermentGraph provides:
- Curated source coverage across 5+ databases with explicit provenance
- Bronze → Silver → Gold materialization ensuring data quality
- Food-context → compound retrieval and evidence-ranked suggestions
- Leakage-aware benchmark evaluation
- Graph-first modelling directions (KGE, GNN) for future expansion

**No other tracker has a scientific knowledge graph underneath.**

### Progressive Feature Disclosure

| Phase | Feature | Pricing |
|-------|---------|---------|
| 1 | "What organisms are in my ferment?" | Free |
| 2 | "What compounds might my batch produce?" | Free |
| 3 | "Similar batches reached target by day 7" | Pro |
| 4 | "Try adjusting temp by 2°C — evidence suggests..." | Pro |
| 5 | Flavor trajectory prediction | Pro |

### Research Paper

> "FermentGraph: An Evidence-Ranked Knowledge Graph for Artisan Fermentation Intelligence"

Target: JOSS (Journal of Open Source Software) — creates a permanent citation loop. Researchers find the paper → find the tool → star the repo → contribute.

---

## Open-Source Strategy

### License

**Apache 2.0** for all core components:
- Maximum adoption (enterprises pre-cleared)
- Explicit patent grant (MIT lacks this)
- Scientific tools precedent (OpenFermion)
- Open-core model for commercial features later

### GitHub Organization

```
fermenttrack/fermentjson       — The data standard
fermenttrack/fermenttrack      — Batch tracker + sensor hub
fermenttrack/plugin-ispindel   — Community plugin example
fermenttrack/plugin-tilt       — Community plugin example
fermenttrack/docs              — Documentation site (MkDocs Material)
```

### Community Targets (Ranked by Reachability)

| Community | Size | Strategy |
|-----------|------|----------|
| **BrewBlox/BrewPi** | 5,700+ topics | Post plugin announcement |
| **iSpindel users** | 867⭐ | PR to add FermentTrack as output target |
| **r/Koji** | ~25-30K | "First open-source koji batch tracker" |
| **r/selfhosted** | 1.5M+ | Docker-native positioning |
| **Hacker News** | Millions | "FermentJSON: open standard" |
| **hendricius** | 4,137⭐ | Tag for sourdough features |

---

## 12-Month Roadmap

```
MONTH 1     FermentJSON v0.1 spec + batch logger MVP
MONTH 2     iSpindel/GravityMon plugin + Docker stack + 🚀 LAUNCH
MONTH 3     Tilt plugin + community feedback + docs site
MONTH 4     FermentGraph "What's in my ferment?" (free intelligence)
MONTH 5     Plugin SDK release + first community plugin
MONTH 6     "Similar batches" analog retrieval (pro feature)
MONTH 7     JOSS paper submission + conference talk
MONTH 8     Plugin store (HACS-style) + mobile PWA polish
MONTH 9     Experiment suggestions (pro feature)
MONTH 10    Commercial hosted tier announcement
MONTH 11    Multi-ferment: kombucha → koji → cheese
MONTH 12    v2.0 launch with full FermentGraph intelligence
```

---

## Revenue Model (Updated)

```
Open Source:   Batch journal, 3 cultures, iSpindel/Tilt plugins, FermentJSON
Pro (€9/mo):   Unlimited cultures, FermentGraph intelligence, analog retrieval
Team (€29/mo): Multi-user, compliance records, API access, priority support
Hosted (€5/mo): Cloud-hosted instance (Nabu Casa model for non-self-hosters)
```

**Path to €500/mo:** ~55 Pro users or ~17 Team users or ~100 Hosted

---

## Kill Criteria (Unchanged)

Stop if:
- Users won't log for 2-3 consecutive batches
- <3 users prepay after seeing the workflow demo
- Retention drops below 30% at day 14
- FermentJSON gets zero stars after 4 weeks on HN/Reddit

---

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | FastAPI (Python) | Shared ecosystem with FermentGraph |
| Database | PostgreSQL + TimescaleDB | Time-series batch + sensor data |
| Frontend | React + TailwindCSS (PWA) | Mobile-friendly, installable |
| Messaging | Embedded Mosquitto (MQTT) | Sensor push protocol |
| Plugin SDK | `fermenttrack.plugin_sdk` | Home Assistant-inspired |
| Hosting | Docker Compose (self-hosted) | Primary install method |
| Photos | S3-compatible | Cheap, scalable |
| Intelligence | FermentGraph (Python pkg) | Direct library dependency |

---

## Next Immediate Actions

1. **This week:** Draft `fermentjson/schema/core.json` (v0.1)
2. **This week:** Implement iSpindel webhook endpoint in FastAPI
3. **Next week:** Plugin SDK base class + manifest spec
4. **Week 3:** Docker Compose full stack (FermentTrack + Postgres + Mosquitto)
5. **Week 4:** Prepare Show HN post + r/fermentation announcement

---

*See also:*
- [ARCHITECTURE.md](ARCHITECTURE.md) — Technical domain model and API design
- [IDEATION_CONTEXT.md](IDEATION_CONTEXT.md) — 10-loop validation journey
- [FermentGraph Vision](https://github.com/Achillethin/fermentgraph/blob/main/docs/FERMENTTRACK_VISION.md) — How FermentGraph powers FermentTrack
