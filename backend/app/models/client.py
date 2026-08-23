import enum
import uuid

from sqlalchemy import ForeignKey, Integer, String
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
    # 120, no 40: en la práctica el teléfono es texto casi libre (varios
    # números, notas como "titular") — visto migrando datos reales desde
    # sequreisp_production, donde llega a 70 caracteres.
    phone: Mapped[str | None] = mapped_column(String(120), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plans.id"), nullable=True)
    mikrotik_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mikrotik_devices.id"), nullable=True
    )

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    status: Mapped[ClientStatus] = mapped_column(
        pg_enum(ClientStatus, "client_status"), default=ClientStatus.ACTIVE
    )

    # id del contrato en el sistema legacy (sequreisp_production) que este
    # registro reemplaza — cada contrato legacy es un cliente acá (un
    # cliente legacy con 2 contratos activos queda como 2 registros, uno
    # por servicio). Permite re-correr scripts/migrate_from_sequreisp.py
    # sin duplicar clientes ya importados.
    legacy_contract_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)

    plan: Mapped["Plan"] = relationship(back_populates="clients")  # noqa: F821
    mikrotik_device: Mapped["MikrotikDevice"] = relationship(back_populates="clients")  # noqa: F821
    invoices: Mapped[list["Invoice"]] = relationship(  # noqa: F821
        back_populates="client", cascade="all, delete-orphan"
    )
