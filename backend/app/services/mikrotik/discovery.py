"""Descubrimiento de equipos Mikrotik en la red local vía MNDP
(Mikrotik Neighbor Discovery Protocol).

Cada Mikrotik anuncia su presencia por broadcast/multicast UDP al puerto 5678
cada ~10s (a menos que esté deshabilitado en /ip neighbor discovery-settings).
Este módulo escucha esos anuncios y mantiene una caché en memoria de
mac -> última IP/identidad vistas, para poder reencontrar un equipo cuando su
IP guardada deja de responder (ver device_service.resolve_current_host).

Nota de diseño: el dato que realmente importa —la IP actual del equipo— es la
dirección de origen del datagrama UDP (socket.recvfrom), no un campo dentro
del payload. Los códigos de tipo de los TLV del payload están documentados de
forma inconsistente entre fuentes; por eso el parser solo confía en el TLV de
MAC (tipo 0x0001) y trata el resto de forma defensiva (nunca revienta el
parseo si un tipo no es el esperado).

Este listener no requiere privilegios especiales (puerto 5678 no es
privilegiado) pero SÍ requiere que el proceso esté en la misma red L2/VLAN
que los Mikrotik para recibir sus broadcasts — no funciona a través de
routers/firewalls que no reenvíen ese tráfico.
"""

from __future__ import annotations

import logging
import socket
import struct
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MNDP_PORT = 5678

# Tipos de TLV MNDP en los que confiamos plenamente (ampliamente documentados
# en implementaciones de referencia de código abierto del protocolo).
_TLV_MAC_ADDRESS = 0x0001
_TLV_IDENTITY = 0x0005
_TLV_VERSION = 0x0007
_TLV_PLATFORM = 0x0008

# Tras cuánto tiempo sin oír un anuncio se considera "no visto recientemente"
# (el intervalo por defecto de anuncio de RouterOS es de 10s).
_STALE_AFTER_SECONDS = 60.0


@dataclass
class DiscoveredDevice:
    mac_address: str
    ip_address: str
    identity: str | None = None
    version: str | None = None
    platform: str | None = None
    seen_at: float = 0.0

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.seen_at) > _STALE_AFTER_SECONDS


def _format_mac(raw: bytes) -> str:
    return ":".join(f"{b:02X}" for b in raw)


def parse_mndp_packet(payload: bytes) -> dict | None:
    """Parsea un paquete MNDP. Devuelve None si no trae al menos una MAC válida.

    Formato: 2 bytes de header (ignorados) + lista de TLV (2 bytes tipo,
    2 bytes longitud, N bytes valor) hasta el final del payload.
    """
    if len(payload) < 4:
        return None

    result: dict = {}
    offset = 2  # los primeros 2 bytes son un header/versión que no usamos

    while offset + 4 <= len(payload):
        tlv_type, tlv_len = struct.unpack_from(">HH", payload, offset)
        offset += 4
        if offset + tlv_len > len(payload):
            break  # TLV truncado/corrupto: dejamos de parsear, no reventamos
        value = payload[offset : offset + tlv_len]
        offset += tlv_len

        try:
            if tlv_type == _TLV_MAC_ADDRESS and tlv_len == 6:
                result["mac_address"] = _format_mac(value)
            elif tlv_type == _TLV_IDENTITY:
                result["identity"] = value.decode("utf-8", errors="replace").strip("\x00")
            elif tlv_type == _TLV_VERSION:
                result["version"] = value.decode("utf-8", errors="replace").strip("\x00")
            elif tlv_type == _TLV_PLATFORM:
                result["platform"] = value.decode("utf-8", errors="replace").strip("\x00")
            # Cualquier otro tipo se ignora deliberadamente: no confiamos en su
            # significado exacto sin poder validarlo contra un router real.
        except (UnicodeDecodeError, struct.error):
            continue

    return result if "mac_address" in result else None


class MndpListener:
    def __init__(self) -> None:
        self._cache: dict[str, DiscoveredDevice] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._socket: socket.socket | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="mndp-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", MNDP_PORT))
            sock.settimeout(1.0)
            self._socket = sock
        except OSError as exc:
            logger.warning(
                "No se pudo abrir el socket MNDP en el puerto %d (%s). "
                "El descubrimiento por MAC quedará deshabilitado.",
                MNDP_PORT,
                exc,
            )
            return

        logger.info("Listener MNDP escuchando en el puerto %d.", MNDP_PORT)
        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break

            parsed = parse_mndp_packet(data)
            if parsed is None:
                continue

            device = DiscoveredDevice(
                mac_address=parsed["mac_address"],
                ip_address=addr[0],
                identity=parsed.get("identity"),
                version=parsed.get("version"),
                platform=parsed.get("platform"),
                seen_at=time.time(),
            )
            with self._lock:
                self._cache[device.mac_address] = device

    def get_by_mac(self, mac_address: str) -> DiscoveredDevice | None:
        with self._lock:
            device = self._cache.get(mac_address.upper())
        return device

    def list_discovered(self) -> list[DiscoveredDevice]:
        with self._lock:
            return list(self._cache.values())


# Instancia única compartida por todo el proceso (ver app.main lifespan).
listener = MndpListener()
