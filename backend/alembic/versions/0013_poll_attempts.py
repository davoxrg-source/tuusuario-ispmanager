"""poll attempts (retry + log de tareas periódicas)

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    poll_job_type = postgresql.ENUM(
        "device_poll",
        "client_online_status",
        "daily_billing",
        "traffic_maintenance",
        name="poll_job_type",
        create_type=False,
    )
    poll_attempt_status = postgresql.ENUM(
        "success", "failure", name="poll_attempt_status", create_type=False
    )
    for enum_type in (poll_job_type, poll_attempt_status):
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "poll_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("mikrotik_devices.id")),
        sa.Column("job_type", poll_job_type, nullable=False),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("max_attempts", sa.Integer, nullable=False),
        sa.Column("status", poll_attempt_status, nullable=False),
        sa.Column("error_message", sa.Text),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_poll_attempts_device_attempted", "poll_attempts", ["device_id", "attempted_at"]
    )
    op.create_index(
        "ix_poll_attempts_status_attempted", "poll_attempts", ["status", "attempted_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_poll_attempts_status_attempted", table_name="poll_attempts")
    op.drop_index("ix_poll_attempts_device_attempted", table_name="poll_attempts")
    op.drop_table("poll_attempts")

    bind = op.get_bind()
    postgresql.ENUM(name="poll_attempt_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="poll_job_type").drop(bind, checkfirst=True)
