"""crédito de prorrateo y cargo de reconexión pendientes por cliente

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("pending_credit", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "clients",
        sa.Column("pending_reconnection_fee", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("clients", "pending_reconnection_fee")
    op.drop_column("clients", "pending_credit")
