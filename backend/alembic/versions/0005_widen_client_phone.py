"""widen clients.phone (real data has multi-number/note text up to ~70 chars)

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-22

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("clients", "phone", type_=sa.String(120), existing_type=sa.String(40))


def downgrade() -> None:
    op.alter_column("clients", "phone", type_=sa.String(40), existing_type=sa.String(120))
