"""Pydantic v2 request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ── Culture ──────────────────────────────────────────────────────────────

class CultureCreate(BaseModel):
    name: str
    type: str = "kombucha"
    born_from: uuid.UUID | None = None
    status: str = "active"
    style: str | None = None  # sourdough: the starter's levain type (catalogue key)

    @field_validator("style")
    @classmethod
    def _known_style(cls, v: str | None) -> str | None:
        from fermenttrack.prediction.sourdough import STYLES

        if v is not None and v not in STYLES:
            raise ValueError(f"unknown levain style {v!r}")
        return v


class CultureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    born_from: uuid.UUID | None
    status: str
    created_at: datetime
    style: str | None = None


class CultureWithBatches(CultureOut):
    batches: list["BatchOut"] = []


class BatchExportOut(BaseModel):
    """Full-fidelity batch data for GET /me/export — unlike BatchOut, includes
    the child rows so an account's data can be exported/reimported wholesale."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    started_at: datetime
    current_stage: str
    target: str | None
    expected_temperature_c: float | None
    outcome: str
    ended_at: datetime | None
    measurements: list["MeasurementOut"] = []


class CultureExportOut(CultureOut):
    batches: list[BatchExportOut] = []


# ── Batch ────────────────────────────────────────────────────────────────

# °C. The upper bound also catches the most likely slip, a Fahrenheit room temperature
# (68-80 °F), which read as °C would be far outside any home-fermentation range.
ExpectedTemperatureC = Annotated[float, Field(ge=-5.0, le=60.0)]


class BatchCreate(BaseModel):
    culture_id: uuid.UUID
    target: str | None = None
    expected_temperature_c: ExpectedTemperatureC | None = None
    sourdough_plan: "SourdoughPlanIn | None" = None


class BatchUpdate(BaseModel):
    """Partial update: only fields present in the body change; an explicit null clears."""

    target: str | None = None
    expected_temperature_c: ExpectedTemperatureC | None = None
    sourdough_plan: "SourdoughPlanIn | None" = None


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    culture_id: uuid.UUID
    started_at: datetime
    current_stage: str
    stage_entered_at: datetime
    target: str | None
    expected_temperature_c: float | None
    outcome: str
    ended_at: datetime | None
    sourdough_plan: dict[str, Any] | None = None


class StageAdvance(BaseModel):
    """Optional explicit target stage; if omitted, advances to the next stage."""

    stage: str | None = None


# ── Measurement ──────────────────────────────────────────────────────────

class MeasurementCreate(BaseModel):
    type: str
    value_numeric: float | None = None
    value_text: str | None = None
    notes: str | None = None


class MeasurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    measured_at: datetime
    type: str
    value_numeric: float | None
    value_text: str | None
    notes: str | None


# ── Note ─────────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    text: str


# ── Reminder ─────────────────────────────────────────────────────────────

class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    action: str
    due_at: datetime
    repeat_interval: timedelta | None
    urgency: str
    completed_at: datetime | None


class ReminderSnooze(BaseModel):
    until: datetime


# ── Ingredient ───────────────────────────────────────────────────────────

class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canonical_id: str | None
    name: str
    default_role: str
    fermentation_systems: list[str]
    is_active: bool


# ── USDA catalog ─────────────────────────────────────────────────────────

class FdcFoodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fdc_id: int
    description: str
    data_type: str  # "SR Legacy" | "Foundation"
    category: str | None


# ── BatchIngredient ──────────────────────────────────────────────────────

# Closed set so composition can convert every new row to grams. Rows logged
# before this existed may hold free text; composition reports them as unquantified.
Unit = Literal["g", "kg", "mg", "ml", "L"]
Role = Literal["base", "flavoring", "additive", "starter"]


class BatchIngredientCreate(BaseModel):
    """Exactly one of ingredient_id (curated, strict ferment check) or fdc_id (USDA catalog)."""

    ingredient_id: uuid.UUID | None = None
    fdc_id: int | None = None
    quantity: float | None = None
    unit: Unit | None = None
    role: Role | None = None  # if omitted, copied from Ingredient.default_role

    @model_validator(mode="after")
    def _exactly_one_source(self) -> BatchIngredientCreate:
        if (self.ingredient_id is None) == (self.fdc_id is None):
            raise ValueError("give exactly one of ingredient_id or fdc_id")
        return self


class BatchIngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    ingredient_id: uuid.UUID
    quantity: float | None
    unit: str | None
    role: str


class BatchIngredientUpdate(BaseModel):
    """Partial update: only fields present in the body change; an explicit null clears."""

    quantity: float | None = None
    unit: Unit | None = None
    role: Role | None = None


# ── Composition ─────────────────────────────────────────────────────────

class NutrientTotalOut(BaseModel):
    nutrient: str
    grams: float
    per_100g: float
    missing_from: list[str]  # mapped ingredients with no reported value: unknown, not 0


class SaltSuggestionOut(BaseModel):
    """Default salt to pre-fill in the recipe form; never logged automatically."""

    pct: float
    basis_g: float
    grams: float


class BatchCompositionOut(BaseModel):
    """Starting composition from the recipe × USDA FDC reference data.

    Every figure is a lower bound when coverage < 1 or a nutrient's
    missing_from is non-empty. salt_pct is added salt (Salt rows) / total mass;
    None = salt not logged, 0 = logged 0 g.
    """

    total_mass_g: float
    mapped_mass_g: float
    coverage: float
    salt_pct: float | None
    salt_suggestion: SaltSuggestionOut | None
    nutrients: list[NutrientTotalOut]
    unmapped: list[str]
    unquantified: list[str]


# ── Timeline / compare ──────────────────────────────────────────────────

class TimelineEvent(BaseModel):
    kind: str  # "measurement" | "note" | "stage_change"
    timestamp: datetime
    detail: dict


class BatchTimeline(BaseModel):
    batch: BatchOut
    events: list[TimelineEvent]


class BatchCompare(BaseModel):
    batches: list[BatchOut]
    measurements: dict[str, list[MeasurementOut]]


class BatchSummaryOut(BaseModel):
    """One row of a batch list/search result: batch + its culture, flattened."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    culture_id: uuid.UUID
    culture_name: str
    culture_type: str
    started_at: datetime
    current_stage: str
    stage_entered_at: datetime
    target: str | None
    outcome: str
    ended_at: datetime | None


# ── Safety ───────────────────────────────────────────────────────────────
# Moved here from routers/safety.py so routers/batches.py's preview endpoint
# can reuse the same response shape without importing another router module.

class RuleVerdictOut(BaseModel):
    rule_id: str
    triggered: bool
    action: str
    reason_code: str
    reason_text_en: str
    reason_text_fr: str
    source_citation: str


class SafetyReportOut(BaseModel):
    safe: bool
    hard_stops: list[RuleVerdictOut]
    warnings: list[RuleVerdictOut]
    rules_evaluated: int
    rules_triggered: int
    summary_en: str
    summary_fr: str


# ── Preview ──────────────────────────────────────────────────────────────
# Presentation-shaped for the (future) batch-preview UI page. Scope ceiling:
# owned by that one page's needs — any other consumer uses /timeline,
# /safety, and /biochemistry directly rather than extending this. No
# organism/enzyme/compound data here: that's GET /batches/{id}/biochemistry
# (docs/superpowers/specs/2026-09-23-fermentation-biochemistry-design.md),
# a separate endpoint, not folded into this one — same scope-ceiling
# reasoning as /timeline and /safety already getting their own endpoints.

class BatchPreview(BaseModel):
    batch: BatchOut
    culture: CultureOut
    days_in_stage: float
    recipe: list[BatchIngredientOut]
    timeline: list[TimelineEvent]
    safety: SafetyReportOut


# ── Biochemistry ─────────────────────────────────────────────────────────
# Reference data for fermentation organisms/enzymes/compounds, sourced from
# KEGG. See docs/superpowers/specs/2026-09-23-fermentation-biochemistry-
# design.md — this reverses the 2026-09-18 UI deferral for compound/
# microbial data (that deferral was about presenting fermentgraph's
# unvalidated heuristic priors as intelligence; KEGG is a different,
# citable provenance). fermentgraph itself remains a "don't use yet"
# dependency per docs/DEPENDENCIES.md, untouched by this reversal.

class OrganismOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kingdom: str
    ncbi_taxon_id: str | None
    kegg_organism_code: str | None


class CompoundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    kegg_compound_id: str | None


class BiochemOrganismOut(BaseModel):
    id: uuid.UUID
    name: str
    kingdom: str
    source: Literal["default", "custom"]
    notes: str | None  # only for custom attachments; None for pure type defaults


class BiochemEnzymeOut(BaseModel):
    id: uuid.UUID
    ec_number: str
    name: str
    organism_ids: list[uuid.UUID]  # resolved organisms carrying this enzyme, by organism name


class BatchBiochemistryOut(BaseModel):
    organisms: list[BiochemOrganismOut]
    enzymes: list[BiochemEnzymeOut]
    compounds: list[CompoundOut]


class BatchOrganismCreate(BaseModel):
    organism_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def _strip_notes(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v is not None else None


class BatchOrganismOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    organism_id: uuid.UUID
    source: str
    notes: str | None


# ── Prediction ───────────────────────────────────────────────────────────
# GET /batches/{id}/prediction. A model estimate, never a measurement: see
# docs/superpowers/specs/2026-09-24-fermentation-prediction-design.md for the model,
# its priors and the labelling rules. Shape built by fermenttrack.prediction.service.

class PredictionModelOut(BaseModel):
    name: str
    version: str
    method: str
    members: int
    effective_members: float
    confidence: Literal["established", "exploratory"]
    confidence_note: str | None  # why an exploratory forecast is only a sketch
    validated: bool
    sources: list[str]


class PredictionTemperatureOut(BaseModel):
    forecast_c: float
    source: Literal["override", "expected", "measured", "type_default"]
    type_default_c: float
    range_c: list[float]
    readings: int


class PredictionSeriesOut(BaseModel):
    key: str  # "ph", "lactic_acid", "pop:<organism>", "mycelium", ...
    label: str
    unit: str  # "" | "g/kg" | "log CFU/g" | "SG" | "°Bx" | "%"
    group: Literal[
        "ph", "density", "substrates", "products", "growth", "population", "rise", "acidity"
    ]
    t_h: list[float]
    p05: list[float]
    p50: list[float]
    p95: list[float]


class PredictionObservationOut(BaseModel):
    key: str
    t_h: float
    value: float
    used: bool
    fits: bool | None  # used readings: within what the calibrated ensemble explains


class MilestoneTimesOut(BaseModel):
    p05: float | None
    p50: float | None
    p95: float | None


class MilestoneThresholdOut(BaseModel):
    series: str
    value: float
    kind: str


class PredictionMilestoneOut(BaseModel):
    key: str
    label: str
    title: str
    note: str
    threshold: MilestoneThresholdOut
    t_h: MilestoneTimesOut  # hours from batch start; null = not reached by the horizon
    probability: float  # weighted share of the ensemble reaching it within the horizon


class ReferenceLineOut(BaseModel):
    series: str
    value: float
    label: str


class PathwayOut(BaseModel):
    label: str
    ec_numbers: list[str]
    in_reference_graph: bool  # a marker enzyme is linked to this organism in KEGG data


class PredictionOrganismOut(BaseModel):
    name: str
    kingdom: str
    modelled: bool
    growing: bool
    role: str
    note: str | None
    series_key: str | None
    pathways: list[PathwayOut]
    sources: list[str]


class PredictionInitialOut(BaseModel):
    source: Literal["recipe", "typical_recipe", "plan"]
    values: dict[str, float]


class PredictionOut(BaseModel):
    model: PredictionModelOut
    fermentation_type: str
    started_at: datetime  # UTC; t_h values are hours since this
    now_h: float
    horizon_h: float
    horizon_options_h: list[float]
    temperature: PredictionTemperatureOut
    status: Literal["prior_only", "calibrated"]
    series: list[PredictionSeriesOut]
    observations: list[PredictionObservationOut]
    milestones: list[PredictionMilestoneOut]
    reference_lines: list[ReferenceLineOut]
    organisms: list[PredictionOrganismOut]
    initial: PredictionInitialOut
    assumptions: list[str]
    warnings: list[str]
    disclaimer: str
    # sourdough plans: the phases (levain, bulk, proof) and the plan's derived figures
    phases: list["PhaseOut"] = []
    summary: dict[str, Any] | None = None


# ── Sourdough ────────────────────────────────────────────────────────────
# Planner and tracked sourdough batches share one plan schema (prediction.sourdough).

Grams = Annotated[float, Field(ge=0.0, le=200_000.0)]
DoughTempC = Annotated[float, Field(ge=-5.0, le=45.0)]


class SourdoughBuildIn(BaseModel):
    seed_g: Annotated[float, Field(gt=0.0, le=100_000.0)]
    flour_g: Annotated[float, Field(gt=0.0, le=200_000.0)]
    water_g: Grams
    flour: dict[str, float] | None = None  # {flour key: share}; null = the style's flour
    temperature_c: DoughTempC
    hours: Annotated[float, Field(gt=0.0, le=72.0)] | None = None


class SourdoughDoughIn(BaseModel):
    flour_g: Annotated[float, Field(gt=0.0, le=200_000.0)]
    water_g: Grams
    salt_g: Grams = 0.0
    flour: dict[str, float] | None = None
    temperature_c: DoughTempC
    levain_g: Annotated[float, Field(gt=0.0, le=200_000.0)] | None = None
    yeast_g: Grams = 0.0
    yeast: Literal["instant", "fresh"] = "instant"
    dried_sour_g: Grams = 0.0
    bulk_hours: Annotated[float, Field(gt=0.0, le=48.0)] | None = None
    target_rise_pct: Annotated[float, Field(gt=0.0, le=300.0)] = 75.0


class SourdoughProofIn(BaseModel):
    temperature_c: DoughTempC
    hours: Annotated[float, Field(gt=0.0, le=96.0)]


class SourdoughPlanIn(BaseModel):
    style: str
    starter: Literal["ripe", "refrigerated"] = "ripe"
    culture_id: uuid.UUID | None = None  # planner only: use this starter's learned kinetics
    levain: SourdoughBuildIn | None = None
    dough: SourdoughDoughIn | None = None
    proof: SourdoughProofIn | None = None

    @model_validator(mode="after")
    def _valid_plan(self) -> "SourdoughPlanIn":
        from fermenttrack.prediction.sourdough import plan_from_dict

        plan_from_dict(self.model_dump(mode="json", exclude={"culture_id"}))  # ValueError -> 422
        if self.dough is not None and self.dough.salt_g > 0.1 * self.dough.flour_g:
            raise ValueError("salt above 10 % of the dough flour: check the grams")
        return self


class PhaseOut(BaseModel):
    key: str
    label: str
    start_h: float
    end_h: float
    temperature_c: float


class FeedingChartIn(BaseModel):
    style: str
    flour: dict[str, float] | None = None
    hydration_pct: Annotated[float, Field(ge=20.0, le=300.0)] = 100.0
    temperature_c: Annotated[float, Field(ge=5.0, le=40.0)]
    starter: Literal["ripe", "refrigerated"] = "ripe"
    culture_id: uuid.UUID | None = None
    ratios: Annotated[
        list[Annotated[float, Field(ge=0.2, le=50.0)]], Field(min_length=1, max_length=10)
    ] = [1.0, 2.0, 3.0, 5.0, 8.0, 10.0]


class FeedingChartRowOut(BaseModel):
    ratio: float
    label: str
    peak_h: MilestoneTimesOut
    doubled_h: MilestoneTimesOut
    ph_at_peak: float
    rise_at_peak_pct: float


class FeedingChartOut(BaseModel):
    temperature_c: float
    style: str
    rows: list[FeedingChartRowOut]


CultureWithBatches.model_rebuild()


# ── Logbook (GET /me/log) ────────────────────────────────────────────────

class LogCultureOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str


class LogBatchOut(BaseModel):
    id: uuid.UUID
    current_stage: str
    started_at: datetime


class LogEntryOut(BaseModel):
    # Source row id: Measurement.id (readings, notes and logged stage changes), or Batch.id for
    # the synthesized stage-change of a batch without logged history — clients must key on
    # kind + id, not id alone.
    id: uuid.UUID
    culture: LogCultureOut
    batch: LogBatchOut
    kind: Literal["measurement", "note", "stage-change"]
    timestamp: datetime
    detail: dict


BatchCreate.model_rebuild()
BatchUpdate.model_rebuild()
PredictionOut.model_rebuild()
