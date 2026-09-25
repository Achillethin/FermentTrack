"""SQLAlchemy 2.0 ORM models — Culture, Batch, Measurement, Reminder.

Postgres-native types (UUID, TIMESTAMPTZ) per docs/ARCHITECTURE.md's schema.
Tests run against SQLite (see tests/conftest.py) — SQLAlchemy's postgresql
dialect types degrade gracefully to generic equivalents there.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Integer, Interval, JSON, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fermenttrack.database import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Culture(Base):
    __tablename__ = "cultures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # kombucha, sourdough, koji, ...
    born_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cultures.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)

    batches: Mapped[list["Batch"]] = relationship(back_populates="culture")


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    culture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cultures.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
    current_stage: Mapped[str] = mapped_column(Text, nullable=False)
    stage_entered_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=_now
    )
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The user's estimate of the temperature the batch ferments at (°C), set up front.
    # An input to the prediction model, not a measurement: logged temperature readings
    # stay Measurement rows and are never overwritten by this.
    expected_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False, default="in_progress")
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    culture: Mapped["Culture"] = relationship(back_populates="batches")
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    batch_ingredients: Mapped[list["BatchIngredient"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    batch_organisms: Mapped[list["BatchOrganism"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False
    )
    measured_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # pH, temperature, brix, gravity, ...
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch: Mapped["Batch"] = relationship(back_populates="measurements")


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    repeat_interval: Mapped[timedelta | None] = mapped_column(Interval, nullable=True)
    urgency: Mapped[str] = mapped_column(Text, nullable=False, default="medium")
    completed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    batch: Mapped["Batch"] = relationship(back_populates="reminders")


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    canonical_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    default_role: Mapped[str] = mapped_column(Text, nullable=False)  # base | starter | flavoring | additive
    fermentation_systems: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fdc_id: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True, index=True)
    nutrients: Mapped[list[IngredientNutrient]] = relationship()


class BatchIngredient(Base):
    __tablename__ = "batch_ingredients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id"), nullable=False
    )
    quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # Copied from Ingredient.default_role AT INSERT TIME by the router (Task 6),
    # never re-derived — see Global Constraints.

    batch: Mapped["Batch"] = relationship(back_populates="batch_ingredients")
    ingredient: Mapped["Ingredient"] = relationship()


class IngredientNutrient(Base):
    """Reference nutrient per 100 g (always grams). No row = not reported = unknown, never 0."""

    __tablename__ = "ingredient_nutrients"
    __table_args__ = (UniqueConstraint("ingredient_id", "nutrient", "source"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id"), nullable=False
    )
    nutrient: Mapped[str] = mapped_column(Text, nullable=False)  # key of nutrients.NUTRIENTS
    amount_per_100g: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)  # "usda_fdc"
    source_food_id: Mapped[str] = mapped_column(Text, nullable=False)  # FDC fdcId
    source_version: Mapped[str] = mapped_column(Text, nullable=False)  # snapshot file stem


class FdcFood(Base):
    """USDA FDC catalog food (SR Legacy / Foundation), loaded from fdc_catalog_v1.csv.gz."""

    __tablename__ = "fdc_foods"

    fdc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)  # "SR Legacy" | "Foundation"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    nutrients: Mapped[list[FdcFoodNutrient]] = relationship()


class FdcFoodNutrient(Base):
    """Catalog nutrient per 100 g (grams). No row = not reported = unknown, never 0."""

    __tablename__ = "fdc_food_nutrients"

    fdc_id: Mapped[int] = mapped_column(Integer, ForeignKey("fdc_foods.fdc_id"), primary_key=True)
    nutrient: Mapped[str] = mapped_column(Text, primary_key=True)  # key of nutrients.NUTRIENTS
    amount_per_100g: Mapped[float] = mapped_column(Float, nullable=False)


class Organism(Base):
    __tablename__ = "organisms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    kingdom: Mapped[str] = mapped_column(Text, nullable=False)  # bacteria | yeast | mold
    ncbi_taxon_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    kegg_organism_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_version: Mapped[str] = mapped_column(Text, nullable=False)


class Enzyme(Base):
    __tablename__ = "enzymes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    ec_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kegg_entry_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_version: Mapped[str] = mapped_column(Text, nullable=False)


class Compound(Base):
    __tablename__ = "compounds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    kegg_compound_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)  # acid|alcohol|gas|flavor|other
    source_version: Mapped[str] = mapped_column(Text, nullable=False)


class OrganismEnzyme(Base):
    """'This organism expresses this enzyme' — hand-curated, see biochem.py."""

    __tablename__ = "organism_enzymes"
    __table_args__ = (UniqueConstraint("organism_id", "enzyme_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisms.id"), nullable=False
    )
    enzyme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enzymes.id"), nullable=False
    )

    enzyme: Mapped["Enzyme"] = relationship()


class EnzymeReaction(Base):
    """'This enzyme converts substrate to product' (one representative
    reaction per curated enzyme, not full pathway completeness)."""

    __tablename__ = "enzyme_reactions"
    __table_args__ = (UniqueConstraint("enzyme_id", "substrate_id", "product_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    enzyme_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enzymes.id"), nullable=False
    )
    substrate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compounds.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("compounds.id"), nullable=False
    )

    substrate: Mapped["Compound"] = relationship(foreign_keys=[substrate_id])
    product: Mapped["Compound"] = relationship(foreign_keys=[product_id])


class FermentationTypeOrganism(Base):
    """Default organisms per fermentation_type (the STAGE_MACHINES vocabulary
    plus kefir/vinegar) — hand-curated, see biochem.py."""

    __tablename__ = "fermentation_type_organisms"
    __table_args__ = (UniqueConstraint("fermentation_type", "organism_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    fermentation_type: Mapped[str] = mapped_column(Text, nullable=False)
    organism_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisms.id"), nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organism: Mapped["Organism"] = relationship()


class BatchOrganism(Base):
    """A custom organism attached to a batch. The /biochemistry endpoint shows the
    fermentation type's default organisms PLUS these rows, deduped by organism (a
    custom row supersedes the default entry, so its notes show and source is
    "custom"). Attachments only add; they never remove a type default."""

    __tablename__ = "batch_organisms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("batches.id"), nullable=False
    )
    organism_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisms.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, default="custom")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=_now)

    batch: Mapped["Batch"] = relationship(back_populates="batch_organisms")
    organism: Mapped["Organism"] = relationship()
