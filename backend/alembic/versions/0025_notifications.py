"""notificaciones (correo/push), recordatorios de pago, suscripciones push

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ALTER TYPE ... ADD VALUE no puede correr en la misma transacción que
    # lo agrega -- este proyecto corre todas las migraciones pendientes de
    # un `alembic upgrade head` en una sola transacción, así que hace falta
    # aislarlo (mismo patrón que la migración 0018 con `finance`).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE poll_job_type ADD VALUE IF NOT EXISTS 'payment_reminders'")

    notification_channel = postgresql.ENUM(
        "email", "push", name="notification_channel", create_type=False
    )
    notification_channel.create(bind, checkfirst=True)
    notification_status = postgresql.ENUM(
        "sent", "failed", name="notification_status", create_type=False
    )
    notification_status.create(bind, checkfirst=True)

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("channel", notification_channel, nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        # Congelado al momento del envío -- el email/endpoint usado, no una
        # referencia que cambie si el cliente edita su perfil después.
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", notification_status, nullable=False),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_client_id", "notifications", ["client_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.create_table(
        "push_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("endpoint", sa.Text, nullable=False, unique=True),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_push_subscriptions_client_id", "push_subscriptions", ["client_id"])

    op.add_column("invoices", sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "billing_settings",
        sa.Column("payment_reminder_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "billing_settings",
        sa.Column("payment_reminder_days_before_due", sa.Integer, nullable=False, server_default="3"),
    )


def downgrade() -> None:
    op.drop_column("billing_settings", "payment_reminder_days_before_due")
    op.drop_column("billing_settings", "payment_reminder_enabled")
    op.drop_column("invoices", "reminder_sent_at")

    op.drop_index("ix_push_subscriptions_client_id", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")

    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_client_id", table_name="notifications")
    op.drop_table("notifications")

    bind = op.get_bind()
    postgresql.ENUM(name="notification_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="notification_channel").drop(bind, checkfirst=True)

    # Postgres no tiene DROP VALUE para enums -- mismo motivo/documentación
    # que la migración 0018, no vale la pena reconstruir el tipo entero
    # para un downgrade rutinario.