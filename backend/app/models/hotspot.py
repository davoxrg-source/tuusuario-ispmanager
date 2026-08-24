import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class HotspotVoucherStatus(str, enum.Enum):
    UNUSED = "unused"
    SOLD = "sold"
    VOID = "void"


class HotspotProfile(Base, TimestampMixin):
    """Qué otorga una ficha (tiempo y/o datos) y su precio -- mismo rol que
    Plan para el negocio postpago, pero una entidad separada: un perfil de
    ficha no tiene velocidad de bajada/subida ni piso garantizado."""

    __tablename__ = "hotspot_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_limit_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    vouchers: Mapped[list["HotspotVoucher"]] = relationship(back_populates="profile")


class HotspotVoucher(Base):
    """Una ficha concreta, generada en lote (batch_id). Sin TimestampMixin
    completo -- solo created_at, ya que cada transición de estado tiene su
    propio timestamp dedicado (sold_at/voided_at), mismo criterio que
    PaymentReport (reported_at/reviewed_at en vez de un updated_at genérico).

    Esta fase NO empuja nada a un Mikrotik real (ver services/hotspot/) --
    por eso no existe un estado "usada/redimida": trackear eso sin
    integración real con el router sería inventar un dato no verificable."""

    __tablename__ = "hotspot_vouchers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hotspot_profiles.id"))
    code: Mapped[str] = mapped_column(String(8), unique=True)
    # Congelado del precio del perfil al momento de generar la ficha -- una
    # ficha ya impresa no puede cambiar de precio retroactivamente si
    # alguien edita el perfil después.
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[HotspotVoucherStatus] = mapped_column(
        pg_enum(HotspotVoucherStatus, "hotspot_voucher_status"), default=HotspotVoucherStatus.UNUSED
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sold_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped["HotspotProfile"] = relationship(back_populates="vouchers")
