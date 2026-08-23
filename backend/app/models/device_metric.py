import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class DeviceMetric(Base):
    __tablename__ = "device_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mikrotik_devices.id"))

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    cpu_load_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # BigInteger, no Integer: un equipo con 4GB+ de RAM ya desborda un
    # int32 de Postgres (4294967296 > 2147483647) — pasó de verdad con el
    # CCR2004 real, tumbando cada ciclo del poller de métricas.
    memory_used_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    memory_total_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uptime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_ppp_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # snapshot libre de estadísticas de interfaces: [{name, rx_bytes, tx_bytes}, ...]
    interfaces: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    device: Mapped["MikrotikDevice"] = relationship(back_populates="metrics")  # noqa: F821
