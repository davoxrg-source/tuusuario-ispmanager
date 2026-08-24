"""agenda de instalaciones

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    installation_status = postgresql.ENUM(
        "scheduled", "completed", "cancelled", name="installation_status", create_type=False
    )
    installation_status.create(bind, checkfirst=True)

    op.create_table(
        "installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # Sin ondelete a nivel de BD -- la cascada la maneja el ORM
        # (Client.installations, cascade="all, delete-orphan"), mismo
        # patrón que Client.invoices ya usa hoy.
        sa.Column(
            "client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False
        ),
        sa.Column(
            "assigned_technician_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column("status", installation_status, nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()
        ),
    )
    op.create_index("ix_installations_client_id", "installations", ["client_id"])
    op.create_index("ix_installations_scheduled_date", "installations", ["scheduled_date"])


def downgrade() -> None:
    op.drop_index("ix_installations_scheduled_date", table_name="installations")
    op.drop_index("ix_installations_client_id", table_name="installations")
    op.drop_table("installations")

    bind = op.get_bind()
    postgresql.ENUM(name="installation_status").drop(bind, checkfirst=True)
