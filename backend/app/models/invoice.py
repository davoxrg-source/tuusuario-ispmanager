import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))

    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)

    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[InvoiceStatus] = mapped_column(
        pg_enum(InvoiceStatus, "invoice_status"), default=InvoiceStatus.PENDING
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Prórroga puntual otorgada a este cliente/factura (ver
    # POST /invoices/{id}/promise-to-pay) -- mientras esté vigente,
    # suspend_clients_with_overdue_invoices no suspende por esta factura
    # aunque ya haya pasado el umbral de gracia configurado.
    promise_to_pay_until: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Mora automática (ver services/billing/invoicing.apply_late_fees) --
    # late_fee_applied_at sirve de guardia para no volver a aplicarla en
    # corridas posteriores del job diario.
    late_fee_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    late_fee_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Guard contra re-notificar cada día dentro de la ventana de
    # recordatorio -- mismo patrón exacto que late_fee_applied_at (ver
    # services/notifications, send_payment_reminders).
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Folio secuencial (prefijo + número configurables, ver BillingSettings).
    # Nullable porque facturas ya existentes antes de esta migración no
    # tienen uno asignado retroactivamente.
    folio: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)

    client: Mapped["Client"] = relationship(back_populates="invoices")  # noqa: F821
    payments: Mapped[list["Payment"]] = relationship(  # noqa: F821
        back_populates="invoice", cascade="all, delete-orphan"
    )
    payment_reports: Mapped[list["PaymentReport"]] = relationship(  # noqa: F821
        back_populates="invoice", cascade="all, delete-orphan"
    )
