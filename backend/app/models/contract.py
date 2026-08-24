import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin
from app.db.types import pg_enum


class ContractStatus(str, enum.Enum):
    DRAFT = "draft"
    SIGNED = "signed"
    VOID = "void"


class ContractTemplate(Base, TimestampMixin):
    __tablename__ = "contract_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    body: Mapped[str] = mapped_column(Text)


class Contract(Base, TimestampMixin):
    """Firma simple en pantalla, no firma digital certificada -- ver
    app/services/contracts.py y el docstring de la ruta de firma. El texto
    queda congelado en `rendered_body` al crearse (no se re-renderiza si la
    plantilla o el cliente cambian después)."""

    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contract_templates.id", ondelete="SET NULL"), nullable=True
    )
    rendered_body: Mapped[str] = mapped_column(Text)
    status: Mapped[ContractStatus] = mapped_column(
        pg_enum(ContractStatus, "contract_status"), default=ContractStatus.DRAFT
    )

    signer_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    signer_identification: Mapped[str | None] = mapped_column(String(60), nullable=True)
    signature_image: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signer_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    witnessed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
