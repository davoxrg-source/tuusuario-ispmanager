import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.db.types import pg_enum


class PollJobType(str, enum.Enum):
    DEVICE_POLL = "device_poll"
    CLIENT_ONLINE_STATUS = "client_online_status"
    DAILY_BILLING = "daily_billing"
    TRAFFIC_MAINTENANCE = "traffic_maintenance"
    PAYMENT_REMINDERS = "payment_reminders"


class PollAttemptStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class PollAttempt(Base):
    """Un intento (éxito o fallo) de un job de background -- ver
    app/workers/retry.py y app/workers/poller.py. device_id es NULL para
    jobs que no son por-dispositivo (facturación diaria, purga de tráfico).
    max_attempts se guarda por fila (no se relee de Settings después) para
    que una fila vieja se siga entendiendo aunque cambie la config."""

    __tablename__ = "poll_attempts"
    __table_args__ = (
        Index("ix_poll_attempts_device_attempted", "device_id", "attempted_at"),
        Index("ix_poll_attempts_status_attempted", "status", "attempted_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mikrotik_devices.id"), nullable=True
    )
    job_type: Mapped[PollJobType] = mapped_column(pg_enum(PollJobType, "poll_job_type"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer)
    status: Mapped[PollAttemptStatus] = mapped_column(pg_enum(PollAttemptStatus, "poll_attempt_status"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
