import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.mikrotik_device import DeviceStatus

# Direcciones que nunca son un destino válido para conectarse a un equipo:
# 0.0.0.0 en particular suele "funcionar" a nivel de socket porque el propio
# sistema operativo la resuelve como localhost, lo que hace que el backend
# termine probando las credenciales del Mikrotik contra sí mismo — un fallo
# confuso de diagnosticar. Ver services/mikrotik/discovery.py: un equipo
# anunciándose por MNDP sin IP real en esa interfaz llega con esta dirección.
_UNROUTABLE_HOSTS = {"0.0.0.0", "255.255.255.255"}


def _reject_unroutable_host(value: str | None) -> str | None:
    if value is not None and value.strip() in _UNROUTABLE_HOSTS:
        raise ValueError(
            f"'{value}' no es una dirección válida para conectarse (nunca tiene un equipo real detrás). "
            "Si el equipo se detectó sin IP real, gestiónalo por su MAC o asígnale una IP primero."
        )
    return value


class MikrotikDeviceBase(BaseModel):
    name: str
    site: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    host: str
    mac_address: str | None = None
    api_port: int = 8728
    api_use_tls: bool = False
    ssh_port: int = 22
    username: str
    # Agrupación para acceso por rol (ver app/api/deps.py) -- opcional,
    # distinta de `site` (etiqueta de texto libre).
    zone_id: uuid.UUID | None = None


class MikrotikDeviceCreate(MikrotikDeviceBase):
    password: str

    # Solo en los esquemas de entrada: un registro existente con un host ya
    # inválido (ej. guardado antes de esta validación) debe poder seguir
    # leyéndose/mostrándose sin que la lectura misma falle.
    _validate_host = field_validator("host")(_reject_unroutable_host)


class MikrotikDeviceUpdate(BaseModel):
    name: str | None = None
    site: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    host: str | None = None
    mac_address: str | None = None
    api_port: int | None = None
    api_use_tls: bool | None = None
    ssh_port: int | None = None
    username: str | None = None
    password: str | None = None
    zone_id: uuid.UUID | None = None

    _validate_host = field_validator("host")(_reject_unroutable_host)


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
