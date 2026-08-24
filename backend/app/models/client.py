import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
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

    # IP pública entregada por proxy-ARP (distinta de ip_address, que es la
    # IP privada de LAN usada para QoS/suspensión) -- reemplaza el
    # procedimiento manual con `arp -Ds` del sistema legacy (ver
    # services/mikrotik/device_service.provision_client_public_ip). Los 3
    # campos van juntos: sin interfaz de proveedor/LAN no hay dónde aplicar
    # el proxy-ARP ni la ruta.
    public_ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    public_ip_provider_interface: Mapped[str | None] = mapped_column(String(60), nullable=True)
    public_ip_lan_interface: Mapped[str | None] = mapped_column(String(60), nullable=True)

    status: Mapped[ClientStatus] = mapped_column(
        pg_enum(ClientStatus, "client_status"), default=ClientStatus.ACTIVE
    )

    # Conectividad real (no facturación): ¿su IP tiene una entrada ARP
    # 'complete' en su Mikrotik ahora mismo? Lo actualiza el poller en cada
    # ciclo (ver workers/poller.py, DeviceService.get_online_ip_set) --
    # nunca se setea a mano. Distinto de `status`, que es el estado
    # administrativo/de facturación del contrato.
    is_online: Mapped[bool] = mapped_column(default=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Crédito de prorrateo (ver services/billing/invoicing.apply_proration_if_needed
    # con proration_target=NEXT_INVOICE) y bandera de cargo de reconexión
    # (reconnection_fee_mode=ON_NEXT_INVOICE) pendientes de aplicar en la
    # próxima factura -- se consumen y resetean en generate_monthly_invoices.
    pending_credit: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    pending_reconnection_fee: Mapped[bool] = mapped_column(Boolean, default=False)

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
