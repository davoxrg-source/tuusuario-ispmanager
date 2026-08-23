"""add promise_to_pay_until to invoices

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("promise_to_pay_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("invoices", "promise_to_pay_until")
