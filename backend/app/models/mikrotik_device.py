import enum
import uuid

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class DeviceStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class MikrotikDevice(Base, TimestampMixin):
    __tablename__ = "mikrotik_devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    site: Mapped[str | None] = mapped_column(String(120), nullable=True)
    host: Mapped[str] = mapped_column(String(255))
    # Dirección física, estable aunque la IP cambie. Usada para redescubrir el
    # equipo por MNDP si la IP guardada deja de responder (ver services/mikrotik/discovery.py).
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True, index=True)
    api_port: Mapped[int] = mapped_column(Integer, default=8728)
    api_use_tls: Mapped[bool] = mapped_column(default=False)
    ssh_port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(120))
    # Contraseña cifrada con Fernet (ver app.core.security). Nunca en texto plano.
    encrypted_password: Mapped[str] = mapped_column(String(500))

    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    routeros_version: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Si ya se le habilitó el export NetFlow hacia el colector de ispmanager
    # (ver services/netflow/collector.py) -- evita reconfigurarlo en cada
    # ciclo del poller, solo se hace una vez por equipo.
    traffic_flow_configured: Mapped[bool] = mapped_column(default=False)

    status: Mapped[DeviceStatus] = mapped_column(
        pg_enum(DeviceStatus, "device_status"), default=DeviceStatus.UNKNOWN
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    clients: Mapped[list["Client"]] = relationship(back_populates="mikrotik_device")  # noqa: F821
    metrics: Mapped[list["DeviceMetric"]] = relationship(  # noqa: F821
        back_populates="device", cascade="all, delete-orphan"
    )
