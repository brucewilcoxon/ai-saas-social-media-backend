"""add_generation_config_to_monthly_plans

Revision ID: c3d5e7f90b21
Revises: b2c4e6f80a12
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa


revision = "c3d5e7f90b21"
down_revision = "b2c4e6f80a12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monthly_plans",
        sa.Column("generation_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("monthly_plans", "generation_config")
