import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin


class PaymentAccount(Base, TimestampMixin):
    """Cuenta/forma de pago real del negocio (efectivo, Nequi, una cuenta
    bancaria puntual) -- permite reportar saldo por cuenta en vez de un
    solo total agregado (ver GET /billing/balance-by-account). `kind` es
    texto libre, no enum: el conjunto real lo define el usuario, no es un
    vocabulario fijo."""

    __tablename__ = "payment_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    kind: Mapped[str] = mapped_column(String(30), default="other")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
