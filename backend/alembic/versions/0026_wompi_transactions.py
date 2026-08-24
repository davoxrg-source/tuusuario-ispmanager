"""pasarela de pago Wompi -- transacciones de checkout

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    wompi_transaction_status = postgresql.ENUM(
        "pending", "approved", "declined", "voided", "error",
        name="wompi_transaction_status", create_type=False,
    )
    wompi_transaction_status.create(bind, checkfirst=True)

    op.create_table(
        "wompi_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        # Única por INTENTO de pago, no por factura -- un reintento tras un
        # pago fallido genera una referencia nueva (ver docs de Wompi sobre
        # evitar transacciones duplicadas accidentales).
        sa.Column("reference", sa.String(64), nullable=False, unique=True),
        # El id que Wompi le asigna a la transacción -- llega recién en el
        # webhook, no existe todavía cuando creamos el link de pago.
        sa.Column("wompi_transaction_id", sa.String(64), nullable=True),
        sa.Column("amount_in_cents", sa.Integer, nullable=False),
        sa.Column("status", wompi_transaction_status, nullable=False, server_default="pending"),
        # JSON crudo del último webhook recibido -- para poder auditar/
        # debuggear sin depender de que Wompi lo reenvíe.
        sa.Column("raw_webhook_payload", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )
    op.create_index("ix_wompi_transactions_invoice_id", "wompi_transactions", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_wompi_transactions_invoice_id", table_name="wompi_transactions")
    op.drop_table("wompi_transactions")

    bind = op.get_bind()
    postgresql.ENUM(name="wompi_transaction_status").drop(bind, checkfirst=True)
