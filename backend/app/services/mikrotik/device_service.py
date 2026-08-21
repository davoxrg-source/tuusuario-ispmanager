"""Capa única de acceso a un Mikrotik: intenta API RouterOS y cae a SSH cuando aplica.

El resto del backend solo conoce esta interfaz, nunca los detalles de transporte.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.mikrotik_device import MikrotikDevice
from app.schemas.mikrotik_device import (
    ActivePppSession,
    ConnectionTestResult,
    DeviceResourceStatus,
)
from app.services.mikrotik import api_client, discovery, mactelnet_client, ssh_client

logger = logging.getLogger(__name__)


class DeviceService:
    def __init__(self, device: MikrotikDevice, password: str) -> None:
        self.device = device
        self.password = password

    def _api(self):
        return api_client.api_connection(
            host=self.device.host,
            username=self.device.username,
            password=self.password,
            port=self.device.api_port,
            use_tls=self.device.api_use_tls,
        )

    def _ssh(self):
        return ssh_client.ssh_connection(
            host=self.device.host,
            username=self.device.username,
            password=self.password,
            port=self.device.ssh_port,
        )

    def _test_connection_at_current_host(self) -> ConnectionTestResult:
        try:
            with self._api() as api:
                identity = api_client.get_identity(api)
                resource = api_client.get_system_resource(api)
                return ConnectionTestResult(
                    success=True,
                    method="api",
                    message="Conexión exitosa vía API RouterOS.",
                    identity=identity,
                    routeros_version=resource.get("version"),
                    uptime_seconds=_parse_routeros_uptime(resource.get("uptime")),
                )
        except api_client.RouterOsApiError as api_error:
            logger.warning("API RouterOS falló para %s, probando SSH: %s", self.device.host, api_error)
            try:
                with self._ssh() as client:
                    identity = ssh_client.get_identity(client)
                    return ConnectionTestResult(
                        success=True,
                        method="ssh",
                        message="La API falló, pero la conexión SSH fue exitosa.",
                        identity=identity,
                    )
            except ssh_client.RouterOsSshError as ssh_error:
                return ConnectionTestResult(
                    success=False,
                    method="none",
                    message=f"API falló ({api_error}); SSH también falló ({ssh_error}).",
                )

    def resolve_host_via_mac(self, db: Session) -> str | None:
        """Si el equipo tiene MAC registrada y MNDP la vio con otra IP, actualiza
        device.host en la base de datos. Devuelve la IP nueva si hubo cambio."""
        if not self.device.mac_address:
            return None
        seen = discovery.listener.get_by_mac(self.device.mac_address)
        if seen is None or seen.is_stale or seen.ip_address == self.device.host:
            return None

        logger.info(
            "Equipo %s: IP cambió de %s a %s (detectado por MAC %s).",
            self.device.name,
            self.device.host,
            seen.ip_address,
            self.device.mac_address,
        )
        self.device.host = seen.ip_address
        db.commit()
        return seen.ip_address

    def test_connection(self, db: Session | None = None) -> ConnectionTestResult:
        result = self._test_connection_at_current_host()
        if result.success or db is None or not self.device.mac_address:
            return result

        # La IP guardada falló por completo: intentamos redescubrir por MAC
        # antes de rendirnos (ver discovery.py).
        new_host = self.resolve_host_via_mac(db)
        if new_host:
            retry = self._test_connection_at_current_host()
            if retry.success:
                retry.resolved_via_mac = True
                retry.updated_host = new_host
                return retry
            result = retry

        # Último recurso: MAC-Telnet, solo funciona en la misma red L2 y con
        # el binario externo instalado (ver mactelnet_client.py).
        try:
            identity = mactelnet_client.get_identity(
                self.device.mac_address, self.device.username, self.password
            )
            return ConnectionTestResult(
                success=True,
                method="mactelnet",
                message="API y SSH fallaron; se alcanzó el equipo por MAC-Telnet (último recurso).",
                identity=identity,
                resolved_via_mac=True,
            )
        except mactelnet_client.MacTelnetError as mactelnet_error:
            return ConnectionTestResult(
                success=False,
                method="none",
                message=f"{result.message} MAC-Telnet también falló ({mactelnet_error}).",
            )

    def get_status(self) -> DeviceResourceStatus:
        with self._api() as api:
            resource = api_client.get_system_resource(api)
            sessions = api_client.get_active_ppp_sessions(api)
            return DeviceResourceStatus(
                cpu_load_percent=_safe_int(resource.get("cpu-load")),
                memory_used_bytes=_safe_int(resource.get("total-memory"), sub=_safe_int(resource.get("free-memory"))),
                memory_total_bytes=_safe_int(resource.get("total-memory")),
                uptime_seconds=_parse_routeros_uptime(resource.get("uptime")),
                active_ppp_sessions=len(sessions),
            )

    def get_interfaces_snapshot(self) -> list[dict]:
        with self._api() as api:
            interfaces = api_client.get_interfaces(api)
        return [
            {
                "name": iface.get("name"),
                "rx_bytes": _safe_int(iface.get("rx-byte")),
                "tx_bytes": _safe_int(iface.get("tx-byte")),
                "running": iface.get("running") == "true",
            }
            for iface in interfaces
        ]

    def get_active_sessions(self) -> list[ActivePppSession]:
        with self._api() as api:
            sessions = api_client.get_active_ppp_sessions(api)
        return [
            ActivePppSession(
                name=row.get("name", ""),
                address=row.get("address"),
                uptime=row.get("uptime"),
                caller_id=row.get("caller-id"),
            )
            for row in sessions
        ]

    def create_pppoe_secret(self, username: str, password: str, profile: str | None = None) -> None:
        with self._api() as api:
            api_client.create_ppp_secret(api, name=username, password=password, profile=profile)

    def set_client_enabled(self, pppoe_username: str, enabled: bool) -> bool:
        with self._api() as api:
            return api_client.set_ppp_secret_enabled(api, pppoe_username, enabled)

    def remove_pppoe_secret(self, pppoe_username: str) -> bool:
        with self._api() as api:
            return api_client.remove_ppp_secret(api, pppoe_username)

    def reboot(self) -> None:
        try:
            with self._api() as api:
                api_client.reboot(api)
                return
        except api_client.RouterOsApiError:
            logger.warning("Reboot vía API falló para %s, probando SSH.", self.device.host)
        with self._ssh() as client:
            ssh_client.reboot(client)

    def reset_to_factory_defaults(self, no_defaults: bool = True) -> None:
        """ACCIÓN DESTRUCTIVA: borra toda la configuración del equipo y lo
        reinicia. Con no_defaults=True el equipo queda sin ninguna IP asignada
        (solo alcanzable por MAC vía MNDP/MAC-Telnet) hasta configurarlo desde cero."""
        logger.warning(
            "Ejecutando reset de configuración de fábrica en %s (%s) — no_defaults=%s",
            self.device.name,
            self.device.host,
            no_defaults,
        )
        try:
            with self._api() as api:
                api_client.reset_configuration(api, no_defaults=no_defaults)
                return
        except api_client.RouterOsApiError:
            logger.warning("Reset vía API falló para %s, probando SSH.", self.device.host)
        with self._ssh() as client:
            ssh_client.reset_configuration(client, no_defaults=no_defaults)


def _safe_int(value, sub: int | None = None) -> int | None:
    if value is None:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    if sub is not None:
        result = result - sub
    return result


def _parse_routeros_uptime(uptime: str | None) -> int | None:
    """Convierte '1w2d3h4m5s' (formato RouterOS) a segundos."""
    if not uptime:
        return None
    units = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
    total = 0
    number = ""
    for char in uptime:
        if char.isdigit():
            number += char
        elif char in units and number:
            total += int(number) * units[char]
            number = ""
    return total or None
