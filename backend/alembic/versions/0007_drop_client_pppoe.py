"""drop per-client pppoe fields (this deployment doesn't use PPPoE, static IP only)

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("clients", "pppoe_username")
    op.drop_column("clients", "encrypted_pppoe_password")


def downgrade() -> None:
    op.add_column("clients", sa.Column("encrypted_pppoe_password", sa.String(500), nullable=True))
    op.add_column("clients", sa.Column("pppoe_username", sa.String(120), nullable=True))
