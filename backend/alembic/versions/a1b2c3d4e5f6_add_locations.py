"""add locations reference table

Revision ID: a1b2c3d4e5f6
Revises: 43d7a9a13999
Create Date: 2026-09-04

State/district reference data for the onboarding location pickers — moved
server-side (was a bundled frontend JSON). Seeded by
backend/scripts/seed_reference_data.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "43d7a9a13999"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("district", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("state", "district", name="uq_locations_state_district"),
    )
    op.create_index(op.f("ix_locations_state"), "locations", ["state"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_locations_state"), table_name="locations")
    op.drop_table("locations")
