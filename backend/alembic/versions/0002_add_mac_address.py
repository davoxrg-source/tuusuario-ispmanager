"""add mac_address to mikrotik_devices

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21

"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mikrotik_devices", sa.Column("mac_address", sa.String(17), nullable=True))
    op.create_index(
        "ix_mikrotik_devices_mac_address", "mikrotik_devices", ["mac_address"]
    )


def downgrade() -> None:
    op.drop_index("ix_mikrotik_devices_mac_address", table_name="mikrotik_devices")
    op.drop_column("mikrotik_devices", "mac_address")
