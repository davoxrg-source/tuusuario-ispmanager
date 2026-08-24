import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.db.types import pg_enum


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    PUSH = "push"


class NotificationStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"


class Notification(Base):
    """Un intento de aviso a un cliente (correo o push) -- éxito o fracaso,
    uno por canal por evento (ver app/services/notifications/service.py).
    Sin TimestampMixin: es un log de un evento puntual, como PollAttempt/
    TicketReply, no algo que se actualiza."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))
    channel: Mapped[NotificationChannel] = mapped_column(pg_enum(NotificationChannel, "notification_channel"))
    event_type: Mapped[str] = mapped_column(String(60))
    # Congelado al momento del envío -- el email/endpoint usado, no una
    # referencia viva que cambie si el cliente edita su perfil después.
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[NotificationStatus] = mapped_column(pg_enum(NotificationStatus, "notification_status"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
