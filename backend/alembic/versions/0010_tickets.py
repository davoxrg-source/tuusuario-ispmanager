"""support ticket system

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    ticket_status = postgresql.ENUM(
        "open", "in_progress", "waiting_client", "resolved", "closed", name="ticket_status", create_type=False
    )
    ticket_priority = postgresql.ENUM(
        "low", "medium", "high", "urgent", name="ticket_priority", create_type=False
    )
    ticket_category = postgresql.ENUM(
        "billing", "technical", "installation", "other", name="ticket_category", create_type=False
    )
    for enum_type in (ticket_status, ticket_priority, ticket_category):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id")),
        sa.Column(
            "created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("assigned_to_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", ticket_status, nullable=False, server_default="open"),
        sa.Column("priority", ticket_priority, nullable=False, server_default="medium"),
        sa.Column("category", ticket_category, nullable=False, server_default="other"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "ticket_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column(
            "author_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ticket_replies")
    op.drop_table("tickets")

    bind = op.get_bind()
    postgresql.ENUM(name="ticket_category").drop(bind, checkfirst=True)
    postgresql.ENUM(name="ticket_priority").drop(bind, checkfirst=True)
    postgresql.ENUM(name="ticket_status").drop(bind, checkfirst=True)
