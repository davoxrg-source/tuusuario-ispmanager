import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ClientTrafficUsage(Base):
    """Uso de tráfico por cliente, agregado en buckets de una hora a partir
    de exports NetFlow v5 del Mikrotik (ver services/netflow/collector.py).
    No es un registro por-flujo -- eso explotaría la base -- es un contador
    acumulado por (cliente, hora)."""

    __tablename__ = "client_traffic_usage"
    __table_args__ = (
        UniqueConstraint("client_id", "bucket_start", name="uq_client_traffic_usage_client_bucket"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mikrotik_devices.id"))

    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    # BigInteger: mismo motivo que DeviceMetric.memory_used_bytes (ver ese
    # modelo) -- bytes acumulados por hora superan un int32 con facilidad.
    bytes_in: Mapped[int] = mapped_column(BigInteger, default=0)
    bytes_out: Mapped[int] = mapped_column(BigInteger, default=0)
    packets_in: Mapped[int] = mapped_column(BigInteger, default=0)
    packets_out: Mapped[int] = mapped_column(BigInteger, default=0)
