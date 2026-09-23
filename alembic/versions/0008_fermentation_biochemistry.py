# alembic/versions/0008_fermentation_biochemistry.py
"""organisms/enzymes/compounds fermentation biochemistry reference data + batch_organisms override

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-23

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op
from fermenttrack.biochem import KEGG_BIOCHEM_V1, load_snapshot, snapshot_seed_rows

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    organisms_t = op.create_table(
        "organisms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kingdom", sa.Text(), nullable=False),
        sa.Column("ncbi_taxon_id", sa.Text(), nullable=True),
        sa.Column("kegg_organism_code", sa.Text(), nullable=True),
        sa.Column("source_version", sa.Text(), nullable=False),
    )
    enzymes_t = op.create_table(
        "enzymes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ec_number", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kegg_entry_id", sa.Text(), nullable=True),
        sa.Column("source_version", sa.Text(), nullable=False),
    )
    compounds_t = op.create_table(
        "compounds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kegg_compound_id", sa.Text(), nullable=True, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("source_version", sa.Text(), nullable=False),
    )
    organism_enzymes_t = op.create_table(
        "organism_enzymes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organism_id", UUID(as_uuid=True), sa.ForeignKey("organisms.id"), nullable=False),
        sa.Column("enzyme_id", UUID(as_uuid=True), sa.ForeignKey("enzymes.id"), nullable=False),
        sa.UniqueConstraint("organism_id", "enzyme_id"),
    )
    enzyme_reactions_t = op.create_table(
        "enzyme_reactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("enzyme_id", UUID(as_uuid=True), sa.ForeignKey("enzymes.id"), nullable=False),
        sa.Column("substrate_id", UUID(as_uuid=True), sa.ForeignKey("compounds.id"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("compounds.id"), nullable=False),
        sa.UniqueConstraint("enzyme_id", "substrate_id", "product_id"),
    )
    fermentation_type_organisms_t = op.create_table(
        "fermentation_type_organisms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fermentation_type", sa.Text(), nullable=False),
        sa.Column("organism_id", UUID(as_uuid=True), sa.ForeignKey("organisms.id"), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("fermentation_type", "organism_id"),
    )
    op.create_table(
        "batch_organisms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", UUID(as_uuid=True), sa.ForeignKey("batches.id"), nullable=False),
        sa.Column("organism_id", UUID(as_uuid=True), sa.ForeignKey("organisms.id"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default="custom"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    )

    # KEGG_BIOCHEM_V1 is frozen, so this migration stays a faithful record of what it inserted.
    seed = snapshot_seed_rows(load_snapshot(KEGG_BIOCHEM_V1))
    op.bulk_insert(organisms_t, seed["organisms"])
    op.bulk_insert(enzymes_t, seed["enzymes"])
    op.bulk_insert(compounds_t, seed["compounds"])
    op.bulk_insert(organism_enzymes_t, seed["organism_enzymes"])
    op.bulk_insert(enzyme_reactions_t, seed["enzyme_reactions"])
    op.bulk_insert(fermentation_type_organisms_t, seed["fermentation_type_organisms"])


def downgrade() -> None:
    op.drop_table("batch_organisms")
    op.drop_table("fermentation_type_organisms")
    op.drop_table("enzyme_reactions")
    op.drop_table("organism_enzymes")
    op.drop_table("compounds")
    op.drop_table("enzymes")
    op.drop_table("organisms")
