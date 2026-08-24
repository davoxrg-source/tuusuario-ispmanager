"""acceso al portal del cliente + reportes de pago pendientes de verificación

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("clients", sa.Column("hashed_password", sa.String(255), nullable=True))

    # created_by_user_id/author_user_id eran NOT NULL -- hasta ahora solo el
    # staff creaba tickets/respuestas. Se aflojan para permitir que un
    # cliente autenticado en el portal cree su propio ticket/respuesta, sin
    # inventar un User "sistema" que finja ser el autor.
    op.alter_column("tickets", "created_by_user_id", nullable=True)
    op.add_column(
        "tickets",
        sa.Column("created_by_client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True),
    )
    op.alter_column("ticket_replies", "author_user_id", nullable=True)
    op.add_column(
        "ticket_replies",
        sa.Column("author_client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=True),
    )

    payment_report_status = postgresql.ENUM(
        "pending", "confirmed", "rejected", name="payment_report_status", create_type=False
    )
    payment_report_status.create(bind, checkfirst=True)

    op.create_table(
        "payment_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Sin ondelete propio -- mismo criterio que Payment.invoice_id: la
        # cascada real pasa por el ORM (Invoice.payment_reports,
        # cascade="all, delete-orphan"), que a su vez cuelga de
        # Client.invoices, ya cascada hoy.
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", sa.String(60), nullable=False),
        sa.Column("reference", sa.String(120), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("status", payment_report_status, nullable=False, server_default="pending"),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payment_reports_client_id", "payment_reports", ["client_id"])
    op.create_index("ix_payment_reports_invoice_id", "payment_reports", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_reports_invoice_id", table_name="payment_reports")
    op.drop_index("ix_payment_reports_client_id", table_name="payment_reports")
    op.drop_table("payment_reports")

    bind = op.get_bind()
    postgresql.ENUM(name="payment_report_status").drop(bind, checkfirst=True)

    op.drop_column("ticket_replies", "author_client_id")
    op.alter_column("ticket_replies", "author_user_id", nullable=False)
    op.drop_column("tickets", "created_by_client_id")
    op.alter_column("tickets", "created_by_user_id", nullable=False)

    op.drop_column("clients", "hashed_password")
