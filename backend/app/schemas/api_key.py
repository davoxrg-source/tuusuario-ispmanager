import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None = None
    created_at: datetime


class ApiKeyCreateResult(ApiKeyRead):
    """Igual que ApiKeyRead pero con la clave en texto plano -- solo viaja
    en la respuesta de POST /api-keys, nunca se puede volver a leer después."""

    key: str
