"""widen device_metrics memory columns to bigint (4GB+ RAM overflows int32)

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "device_metrics", "memory_used_bytes", type_=sa.BigInteger(), existing_type=sa.Integer()
    )
    op.alter_column(
        "device_metrics", "memory_total_bytes", type_=sa.BigInteger(), existing_type=sa.Integer()
    )


def downgrade() -> None:
    op.alter_column(
        "device_metrics", "memory_used_bytes", type_=sa.Integer(), existing_type=sa.BigInteger()
    )
    op.alter_column(
        "device_metrics", "memory_total_bytes", type_=sa.Integer(), existing_type=sa.BigInteger()
    )
