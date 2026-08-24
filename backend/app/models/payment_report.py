import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import pg_enum


class PaymentReportStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class PaymentReport(Base):
    """Un cliente reporta desde el portal que ya pagó una factura -- no
    marca nada como pagado por sí solo, queda 'pending' hasta que un
    miembro del staff lo confirma o rechaza (ver POST
    /payment-reports/{id}/confirm en billing.py, que reutiliza la misma
    lógica que ya marca una factura pagada en pay_invoice)."""

    __tablename__ = "payment_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id"))

    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    method: Mapped[str] = mapped_column(String(60))
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[PaymentReportStatus] = mapped_column(
        pg_enum(PaymentReportStatus, "payment_report_status"), default=PaymentReportStatus.PENDING
    )
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="payment_reports")  # noqa: F821
    client: Mapped["Client"] = relationship()  # noqa: F821
