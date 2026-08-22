"""add guaranteed_floor_percent to plans

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("guaranteed_floor_percent", sa.Integer(), nullable=False, server_default="9"),
    )
    op.alter_column("plans", "guaranteed_floor_percent", server_default=None)


def downgrade() -> None:
    op.drop_column("plans", "guaranteed_floor_percent")
