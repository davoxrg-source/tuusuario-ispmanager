import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.db.types import pg_enum


class DeviceOwnerType(str, enum.Enum):
    CLIENT = "client"
    USER = "user"


class DeviceToken(Base):
    """Token FCM (Firebase Cloud Messaging) de una app móvil nativa --
    mecanismo de entrega totalmente distinto al Web Push del navegador (ver
    PushSubscription): un token FCM es un string opaco, sin la forma
    endpoint/p256dh/auth del protocolo Web Push, así que no comparte tabla
    ni proveedor de envío con esa.

    Un solo modelo para ambas apps (cliente y staff), diferenciado por
    owner_type/owner_id en vez de 2 tablas gemelas -- la lógica de guardar/
    borrar es idéntica para los dos casos. Sin TimestampMixin: no se
    actualiza, solo se crea o se borra (igual que PushSubscription)."""

    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_type: Mapped[DeviceOwnerType] = mapped_column(pg_enum(DeviceOwnerType, "device_owner_type"))
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    fcm_token: Mapped[str] = mapped_column(String(255), unique=True)
    platform: Mapped[str] = mapped_column(String(20), default="android")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
