import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole
from app.schemas.zone import ZoneRead


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.TECHNICIAN
    zone_ids: list[uuid.UUID] = []


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
    zone_ids: list[uuid.UUID] | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    zones: list[ZoneRead] = []


class StaffNameRead(BaseModel):
    """Solo id + nombre -- para poblar selects (ej. a qué técnico se le
    asigna material en Almacén) sin exponer correo/rol/zonas de todo el
    personal a un no-admin. Ver GET /users/directory."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
