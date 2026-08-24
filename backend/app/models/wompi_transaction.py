import enum
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class WompiTransactionStatus(str, enum.Enum):
    """Calca el vocabulario de estados de Wompi tal cual -- es un
    passthrough de un sistema externo, no un concepto de negocio propio."""

    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    VOIDED = "voided"
    ERROR = "error"


class WompiTransaction(Base, TimestampMixin):
    """Un intento de pago en línea vía Wompi para una factura (ver
    app/services/wompi/). A diferencia de PaymentReport (el cliente dice
    que pagó, sin verificar), esto lo confirma Wompi mismo por webhook
    firmado -- no necesita revisión de staff."""

    __tablename__ = "wompi_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("invoices.id"))
    reference: Mapped[str] = mapped_column(String(64), unique=True)
    wompi_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_in_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[WompiTransactionStatus] = mapped_column(
        pg_enum(WompiTransactionStatus, "wompi_transaction_status"), default=WompiTransactionStatus.PENDING
    )
    raw_webhook_payload: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped["Invoice"] = relationship(back_populates="wompi_transactions")  # noqa: F821
