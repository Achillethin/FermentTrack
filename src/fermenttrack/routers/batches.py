from __future__ import annotations

import uuid
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.composition import RecipeItem, compose, suggest_salt
from fermenttrack.database import get_db
from fermenttrack.models import (
    Batch,
    BatchIngredient,
    BatchOrganism,
    Compound,
    Culture,
    Enzyme,
    EnzymeReaction,
    FdcFood,
    FermentationTypeOrganism,
    Ingredient,
    IngredientNutrient,
    Measurement,
    Organism,
    OrganismEnzyme,
    Reminder,
)
from fermenttrack.reminders import build_reminder_for_stage, now_utc
from fermenttrack.safety.service import get_safety_report
from fermenttrack.schemas import (
    BatchBiochemistryOut,
    BatchCompare,
    BatchCompositionOut,
    BatchCreate,
    BatchIngredientCreate,
    BatchIngredientOut,
    BatchOrganismCreate,
    BatchOrganismOut,
    BatchOut,
    BatchPreview,
    BatchTimeline,
    BiochemEnzymeOut,
    BiochemOrganismOut,
    CompoundOut,
    CultureOut,
    MeasurementCreate,
    MeasurementOut,
    NoteCreate,
    NutrientTotalOut,
    RuleVerdictOut,
    SafetyReportOut,
    SaltSuggestionOut,
    StageAdvance,
    TimelineEvent,
)
from fermenttrack.stages import InvalidStageError, first_stage, next_stage_name

router = APIRouter(prefix="/batches", tags=["batches"])


async def _get_batch(
    batch_id: uuid.UUID,
    db: AsyncSession,
    *,
    with_measurements: bool = False,
    with_culture: bool = False,
    with_batch_ingredients: bool = False,
) -> Batch:
    stmt = select(Batch).where(Batch.id == batch_id)
    if with_measurements:
        stmt = stmt.options(selectinload(Batch.measurements))
    if with_culture:
        stmt = stmt.options(selectinload(Batch.culture))
    if with_batch_ingredients:
        stmt = stmt.options(selectinload(Batch.batch_ingredients))
    result = await db.execute(stmt)
    batch = result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.post("", response_model=BatchOut, status_code=201)
async def create_batch(payload: BatchCreate, db: AsyncSession = Depends(get_db)) -> Batch:
    culture = await db.get(Culture, payload.culture_id)
    if culture is None:
        raise HTTPException(status_code=404, detail="Culture not found")

    started_at = now_utc()
    initial_stage = first_stage(culture.type)
    batch = Batch(
        culture_id=payload.culture_id,
        started_at=started_at,
        current_stage=initial_stage,
        stage_entered_at=started_at,
        target=payload.target,
    )
    db.add(batch)
    await db.flush()

    reminder = build_reminder_for_stage(batch, culture.type, initial_stage, started_at)
    if reminder is not None:
        db.add(reminder)

    await db.commit()
    await db.refresh(batch)
    return batch


@router.patch("/{batch_id}/stage", response_model=BatchOut)
async def advance_stage(
    batch_id: uuid.UUID, payload: StageAdvance, db: AsyncSession = Depends(get_db)
) -> Batch:
    batch = await _get_batch(batch_id, db, with_culture=True)
    substrate = batch.culture.type

    try:
        target_stage = payload.stage or next_stage_name(substrate, batch.current_stage)
        if target_stage is None:
            raise HTTPException(status_code=400, detail="Batch is already at its final stage")
        entered_at = now_utc()
        # validates stage name
        reminder = build_reminder_for_stage(batch, substrate, target_stage, entered_at)
    except InvalidStageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None

    batch.current_stage = target_stage
    batch.stage_entered_at = entered_at
    if target_stage in ("ready", "done"):
        batch.outcome = "success"
        batch.ended_at = entered_at

    # Superseded by the new stage's reminder — mark prior open reminders done
    # rather than leaving stale ones (e.g. a past stage's timer) in the list.
    await db.execute(
        update(Reminder)
        .where(Reminder.batch_id == batch.id, Reminder.completed_at.is_(None))
        .values(completed_at=entered_at)
    )

    if reminder is not None:
        db.add(reminder)

    await db.commit()
    await db.refresh(batch)
    return batch


@router.post("/{batch_id}/measure", response_model=MeasurementOut, status_code=201)
async def add_measurement(
    batch_id: uuid.UUID, payload: MeasurementCreate, db: AsyncSession = Depends(get_db)
) -> Measurement:
    batch = await _get_batch(batch_id, db)
    measurement = Measurement(batch_id=batch.id, **payload.model_dump())
    db.add(measurement)
    await db.commit()
    await db.refresh(measurement)
    return measurement


@router.post("/{batch_id}/note", response_model=MeasurementOut, status_code=201)
async def add_note(
    batch_id: uuid.UUID, payload: NoteCreate, db: AsyncSession = Depends(get_db)
) -> Measurement:
    """Notes are stored as measurements with type="note" (no separate table
    in docs/ARCHITECTURE.md's schema — value_text carries the note body)."""
    batch = await _get_batch(batch_id, db)
    note = Measurement(batch_id=batch.id, type="note", value_text=payload.text)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


def _build_timeline_events(batch: Batch) -> list[TimelineEvent]:
    return [
        TimelineEvent(
            kind="note" if m.type == "note" else "measurement",
            timestamp=m.measured_at,
            detail={
                "type": m.type,
                "value_numeric": m.value_numeric,
                "value_text": m.value_text,
                "notes": m.notes,
            },
        )
        for m in sorted(batch.measurements, key=lambda m: m.measured_at)
    ]


@router.get("/{batch_id}/timeline", response_model=BatchTimeline)
async def get_timeline(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BatchTimeline:
    batch = await _get_batch(batch_id, db, with_measurements=True)
    return BatchTimeline(batch=BatchOut.model_validate(batch), events=_build_timeline_events(batch))


@router.get("/compare", response_model=BatchCompare)
async def compare_batches(
    batch_id: list[uuid.UUID] = Query(...), db: AsyncSession = Depends(get_db)
) -> BatchCompare:
    if len(batch_id) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two batch_id query params")

    result = await db.execute(
        select(Batch).where(Batch.id.in_(batch_id)).options(selectinload(Batch.measurements))
    )
    batches = list(result.scalars().all())
    found_ids = {b.id for b in batches}
    missing = set(batch_id) - found_ids
    if missing:
        raise HTTPException(status_code=404, detail=f"Batch(es) not found: {missing}")

    measurements = {
        str(b.id): [
            MeasurementOut.model_validate(m)
            for m in sorted(b.measurements, key=lambda m: m.measured_at)
        ]
        for b in batches
    }
    return BatchCompare(batches=[BatchOut.model_validate(b) for b in batches], measurements=measurements)


async def _ingredient_for_fdc_food(
    db: AsyncSession, fdc_id: int, ferment_type: str, role: str | None
) -> Ingredient:
    """Find-or-create the Ingredient for a USDA catalog food and tag it for this ferment.

    Spec: docs/superpowers/specs/2026-09-23-usda-food-catalog-design.md § Pick.
    ponytail: check-then-create isn't race-safe (unique index -> 500 on a simultaneous
    first pick); fine single-user, catch IntegrityError + re-select if that changes.
    """
    food = await db.get(FdcFood, fdc_id, options=[selectinload(FdcFood.nutrients)])
    if food is None:
        raise HTTPException(status_code=404, detail="USDA food not found")
    result = await db.execute(select(Ingredient).where(Ingredient.fdc_id == fdc_id))
    ingredient = result.scalar_one_or_none()
    if ingredient is None:
        ingredient = Ingredient(
            name=food.description,
            default_role=role or "base",
            fermentation_systems=[ferment_type],
            fdc_id=fdc_id,
            nutrients=[
                IngredientNutrient(
                    nutrient=n.nutrient,
                    amount_per_100g=n.amount_per_100g,
                    source="usda_fdc",
                    source_food_id=str(fdc_id),
                    source_version="fdc_catalog_v1",
                )
                for n in food.nutrients
            ],
        )
        db.add(ingredient)
        await db.flush()
    elif ingredient.is_active and ferment_type not in ingredient.fermentation_systems:
        # Reassign: the JSON column doesn't track in-place mutation.
        ingredient.fermentation_systems = [*ingredient.fermentation_systems, ferment_type]
    return ingredient


@router.post("/{batch_id}/ingredients", response_model=BatchIngredientOut, status_code=201)
async def add_batch_ingredient(
    batch_id: uuid.UUID, payload: BatchIngredientCreate, db: AsyncSession = Depends(get_db)
) -> BatchIngredient:
    batch = await _get_batch(batch_id, db, with_culture=True)
    if payload.fdc_id is not None:
        ingredient = await _ingredient_for_fdc_food(
            db, payload.fdc_id, batch.culture.type, payload.role
        )
    else:
        found = await db.get(Ingredient, payload.ingredient_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        ingredient = found
    if not ingredient.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"{ingredient.name!r} is retired; pick a specific ingredient instead",
        )
    if batch.culture.type not in ingredient.fermentation_systems:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{ingredient.name!r} isn't tagged for {batch.culture.type!r} "
                f"(tagged for {ingredient.fermentation_systems})"
            ),
        )

    batch_ingredient = BatchIngredient(
        batch_id=batch.id,
        ingredient_id=ingredient.id,
        quantity=payload.quantity,
        unit=payload.unit,
        role=payload.role or ingredient.default_role,
    )
    db.add(batch_ingredient)
    await db.commit()
    await db.refresh(batch_ingredient)
    return batch_ingredient


@router.get("/{batch_id}/ingredients", response_model=list[BatchIngredientOut])
async def list_batch_ingredients(
    batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[BatchIngredient]:
    await _get_batch(batch_id, db)  # raises 404 if the batch doesn't exist
    result = await db.execute(select(BatchIngredient).where(BatchIngredient.batch_id == batch_id))
    return list(result.scalars().all())


@router.get("/{batch_id}/composition", response_model=BatchCompositionOut)
async def get_batch_composition(
    batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> BatchCompositionOut:
    batch = await _get_batch(batch_id, db, with_culture=True)  # 404 if missing
    result = await db.execute(
        select(BatchIngredient)
        .where(BatchIngredient.batch_id == batch_id)
        .options(selectinload(BatchIngredient.ingredient).selectinload(Ingredient.nutrients))
    )
    items = [
        RecipeItem(
            bi.ingredient.name,
            bi.quantity,
            bi.unit,
            {n.nutrient: n.amount_per_100g for n in bi.ingredient.nutrients},
            bi.role,
        )
        for bi in result.scalars()
    ]
    c = compose(items)
    salt = suggest_salt(batch.culture.type, items)
    return BatchCompositionOut(
        total_mass_g=c.total_mass_g,
        mapped_mass_g=c.mapped_mass_g,
        coverage=c.coverage,
        salt_pct=c.salt_pct,
        salt_suggestion=SaltSuggestionOut(**salt._asdict()) if salt else None,
        nutrients=[
            NutrientTotalOut(
                nutrient=name, grams=t.grams, per_100g=c.per_100g(name), missing_from=t.missing_from
            )
            for name, t in c.nutrients.items()
        ],
        unmapped=c.unmapped,
        unquantified=c.unquantified,
    )


@router.get("/{batch_id}/preview", response_model=BatchPreview)
async def get_batch_preview(batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> BatchPreview:
    """Presentation-shaped aggregate for the batch-preview UI page — batch
    header, recipe, timeline, and safety advisory in one call. No compound/
    microbial data (see docs/superpowers/specs/2026-09-18-experiment-
    logging-design.md § 2 for why). Scope ceiling: this endpoint is owned by
    that one page's needs; any other consumer should use /timeline and
    /safety directly rather than this growing to serve them too.
    """
    batch = await _get_batch(
        batch_id, db, with_measurements=True, with_culture=True, with_batch_ingredients=True
    )

    now = now_utc()
    stage_entered_at = batch.stage_entered_at
    if stage_entered_at.tzinfo is None:
        # SQLite (used in tests/local dev, see tests/conftest.py) doesn't
        # preserve tz-awareness on TIMESTAMP(timezone=True) columns the way
        # Postgres does — all app timestamps are UTC by convention regardless.
        stage_entered_at = stage_entered_at.replace(tzinfo=timezone.utc)
    days_in_stage = (now - stage_entered_at).total_seconds() / 86400.0

    report = get_safety_report(batch)
    safety = SafetyReportOut(
        safe=report.safe,
        hard_stops=[RuleVerdictOut(**vars(v)) for v in report.hard_stops],
        warnings=[RuleVerdictOut(**vars(v)) for v in report.warnings],
        rules_evaluated=report.rules_evaluated,
        rules_triggered=report.rules_triggered,
        summary_en=report.summary_en,
        summary_fr=report.summary_fr,
    )

    return BatchPreview(
        batch=BatchOut.model_validate(batch),
        culture=CultureOut.model_validate(batch.culture),
        days_in_stage=max(days_in_stage, 0.0),
        recipe=[BatchIngredientOut.model_validate(bi) for bi in batch.batch_ingredients],
        timeline=_build_timeline_events(batch),
        safety=safety,
    )


async def _resolve_batch_organisms(
    batch: Batch, db: AsyncSession
) -> list[tuple[Organism, str, str | None]]:
    """Type defaults plus the batch's custom attachments, deduped by organism id
    (a custom attachment supersedes the default entry), sorted by name."""
    result = await db.execute(
        select(FermentationTypeOrganism)
        .where(
            FermentationTypeOrganism.fermentation_type == batch.culture.type,
            FermentationTypeOrganism.is_default.is_(True),
        )
        .options(selectinload(FermentationTypeOrganism.organism))
    )
    merged: dict[uuid.UUID, tuple[Organism, str, str | None]] = {
        fo.organism.id: (fo.organism, "default", None) for fo in result.scalars().all()
    }
    result = await db.execute(
        select(BatchOrganism)
        .where(BatchOrganism.batch_id == batch.id)
        .options(selectinload(BatchOrganism.organism))
    )
    for bo in result.scalars().all():
        merged[bo.organism.id] = (bo.organism, bo.source, bo.notes)
    return sorted(merged.values(), key=lambda t: t[0].name.lower())


def _ec_key(ec_number: str) -> tuple[tuple[int, int], ...]:
    # "3.2.1.3" < "3.2.1.20"; non-numeric parts ("-", "n1") sort after numbers.
    return tuple((0, int(p)) if p.isdigit() else (1, 0) for p in ec_number.split("."))


@router.get("/{batch_id}/biochemistry", response_model=BatchBiochemistryOut)
async def get_batch_biochemistry(
    batch_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> BatchBiochemistryOut:
    batch = await _get_batch(batch_id, db, with_culture=True)
    organisms = await _resolve_batch_organisms(batch, db)

    result = await db.execute(
        select(OrganismEnzyme)
        .where(OrganismEnzyme.organism_id.in_([o.id for o, _, _ in organisms]))
        .options(selectinload(OrganismEnzyme.enzyme))
    )
    links = result.scalars().all()
    enzymes: dict[uuid.UUID, Enzyme] = {}
    carriers: dict[uuid.UUID, set[uuid.UUID]] = {}
    for oe in links:
        enzymes[oe.enzyme.id] = oe.enzyme
        carriers.setdefault(oe.enzyme.id, set()).add(oe.organism_id)

    compounds: dict[uuid.UUID, Compound] = {}
    if enzymes:
        result = await db.execute(
            select(EnzymeReaction)
            .where(EnzymeReaction.enzyme_id.in_(list(enzymes)))
            .options(
                selectinload(EnzymeReaction.substrate), selectinload(EnzymeReaction.product)
            )
        )
        for er in result.scalars().all():
            compounds[er.substrate.id] = er.substrate
            compounds[er.product.id] = er.product

    return BatchBiochemistryOut(
        organisms=[
            BiochemOrganismOut(
                id=o.id, name=o.name, kingdom=o.kingdom, source=source, notes=notes
            )
            for o, source, notes in organisms
        ],
        enzymes=[
            BiochemEnzymeOut(
                id=e.id,
                ec_number=e.ec_number,
                name=e.name,
                # `organisms` is already name-sorted, so this keeps that order.
                organism_ids=[o.id for o, _, _ in organisms if o.id in carriers[e.id]],
            )
            for e in sorted(enzymes.values(), key=lambda e: _ec_key(e.ec_number))
        ],
        compounds=[
            CompoundOut.model_validate(c)
            for c in sorted(compounds.values(), key=lambda c: (c.category, c.name.lower()))
        ],
    )


@router.post("/{batch_id}/organisms", response_model=BatchOrganismOut, status_code=201)
async def add_batch_organism(
    batch_id: uuid.UUID, payload: BatchOrganismCreate, db: AsyncSession = Depends(get_db)
) -> BatchOrganism:
    batch = await _get_batch(batch_id, db)
    organism = await db.get(Organism, payload.organism_id)
    if organism is None:
        raise HTTPException(status_code=404, detail="Organism not found")
    # ponytail: check-then-insert isn't race-safe; add a unique constraint +
    # IntegrityError handling if this ever becomes multi-user.
    existing = await db.execute(
        select(BatchOrganism.id).where(
            BatchOrganism.batch_id == batch.id, BatchOrganism.organism_id == organism.id
        )
    )
    if existing.first() is not None:
        raise HTTPException(
            status_code=409, detail=f"{organism.name!r} is already attached to this batch"
        )

    batch_organism = BatchOrganism(
        batch_id=batch.id, organism_id=organism.id, notes=payload.notes
    )
    db.add(batch_organism)
    await db.commit()
    await db.refresh(batch_organism)
    return batch_organism


@router.delete("/{batch_id}/organisms/{organism_id}", status_code=204)
async def remove_batch_organism(
    batch_id: uuid.UUID, organism_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    batch = await _get_batch(batch_id, db)
    result = await db.execute(
        select(BatchOrganism).where(
            BatchOrganism.batch_id == batch.id, BatchOrganism.organism_id == organism_id
        )
    )
    attachment = result.scalar_one_or_none()
    if attachment is None:
        raise HTTPException(status_code=404, detail="Organism is not attached to this batch")
    await db.delete(attachment)
    await db.commit()
