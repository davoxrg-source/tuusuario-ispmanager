import uuid

from pydantic import BaseModel, ConfigDict

from app.models.client import ClientStatus


class ClientBase(BaseModel):
    full_name: str
    identification: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    plan_id: uuid.UUID | None = None
    mikrotik_device_id: uuid.UUID | None = None
    pppoe_username: str | None = None
    ip_address: str | None = None


class ClientCreate(ClientBase):
    pppoe_password: str | None = None


class ClientUpdate(BaseModel):
    full_name: str | None = None
    identification: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    plan_id: uuid.UUID | None = None
    mikrotik_device_id: uuid.UUID | None = None
    pppoe_username: str | None = None
    pppoe_password: str | None = None
    ip_address: str | None = None


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ClientStatus
