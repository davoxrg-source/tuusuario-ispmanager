import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class TicketStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_CLIENT = "waiting_client"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(str, enum.Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    INSTALLATION = "installation"
    OTHER = "other"


class Ticket(Base, TimestampMixin):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    # Un ticket lo crea el staff (User) O el propio cliente desde el portal
    # (Client) -- exactamente uno de los dos está seteado, nunca ambos ni
    # ninguno; se valida en la ruta que crea el ticket, no acá.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    subject: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)

    status: Mapped[TicketStatus] = mapped_column(pg_enum(TicketStatus, "ticket_status"), default=TicketStatus.OPEN)
    priority: Mapped[TicketPriority] = mapped_column(
        pg_enum(TicketPriority, "ticket_priority"), default=TicketPriority.MEDIUM
    )
    category: Mapped[TicketCategory] = mapped_column(
        pg_enum(TicketCategory, "ticket_category"), default=TicketCategory.OTHER
    )

    # foreign_keys explícito: ahora hay 2 FKs a clients.id en esta tabla
    # (client_id y created_by_client_id), sin esto SQLAlchemy no sabe cuál
    # usar para esta relación.
    client: Mapped["Client"] = relationship(foreign_keys=[client_id])  # noqa: F821
    replies: Mapped[list["TicketReply"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="TicketReply.created_at"
    )


class TicketReply(Base):
    __tablename__ = "ticket_replies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id"))
    # Mismo criterio que Ticket.created_by_*: exactamente uno de los dos.
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="replies")
