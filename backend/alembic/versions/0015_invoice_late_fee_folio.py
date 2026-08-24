"""mora y folio en invoices

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("late_fee_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "invoices", sa.Column("late_fee_applied_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("invoices", sa.Column("folio", sa.String(40), nullable=True))
    op.create_index("ix_invoices_folio", "invoices", ["folio"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invoices_folio", table_name="invoices")
    op.drop_column("invoices", "folio")
    op.drop_column("invoices", "late_fee_applied_at")
    op.drop_column("invoices", "late_fee_amount")
