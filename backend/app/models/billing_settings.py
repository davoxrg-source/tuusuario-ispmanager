import enum
import uuid

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class ProrationTarget(str, enum.Enum):
    CURRENT_INVOICE = "current_invoice"
    NEXT_INVOICE = "next_invoice"


class ReconnectionFeeMode(str, enum.Enum):
    OFF = "off"
    ON_SUSPEND = "on_suspend"
    ON_NEXT_INVOICE = "on_next_invoice"


class BillingSettings(Base, TimestampMixin):
    """Fila única con las reglas de facturación configurables desde la UI
    (ver Settings.tsx) -- reemplaza constantes que antes estaban
    hardcodeadas en invoicing.py/billing.py. Sin caché: es una sola fila,
    cachearla reintroduciría el problema de "hay que reiniciar para que
    tome el cambio" que esto busca evitar (ver services/billing/settings.py)."""

    __tablename__ = "billing_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    generate_invoice_days_before_due: Mapped[int] = mapped_column(Integer, default=0)
    suspend_days_after_due: Mapped[int] = mapped_column(Integer, default=5)

    proration_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    proration_min_days: Mapped[int] = mapped_column(Integer, default=1)
    proration_target: Mapped[ProrationTarget] = mapped_column(
        pg_enum(ProrationTarget, "proration_target"), default=ProrationTarget.NEXT_INVOICE
    )

    late_fee_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    late_fee_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    late_fee_apply_hour: Mapped[int] = mapped_column(Integer, default=6)

    reconnection_fee_mode: Mapped[ReconnectionFeeMode] = mapped_column(
        pg_enum(ReconnectionFeeMode, "reconnection_fee_mode"), default=ReconnectionFeeMode.OFF
    )
    reconnection_fee_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    invoice_folio_prefix: Mapped[str] = mapped_column(String(20), default="")
    invoice_folio_next_number: Mapped[int] = mapped_column(Integer, default=1)
