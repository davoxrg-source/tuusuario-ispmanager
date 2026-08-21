import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.mikrotik_device import DeviceStatus


class MikrotikDeviceBase(BaseModel):
    name: str
    site: str | None = None
    host: str
    mac_address: str | None = None
    api_port: int = 8728
    api_use_tls: bool = False
    ssh_port: int = 22
    username: str


class MikrotikDeviceCreate(MikrotikDeviceBase):
    password: str


class MikrotikDeviceUpdate(BaseModel):
    name: str | None = None
    site: str | None = None
    host: str | None = None
    mac_address: str | None = None
    api_port: int | None = None
    api_use_tls: bool | None = None
    ssh_port: int | None = None
    username: str | None = None
    password: str | None = None


class MikrotikDeviceRead(MikrotikDeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    model: str | None = None
    routeros_version: str | None = None
    status: DeviceStatus
    last_seen_at: datetime | None = None


class ConnectionTestResult(BaseModel):
    success: bool
    method: str
    message: str
    identity: str | None = None
    routeros_version: str | None = None
    uptime_seconds: int | None = None
    resolved_via_mac: bool = False
    updated_host: str | None = None


class DiscoveredDeviceRead(BaseModel):
    mac_address: str
    ip_address: str
    identity: str | None = None
    version: str | None = None
    platform: str | None = None
    seen_seconds_ago: float


class DeviceResourceStatus(BaseModel):
    cpu_load_percent: int | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    uptime_seconds: int | None = None
    active_ppp_sessions: int | None = None


class ActivePppSession(BaseModel):
    name: str
    address: str | None = None
    uptime: str | None = None
    caller_id: str | None = None


class ResetConfigurationRequest(BaseModel):
    # Acción destructiva: exige repetir el nombre exacto del equipo como
    # confirmación explícita, además del diálogo de confirmación del frontend.
    confirm_name: str
    no_defaults: bool = True
