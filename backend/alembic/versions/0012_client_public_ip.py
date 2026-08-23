"""add public IP (proxy-ARP delivery) fields to clients

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("public_ip_address", sa.String(45), nullable=True))
    op.add_column("clients", sa.Column("public_ip_provider_interface", sa.String(60), nullable=True))
    op.add_column("clients", sa.Column("public_ip_lan_interface", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("clients", "public_ip_lan_interface")
    op.drop_column("clients", "public_ip_provider_interface")
    op.drop_column("clients", "public_ip_address")
