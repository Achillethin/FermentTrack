"""SQLAlchemy 2.0 ORM models — Culture, Batch, Measurement, Reminder.

Postgres-native types (UUID, TIMESTAMPTZ) per docs/ARCHITECTURE.md's schema.
Tests run against SQLite (see tests/conftest.py) — SQLAlchemy's postgresql
dialect types degrade gracefully to generic equivalents there.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Float, ForeignKey, Interval, Text
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
    outcome: Mapped[str] = mapped_column(Text, nullable=False, default="in_progress")
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    culture: Mapped["Culture"] = relationship(back_populates="batches")
    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    reminders: Mapped[list["Reminder"]] = relationship(
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
