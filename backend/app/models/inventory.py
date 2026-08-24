import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class MovementReason(str, enum.Enum):
    PURCHASE = "purchase"
    ASSIGNMENT = "assignment"
    INSTALLATION = "installation"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    LOSS = "loss"


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    phone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    items: Mapped[list["InventoryItem"]] = relationship(back_populates="supplier")


class InventoryItem(Base, TimestampMixin):
    """Stock actual guardado directo en la fila (no recalculado sumando
    movimientos en cada consulta) -- mismo criterio que Invoice.amount:
    un valor actual + un log aparte para el historial (ver InventoryMovement)."""

    __tablename__ = "inventory_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    # Texto libre, no enum -- mismo criterio que PaymentAccount.kind: el
    # conjunto real (router, antena, cable...) lo define el usuario.
    category: Mapped[str] = mapped_column(String(60), default="otro")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    supplier: Mapped["Supplier"] = relationship(back_populates="items")
    movements: Mapped[list["InventoryMovement"]] = relationship(back_populates="item")


class InventoryMovement(Base):
    """Log de auditoría de un solo evento -- no se edita ni se borra, por
    eso no lleva TimestampMixin (solo created_at), mismo criterio que
    PollAttempt/TicketReply."""

    __tablename__ = "inventory_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_items.id"))
    reason: Mapped[MovementReason] = mapped_column(pg_enum(MovementReason, "movement_reason"))
    quantity_delta: Mapped[int] = mapped_column(Integer)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped["InventoryItem"] = relationship(back_populates="movements")
