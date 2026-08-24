"""coordenadas (latitud/longitud) en clients y mikrotik_devices

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("clients", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("mikrotik_devices", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("mikrotik_devices", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("mikrotik_devices", "longitude")
    op.drop_column("mikrotik_devices", "latitude")
    op.drop_column("clients", "longitude")
    op.drop_column("clients", "latitude")
