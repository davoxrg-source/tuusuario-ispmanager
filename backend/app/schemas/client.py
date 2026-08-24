import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.client import ClientStatus


class ClientBase(BaseModel):
    full_name: str
    identification: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    plan_id: uuid.UUID | None = None
    mikrotik_device_id: uuid.UUID | None = None
    ip_address: str | None = None
    # IP pública por proxy-ARP (ver DeviceService.provision_client_public_ip)
    # -- los 3 campos van juntos, sin interfaz de proveedor/LAN no hay dónde
    # aplicarla.
    public_ip_address: str | None = None
    public_ip_provider_interface: str | None = None
    public_ip_lan_interface: str | None = None
    # Agrupación para acceso por rol (ver app/api/deps.py) -- opcional.
    zone_id: uuid.UUID | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    full_name: str | None = None
    identification: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    plan_id: uuid.UUID | None = None
    mikrotik_device_id: uuid.UUID | None = None
    ip_address: str | None = None
    public_ip_address: str | None = None
    public_ip_provider_interface: str | None = None
    public_ip_lan_interface: str | None = None
    zone_id: uuid.UUID | None = None


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ClientStatus
    is_online: bool
    last_seen_at: datetime | None = None
    portal_active: bool = False


class BulkClientAction(BaseModel):
    client_ids: list[uuid.UUID]


class PortalActivateRead(BaseModel):
    """Respuesta de activar/resetear el portal -- la contraseña en texto
    plano viaja UNA sola vez acá, nunca se puede volver a leer después."""

    password: str
