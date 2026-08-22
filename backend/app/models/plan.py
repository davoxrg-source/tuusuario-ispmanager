import uuid

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    download_speed_mbps: Mapped[int] = mapped_column()
    upload_speed_mbps: Mapped[int] = mapped_column()
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Piso garantizado de ancho de banda (% de download/upload_speed_mbps) que
    # el cliente mantiene incluso con el enlace saturado; puede hacer ráfaga
    # hasta el 100% del plan cuando hay banda libre. 9% replica el valor
    # observado en el sistema legacy que este plan reemplaza (ver qos.py).
    guaranteed_floor_percent: Mapped[int] = mapped_column(default=9)

    # id del plan en el sistema legacy (sequreisp_production) que este
    # registro reemplaza — permite re-correr scripts/migrate_from_sequreisp.py
    # sin duplicar planes ya importados.
    legacy_plan_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)

    clients: Mapped[list["Client"]] = relationship(back_populates="plan")  # noqa: F821
