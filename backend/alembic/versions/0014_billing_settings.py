"""billing settings (fila única, configurable desde la UI)

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-23

"""
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    proration_target = postgresql.ENUM(
        "current_invoice", "next_invoice", name="proration_target", create_type=False
    )
    reconnection_fee_mode = postgresql.ENUM(
        "off", "on_suspend", "on_next_invoice", name="reconnection_fee_mode", create_type=False
    )
    for enum_type in (proration_target, reconnection_fee_mode):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "billing_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("generate_invoice_days_before_due", sa.Integer, nullable=False, server_default="0"),
        sa.Column("suspend_days_after_due", sa.Integer, nullable=False, server_default="5"),
        sa.Column("proration_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("proration_min_days", sa.Integer, nullable=False, server_default="1"),
        sa.Column("proration_target", proration_target, nullable=False, server_default="next_invoice"),
        sa.Column("late_fee_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("late_fee_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("late_fee_apply_hour", sa.Integer, nullable=False, server_default="6"),
        sa.Column(
            "reconnection_fee_mode", reconnection_fee_mode, nullable=False, server_default="off"
        ),
        sa.Column("reconnection_fee_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("invoice_folio_prefix", sa.String(20), nullable=False, server_default=""),
        sa.Column("invoice_folio_next_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )
    # Siembra una única fila con los defaults -- get_billing_settings() nunca
    # tiene que manejar "todavía no hay fila" como caso normal. UUID generado
    # en Python (no gen_random_uuid()) para no depender de pgcrypto.
    op.execute(f"INSERT INTO billing_settings (id) VALUES ('{uuid.uuid4()}')")


def downgrade() -> None:
    op.drop_table("billing_settings")

    bind = op.get_bind()
    postgresql.ENUM(name="reconnection_fee_mode").drop(bind, checkfirst=True)
    postgresql.ENUM(name="proration_target").drop(bind, checkfirst=True)
