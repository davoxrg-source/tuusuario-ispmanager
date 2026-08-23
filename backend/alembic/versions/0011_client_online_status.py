"""add is_online/last_seen_at to clients (real-time connectivity, not billing status)

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients", sa.Column("is_online", sa.Boolean, nullable=False, server_default=sa.false())
    )
    op.alter_column("clients", "is_online", server_default=None)
    op.add_column("clients", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "last_seen_at")
    op.drop_column("clients", "is_online")
