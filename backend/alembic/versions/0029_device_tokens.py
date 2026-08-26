"""tokens de push nativo (FCM) para las apps móviles

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

device_owner_type = postgresql.ENUM("client", "user", name="device_owner_type", create_type=False)


def upgrade() -> None:
    device_owner_type.create(op.get_bind(), checkfirst=True)

    # notification_channel gana 'fcm' (push nativo de las apps móviles,
    # distinto del 'push' de Web Push) -- ALTER TYPE ... ADD VALUE no puede
    # correr en la misma transacción que lo agrega, mismo patrón que la
    # migración 0018 (user_role) y el agregado de payment_reminders en 0025.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_channel ADD VALUE IF NOT EXISTS 'fcm'")

    op.create_table(
        "device_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_type", device_owner_type, nullable=False),
        # Sin FK real a clients/users: sería una FK condicional según
        # owner_type, que Postgres no soporta nativo. Se valida en la ruta.
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fcm_token", sa.String(255), nullable=False, unique=True),
        sa.Column("platform", sa.String(20), nullable=False, server_default="android"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_device_tokens_owner", "device_tokens", ["owner_type", "owner_id"])

    # notifications.client_id pasa a nullable + gana user_id nullable --
    # mismo patrón "dueño A o dueño B, exactamente uno" que
    # tickets.created_by_user_id/created_by_client_id (migración 0024),
    # para poder registrar notificaciones al staff (notify_user), no solo
    # a clientes.
    op.alter_column("notifications", "client_id", nullable=True)
    op.add_column(
        "notifications",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_column("notifications", "user_id")
    op.alter_column("notifications", "client_id", nullable=False)

    op.drop_index("ix_device_tokens_owner", table_name="device_tokens")
    op.drop_table("device_tokens")
    device_owner_type.drop(op.get_bind(), checkfirst=True)
