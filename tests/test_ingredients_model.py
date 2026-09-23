"""Ingredient/BatchIngredient model round-trip (no API — see test_ingredients.py
and test_batch_ingredients.py in later tasks for the HTTP-level behavior)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fermenttrack.models import Batch, BatchIngredient, Culture, Ingredient, IngredientNutrient


@pytest.mark.asyncio
async def test_ingredient_round_trip(db_session: AsyncSession) -> None:
    ingredient = Ingredient(
        name="Black/green tea",
        default_role="base",
        fermentation_systems=["kombucha"],
    )
    db_session.add(ingredient)
    await db_session.commit()

    result = await db_session.execute(select(Ingredient).where(Ingredient.name == "Black/green tea"))
    fetched = result.scalar_one()
    assert fetched.default_role == "base"
    assert fetched.fermentation_systems == ["kombucha"]
    assert fetched.is_active is True
    assert fetched.canonical_id is None


@pytest.mark.asyncio
async def test_batch_ingredient_round_trip(db_session: AsyncSession) -> None:
    culture = Culture(name="Jun SCOBY", type="kombucha")
    db_session.add(culture)
    await db_session.flush()

    batch = Batch(culture_id=culture.id, current_stage="brew_sweet_tea")
    ingredient = Ingredient(name="Cane sugar", default_role="base", fermentation_systems=["kombucha"])
    db_session.add_all([batch, ingredient])
    await db_session.flush()

    batch_ingredient = BatchIngredient(
        batch_id=batch.id,
        ingredient_id=ingredient.id,
        quantity=100.0,
        unit="g",
        role="base",
    )
    db_session.add(batch_ingredient)
    await db_session.commit()

    result = await db_session.execute(
        select(BatchIngredient).where(BatchIngredient.batch_id == batch.id)
    )
    fetched = result.scalar_one()
    assert fetched.quantity == 100.0
    assert fetched.unit == "g"
    assert fetched.role == "base"


@pytest.mark.asyncio
async def test_ingredient_nutrients_roundtrip_and_unique_per_source(
    db_session: AsyncSession,
) -> None:
    salt = Ingredient(name="Salt", default_role="additive", fermentation_systems=["lacto_ferment"])
    salt.nutrients.append(
        IngredientNutrient(
            nutrient="sodium", amount_per_100g=38.758, source="usda_fdc",
            source_food_id="173468", source_version="fdc_nutrients_v1",
        )
    )
    db_session.add(salt)
    await db_session.commit()

    loaded = (
        await db_session.execute(
            select(Ingredient)
            .where(Ingredient.id == salt.id)
            .options(selectinload(Ingredient.nutrients))
        )
    ).scalar_one()
    assert {n.nutrient: n.amount_per_100g for n in loaded.nutrients} == {"sodium": 38.758}

    db_session.add(
        IngredientNutrient(
            ingredient_id=salt.id, nutrient="sodium", amount_per_100g=1.0, source="usda_fdc",
            source_food_id="x", source_version="fdc_nutrients_v1",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
