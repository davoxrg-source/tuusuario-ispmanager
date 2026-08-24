import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))

    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    method: Mapped[str] = mapped_column(String(60))
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Cuenta/forma de pago real para reconciliación (ver GET
    # /billing/balance-by-account). Nullable y coexiste con `method` (texto
    # libre, sin tocar) -- pagos viejos no tienen esto asignado.
    payment_account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("payment_accounts.id"), nullable=True
    )

    invoice: Mapped["Invoice"] = relationship(back_populates="payments")  # noqa: F821
    payment_account: Mapped["PaymentAccount"] = relationship()  # noqa: F821
