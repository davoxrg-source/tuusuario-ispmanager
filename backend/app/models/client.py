import enum
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class ClientStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(160))
    identification: Mapped[str | None] = mapped_column(String(60), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    mikrotik_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mikrotik_devices.id"), nullable=True
    )

    pppoe_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Contraseña PPPoE cifrada con Fernet. Nunca en texto plano.
    encrypted_pppoe_password: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    status: Mapped[ClientStatus] = mapped_column(
        pg_enum(ClientStatus, "client_status"), default=ClientStatus.ACTIVE
    )

    plan: Mapped["Plan"] = relationship(back_populates="clients")  # noqa: F821
    mikrotik_device: Mapped["MikrotikDevice"] = relationship(back_populates="clients")  # noqa: F821
    invoices: Mapped[list["Invoice"]] = relationship(  # noqa: F821
        back_populates="client", cascade="all, delete-orphan"
    )
