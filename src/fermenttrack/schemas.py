"""Pydantic v2 request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


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
    read_only: bool = False  # an admin viewing someone else's batch: no edits


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
        "ph", "density", "substrates", "products", "growth", "population", "rise", "acidity",
        "nutrition", "taste", "aroma",
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
    lens: Literal["process", "taste", "nutrition"] = "process"  # forecast-panel lens


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


class NutritionCellOut(BaseModel):
    p05: float
    p50: float
    p95: float
    lower_bound: bool  # "≥": some ingredient has no data for it


class NutritionRowOut(BaseModel):
    key: str
    label: str
    unit: str
    start: NutritionCellOut | None  # None: unknown (no ingredient reports it)
    now: NutritionCellOut | None
    end: NutritionCellOut | None


class TastePhasesOut(BaseModel):
    vocabulary: list[str]  # ordered, mildest first
    t_h: list[float]
    prob: dict[str, list[float]]  # phase -> weighted share of members in it, per t_h


class AromaSeriesOut(BaseModel):
    # One aromatic series (fruity, sulfurous, ...): the summed odour activity of its compounds.
    key: str
    label: str
    compounds: list[str]
    noticeable: list[float]  # P(series sum above threshold) on taste_phases.t_h
    peak_noticeable: float
    peak_t_h: float


class AromaRouteOut(BaseModel):
    kind: Literal["ingredient", "organism", "chemistry"]
    name: str
    via: str


class AromaThresholdOut(BaseModel):
    p50: float
    lo: float
    hi: float


class AromaCompoundOut(BaseModel):
    key: str
    name: str
    pubchem: str
    chebi: str
    kegg: str
    descriptor: str
    series: list[str]
    tier: str  # calibrated | reported | plausible | engine
    anchor: str
    threshold_basis: str  # measured | class | est | none
    threshold: AromaThresholdOut | None  # µg/kg in water; None: shown as concentration
    ph_corrected: bool
    routes: list[AromaRouteOut]
    peak_noticeable: float | None
    peak_t_h: float | None
    sources: list[str]
    in_series_sum: bool


class NotModelledAromaOut(BaseModel):
    notes: list[str]
    organisms: list[str]
    ingredients: list[str]  # logged ingredients without aroma data yet


class SensoryOut(BaseModel):
    # Taste and nutrition derived from the same ensemble (spec 2026-10-02); model estimates.
    derived_version: str
    validated: bool
    disclaimer: str
    now_h: float
    end_h: float
    taste_phases: TastePhasesOut | None
    nutrition_label: list[NutritionRowOut]
    noticeable: dict[str, dict[str, float]]  # "now"/"end" -> taste -> P(above threshold)
    assumptions: list[str]
    aroma_series: list[AromaSeriesOut] = []
    compounds: list[AromaCompoundOut] = []
    not_modelled_aroma: NotModelledAromaOut | None = None


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
    sensory: SensoryOut | None = None  # taste and nutrition; absent if they failed


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
    owner: str | None = None  # the account (Supabase user id); only on /admin/log


class WhoAmIOut(BaseModel):
    user_id: str
    admin: bool


class AdminCultureOut(CultureOut):
    owner_id: str | None


BatchCreate.model_rebuild()
BatchUpdate.model_rebuild()
PredictionOut.model_rebuild()


# ── Recipe library (GET /recipes, recommender R0) ────────────────────────────


class RecipeSpanOut(BaseModel):
    median: float
    lo: float
    hi: float


class RecipeIngredientOut(BaseModel):
    name: str
    catalogue_status: str
    role: str
    g_per_kg: RecipeSpanOut | None  # None: the source gives no mass (draft recipes only)
    required: Literal["core", "optional"]
    label: str | None
    source: str
    notes: str


class RecipeEnvelopeOut(BaseModel):
    temp_c: RecipeSpanOut | None
    duration_h: RecipeSpanOut | None  # None: the sourdough planner sets the timing
    salt_pct: RecipeSpanOut | None
    sugar_g_per_kg: RecipeSpanOut | None
    temp_schedule: list[tuple[float, float]]  # (start hour, °C) steps; empty: constant
    basis: Literal["sourced", "widened_single_value"]


class RecipeOut(BaseModel):
    key: str
    name: str
    fermentation_type: str
    style_region: str
    status: Literal["active", "draft"]
    provenance: str
    sources: list[str]
    envelope: RecipeEnvelopeOut
    model_scope: list[str]
    labels: list[str]  # trust labels (Q25, Q26); ingredient labels sit on the ingredients
    aerobic: bool
    method: str
    stages: str
    safety_targets: str
    reported_aromas: list[str]
    notes: str
    handoff: Literal["planner"] | None
    planner_style: str | None
    ingredients: list[RecipeIngredientOut]


# ── Recommendations (POST /recommendations, recommender R1) ──────────────────
# Shapes of fermenttrack.recommender.service's plain dicts. Scores are Low / Med / High until
# the calibration gate (design § 13.2); the live forecast also returns E and U.

Level = Literal["Low", "Med", "High"]
TargetKind = Literal["aroma", "taste"]
BatchGrams = Annotated[float, Field(gt=0.0, le=200_000.0)]


def _check_targets(aromas: list[str], tastes: list[str]) -> None:
    from fermenttrack.recommender.service import parse_targets

    parse_targets(aromas, tastes)  # ValueError -> 422


def _check_usda(ids: list[int]) -> None:
    from fermenttrack.recommender.operators import usda_food

    unknown = [i for i in ids if usda_food(i) is None]
    if unknown:
        raise ValueError(f"unknown USDA food id(s): {unknown}")


OperatorKind = Literal["add", "swap", "temperature", "usda"]


class OperatorIn(BaseModel):
    """An Experimental operator as a card's chip sends it back (extra chip fields such as
    `key`, `share` or `label` are ignored: the server recomputes the variant)."""

    op: OperatorKind
    ingredient: Annotated[str, Field(max_length=200)] | None = None  # add, swap, usda by name
    replaces: Annotated[str, Field(max_length=200)] | None = None  # swap
    to_c: ExpectedTemperatureC | None = None  # temperature
    fdc_id: int | None = None  # usda: a USDA food

    @model_validator(mode="after")
    def _valid(self) -> OperatorIn:
        need = {
            "add": ("ingredient",), "swap": ("ingredient", "replaces"), "temperature": ("to_c",)
        }  # fmt: skip
        missing = [f for f in need.get(self.op, ()) if getattr(self, f) is None]
        if self.op == "usda" and self.fdc_id is None and self.ingredient is None:
            missing.append("fdc_id or ingredient")
        if missing:
            raise ValueError(f"a {self.op} operator needs {', '.join(missing)}")
        return self


Operators = Annotated[list[OperatorIn], Field(max_length=3)]


def _check_parent(
    recipe_key: str | None,
    parent_batch_id: uuid.UUID | None,
    operators: list[OperatorIn],
    community_recipe_id: uuid.UUID | None = None,
) -> None:
    if sum(x is not None for x in (recipe_key, parent_batch_id, community_recipe_id)) != 1:
        raise ValueError("give one of recipe_key, parent_batch_id or community_recipe_id")
    if parent_batch_id is not None and not operators:
        raise ValueError("a variant of your batch needs at least one operator")


class RecommendationRequest(BaseModel):
    """Design § 5.1. Ingredients are catalogue names; the non-staple ones must all be in the
    recipe (Proven) or the variant (Experimental), and staples (salt, water, sugar, flour, tea,
    starter cultures) never exclude a recipe (§ 5.2, Q3). parent_batch_id: one of your batches
    as an Experimental parent (Q16); community_recipe_id: an approved community recipe as one
    (§ 10.3); one parent at most. usda_fdc_ids: USDA foods operator (v) may add."""

    ingredients: Annotated[list[str], Field(max_length=20)] = []
    aromas: list[str] = []
    tastes: list[str] = []
    mode: Literal["proven", "experimental", "both"] = "proven"
    temperature_c: ExpectedTemperatureC | None = None  # the user's kitchen; null: each recipe's
    batch_g: BatchGrams = 1000.0
    parent_batch_id: uuid.UUID | None = None
    community_recipe_id: uuid.UUID | None = None
    usda_fdc_ids: Annotated[list[int], Field(max_length=5)] = []

    @model_validator(mode="after")
    def _valid(self) -> RecommendationRequest:
        _check_targets(self.aromas, self.tastes)
        parent = self.parent_batch_id or self.community_recipe_id
        if not (self.ingredients or self.aromas or self.tastes or parent):
            raise ValueError("give at least one ingredient, aroma or taste")
        if self.parent_batch_id and self.community_recipe_id:
            raise ValueError("give parent_batch_id or community_recipe_id, not both")
        if self.mode == "proven" and (parent or self.usda_fdc_ids):
            raise ValueError(
                "parent_batch_id, community_recipe_id and usda_fdc_ids need mode experimental "
                "or both"
            )
        _check_usda(self.usda_fdc_ids)
        return self


class RecommendationTargetOut(BaseModel):
    key: str
    kind: TargetKind
    low_resolution: bool  # a series of 2 compounds or fewer (Q7)


class CompoundRefOut(BaseModel):
    key: str
    name: str
    tier: str  # evidence tier: calibrated | reported | plausible | engine


class CardTargetOut(BaseModel):
    key: str
    kind: TargetKind
    level: Level | None  # None: not modelled for this ferment
    modelled: bool
    low_resolution: bool
    top_compound: CompoundRefOut | None


class CardIngredientOut(BaseModel):
    name: str
    role: str
    grams: float
    required: Literal["core", "optional"]
    in_catalogue: bool  # False: not bookable yet, Start batch skips it
    label: str | None
    fdc_id: int | None = None  # an operator (v) USDA food: Start batch books it from the USDA list


class CardRecipeOut(BaseModel):
    batch_g: float
    ingredients: list[CardIngredientOut]
    salt_pct: float | None  # % w/w of the ingredient rows
    sugar_pct: float | None
    starters: list[str]
    temperature_c: float
    temp_schedule: list[tuple[float, float]]  # (start hour, °C); empty: constant
    stages: str
    aerobic: bool


class TemperatureSpanOut(BaseModel):
    lo: float
    hi: float


class SliderOut(BaseModel):
    min_c: float
    max_c: float


class CardTemperatureOut(BaseModel):
    served_c: float  # the fermentation temperature: shown, booked, in a planner link
    recipe_c: float
    documented_c: TemperatureSpanOut
    model_c: float  # the temperature the model used: a card's nearest grid temperature, the
    # live forecast's nearest profile temperature
    slider: SliderOut | None  # the documented span within the safety limits; None: no slider
    source_only: bool  # Q26: served outside the model's range, the window is the source's


class CardWindowOut(BaseModel):
    taste_from_h: float
    peak_h: float
    stop_by_h: float
    basis: Literal["model", "source", "planner"]
    notes: list[str]


class CardTrustOut(BaseModel):
    provenance: str
    sources: list[str]
    profile_confidence: str
    envelope_basis: str
    labels: list[str]


class OperatorChipOut(BaseModel):
    """An Experimental card's operator chip (design § 11.1), e.g. {"op": "add", "ingredient":
    "Fresh ginger", "share": 0.0078}, {"op": "temperature", "from_c": 20, "to_c": 24},
    {"op": "usda", "fdc_id": 169941, "label": "aroma effect unknown"}. Send it back as is."""

    op: OperatorKind
    key: str
    ingredient: str | None
    replaces: str | None
    share: float | None  # mass share of the whole batch (add, usda)
    from_c: float | None
    to_c: float | None
    fdc_id: int | None
    label: str | None


class CardParentOut(BaseModel):
    kind: Literal["library", "own_batch", "community"]
    recipe_key: str | None
    batch_id: str | None
    community_recipe_id: str | None = None
    name: str
    label: str  # the recipe's name, "your batch #n" or "community recipe “…” by …"


class CommunityCardOut(BaseModel):
    """A community card's author and use (design § 10.3)."""

    id: uuid.UUID
    title: str
    pseudonym: str
    made: int  # distinct other people who started a batch from it (Start batch), author excluded
    mean_liking: float | None  # from tastings (B10); None until then


class RecommendationCardOut(BaseModel):
    id: str
    section: Literal["proven", "experimental", "community"]
    source_kind: Literal["library", "variant", "own_batch", "community"]
    recipe_key: str | None  # the library recipe (a variant's parent); None: your batch, community
    name: str
    fermentation_type: str
    style_region: str
    parent: CardParentOut | None = None  # Experimental: what the variant departs from
    operators: list[OperatorChipOut] = []
    screened: bool = False  # Experimental: combined additively until a live forecast confirms
    interaction_detected: bool | None = None  # known after the confirmation (the forecast)
    recipe: CardRecipeOut
    temperature: CardTemperatureOut
    window: CardWindowOut | None
    level: Level | None  # the targets' mean; None without targets
    targets: list[CardTargetOut]
    to_buy: list[str]  # core ingredients beyond the staples and the user's list
    not_modelled: list[str]  # ingredients without aroma data
    trust: CardTrustOut
    safety_lines: list[str]  # mandatory (design § 7)
    handoff: Literal["planner"] | None
    planner_link: str | None  # "#/levain?p=…", the planner's share link
    notes: list[str]
    community: CommunityCardOut | None = None  # a community card's author and "made n×"


class RecommendationSectionOut(BaseModel):
    cards: list[RecommendationCardOut]
    message: str | None  # why the section is empty


class GatedOutOut(BaseModel):
    recipe_key: str
    reasons: list[str]


class RecommendationDebugOut(BaseModel):
    gated_out: list[GatedOutOut]  # the gate's reasons: debug only, never shown


class RecommendationsOut(BaseModel):
    mode: Literal["proven", "experimental", "both"]
    grid_version: str
    targets: list[RecommendationTargetOut]
    proven: RecommendationSectionOut | None  # None in mode experimental
    experimental: RecommendationSectionOut | None  # None in mode proven
    notes: list[str]
    debug: RecommendationDebugOut
    # "Community — not proven" (design § 10.3): mode proven or both; None in mode experimental
    community: RecommendationSectionOut | None = None


class RecommendationForecastIn(BaseModel):
    """One card's live forecast: a library recipe (recipe_key) or an approved community recipe
    (community_recipe_id), or a variant of either or of one of your batches (parent_batch_id)
    with its operators, at a slider temperature."""

    recipe_key: str | None = None
    parent_batch_id: uuid.UUID | None = None
    community_recipe_id: uuid.UUID | None = None
    operators: Operators = []
    aromas: list[str] = []
    tastes: list[str] = []
    temperature_c: ExpectedTemperatureC | None = None  # the slider; null: the recipe's
    batch_g: BatchGrams = 1000.0  # scales a sourdough planner link

    @model_validator(mode="after")
    def _valid(self) -> RecommendationForecastIn:
        _check_targets(self.aromas, self.tastes)
        _check_parent(
            self.recipe_key, self.parent_batch_id, self.operators, self.community_recipe_id
        )
        return self


class ForecastTargetOut(CardTargetOut):
    e_peak: float
    u_peak: float


class ForecastBandOut(BaseModel):
    key: str
    kind: TargetKind
    t_h: list[float]
    e: list[float]  # central
    u: list[float]  # optimistic (P90)


class RecommendationForecastOut(BaseModel):
    recipe_key: str | None  # None: a variant of your batch, a community recipe
    source_kind: Literal["library", "variant", "own_batch", "community"] = "library"
    operators: list[OperatorChipOut] = []
    screened: bool = False  # the variant's card was screened (design § 8.5)
    screened_e_peak: float | None = None  # its screened E(peak) at this temperature
    interaction_detected: bool | None = None  # confirmed E(peak) < 0.8 × screened
    members: int | None
    temperature: CardTemperatureOut | None
    window: CardWindowOut | None
    level: Level | None
    e_peak: float | None
    u_peak: float | None
    targets: list[ForecastTargetOut]
    bands: list[ForecastBandOut]
    safety_lines: list[str]
    handoff: Literal["planner"] | None
    planner_link: str | None
    notes: list[str]


class FromRecommendationIn(BaseModel):
    """Start batch (design § 11.2): the card is recomputed on the server from these: a library
    recipe (recipe_key) or an approved community recipe (community_recipe_id), or a variant of
    either or of one of your batches (parent_batch_id) with its operators."""

    recipe_key: str | None = None
    parent_batch_id: uuid.UUID | None = None
    community_recipe_id: uuid.UUID | None = None
    operators: Operators = []
    aromas: list[str] = []
    tastes: list[str] = []
    temperature_c: ExpectedTemperatureC | None = None
    batch_g: BatchGrams = 1000.0
    mode: Literal["proven", "experimental", "both"] = "proven"
    culture_id: uuid.UUID | None = None  # an owned culture of the recipe's type; null: a new one
    culture_name: Annotated[str, Field(min_length=1, max_length=200)] | None = None

    @model_validator(mode="after")
    def _valid(self) -> FromRecommendationIn:
        _check_targets(self.aromas, self.tastes)
        _check_parent(
            self.recipe_key, self.parent_batch_id, self.operators, self.community_recipe_id
        )
        return self


class RecommendationLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: uuid.UUID
    source_kind: str
    recipe_key: str | None
    community_recipe_id: uuid.UUID | None
    parent_batch_id: uuid.UUID | None = None
    operators: list[Any]
    mode: str
    temperature_c: float
    temp_schedule: list[list[float]] | None
    window: dict[str, Any]
    targets: list[dict[str, Any]]
    grid_version: str
    created_at: datetime


class FromRecommendationOut(BaseModel):
    batch: BatchOut
    culture: CultureOut
    link: RecommendationLinkOut
    reminders: list[ReminderOut]
    skipped_ingredients: list[str]  # recipe rows not in the catalogue yet: not booked


JobStatus = Literal["queued", "running", "done", "failed"]


class DeepSearchOut(BaseModel):
    """POST /recommendations/deep-search: the job to poll (GET /recommendations/jobs/{job_id}).
    202 for a new job; 200 for your finished job of the same request (its results are kept)."""

    job_id: uuid.UUID
    status: JobStatus


class RecommendationJobOut(BaseModel):
    """A deep search (design § 10.2): up to 20 live forecasts, run in the background. Partial
    results come in as each forecast finishes; cards are confirmed (never "screened") and
    ranked like the Experimental section (§ 5.4)."""

    job_id: uuid.UUID
    status: JobStatus
    done: int  # forecasts run so far
    total: int  # forecasts planned; 0 until the job starts
    eta_s: int | None  # seconds left (queue included), from the mean time per forecast so far;
    # None once finished
    results: list[RecommendationCardOut]
    error: str | None  # why it failed (status failed); its partial results are kept
    request: dict[str, Any]  # the POST /recommendations/deep-search body
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


# ── Community recipes (design § 10.3, recommender.community) ─────────────────

CommunityStatus = Literal["pending", "approved", "rejected"]
# A pen name, never checked against a real one: letters, digits, spaces and . _ ' -, starting
# with a letter or digit; no @ or / (so not an e-mail address or a link).
Pseudonym = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=40, pattern=r"^\w[\w .'-]*$"),
]


class CommunityPublishIn(BaseModel):
    """POST /community-recipes: publish one of your finished batches as a community recipe."""

    batch_id: uuid.UUID
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    pseudonym: Pseudonym


class CommunityIngredientOut(BaseModel):
    name: str
    role: str
    g_per_kg: float  # of the batch's weighed total
    fdc_id: int | None  # a USDA pick
    label: str | None  # "USDA food: aroma effect unknown"


class CommunityRecipeOut(BaseModel):
    id: uuid.UUID
    title: str
    pseudonym: str
    fermentation_type: str
    ingredients: list[CommunityIngredientOut]
    temperature_c: float  # the batch's mean logged temperature, else its expected one
    duration_h: float  # the batch's actual duration
    status: CommunityStatus
    reason: str | None  # the reviewer's
    created_at: datetime
    reviewed_at: datetime | None


class CommunityPublishOut(CommunityRecipeOut):
    notice: str  # "Your recipe stays in the library if you delete your account; …"


class CommunityForecastJobOut(BaseModel):
    """A community recipe's newest forecast job (recommender.community), for its reviewer."""

    id: uuid.UUID
    status: str  # queued | running | done | failed
    error: str | None
    done: int
    total: int
    finished_at: datetime | None


class AdminCommunityRecipeOut(CommunityRecipeOut):
    owner_id: str | None  # None once its author deleted their account
    source_batch_id: uuid.UUID | None
    reviewed_by: str | None
    forecast_job: CommunityForecastJobOut | None = None  # None: never queued


class CommunityReviewIn(BaseModel):
    """An admin's decision; a rejection needs its reason."""

    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
