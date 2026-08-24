import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base, TimestampMixin


class ApiKey(Base, TimestampMixin):
    """Credencial de larga duración para integraciones externas (ver
    app/api/routes/external_api.py) -- a diferencia de un JWT de User/
    Client, no expira y no requiere un login humano. Se actualiza
    (is_active, last_used_at), así que a diferencia de un log de un solo
    evento (PollAttempt/Notification) sí lleva TimestampMixin."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    key_prefix: Mapped[str] = mapped_column(String(12))
    hashed_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
