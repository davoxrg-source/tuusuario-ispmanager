"""Colector NetFlow v5: recibe exports UDP de cada Mikrotik (/ip/traffic-flow,
ver services/mikrotik/api_client.enable_traffic_flow) y acumula bytes/paquetes
por cliente en buckets de una hora (ver ClientTrafficUsage).

Riesgo conocido, no resuelto: si el tráfico de un cliente sale NATeado hacia
otra IP antes de llegar al equipo que exporta NetFlow, el matching por
Client.ip_address se rompe -- es el mismo gotcha que documenta MikroSystem
para su propio "Traffic Flow". No aplica al diseño actual de ispmanager
(Client.ip_address es la IP real asignada por DHCP/binding, sin PPPoE ni
CGNAT intermedio -- ver [[project-wisp-competitor-research]]), pero queda
anotado por si el enrutamiento cambia.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import struct
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.client_traffic_usage import ClientTrafficUsage
from app.models.mikrotik_device import MikrotikDevice

logger = logging.getLogger(__name__)

_HEADER_FMT = "!HHIIIIBBH"
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)
_RECORD_FMT = "!IIIHHIIIIHHBBBBHHBBH"
_RECORD_SIZE = struct.calcsize(_RECORD_FMT)

FLUSH_INTERVAL_SECONDS = 60


class _Counters:
    __slots__ = ("bytes_in", "bytes_out", "packets_in", "packets_out")

    def __init__(self) -> None:
        self.bytes_in = 0
        self.bytes_out = 0
        self.packets_in = 0
        self.packets_out = 0


def parse_v5(data: bytes) -> list[dict]:
    """Decodifica un datagrama NetFlow v5 en una lista de flow records
    (24 bytes de header + N registros de 48 bytes, formato fijo)."""
    if len(data) < _HEADER_SIZE:
        return []
    version, count = struct.unpack_from("!HH", data, 0)
    if version != 5:
        return []

    records: list[dict] = []
    offset = _HEADER_SIZE
    for _ in range(count):
        if offset + _RECORD_SIZE > len(data):
            break
        fields = struct.unpack_from(_RECORD_FMT, data, offset)
        offset += _RECORD_SIZE
        src_addr, dst_addr, _nexthop, _in_if, _out_if, packets, octets = fields[0:7]
        records.append(
            {
                "src_addr": str(ipaddress.IPv4Address(src_addr)),
                "dst_addr": str(ipaddress.IPv4Address(dst_addr)),
                "packets": packets,
                "bytes": octets,
            }
        )
    return records


def _bucket_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(minute=0, second=0, microsecond=0)


class NetflowProtocol(asyncio.DatagramProtocol):
    """Un buffer en memoria por proceso -- igual que _previously_stuck en
    workers/poller.py: si el backend reinicia se pierde como mucho
    FLUSH_INTERVAL_SECONDS de datos, aceptable para accounting operativo,
    no para auditoría legal."""

    def __init__(self) -> None:
        self._buffer: dict[tuple[uuid.UUID, uuid.UUID, datetime], _Counters] = defaultdict(_Counters)
        self._device_by_host: dict[str, uuid.UUID] = {}
        self._clients_by_device: dict[uuid.UUID, dict[str, uuid.UUID]] = {}
        self.maintenance_task: asyncio.Task | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport
        self.maintenance_task = asyncio.get_event_loop().create_task(self._maintenance_forever())

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        # Solo lookups en memoria y parseo -- nada de I/O acá, para no
        # bloquear el event loop en el callback (el refresco de caché de
        # dispositivos/clientes corre aparte, ver _maintenance_forever).
        exporter_ip = addr[0]
        device_id = self._device_by_host.get(exporter_ip)
        if device_id is None:
            return
        clients_by_ip = self._clients_by_device.get(device_id)
        if not clients_by_ip:
            return

        try:
            records = parse_v5(data)
        except struct.error:
            logger.warning("Paquete NetFlow malformado desde %s", exporter_ip)
            return

        bucket = _bucket_start()
        for record in records:
            src_client = clients_by_ip.get(record["src_addr"])
            dst_client = clients_by_ip.get(record["dst_addr"])
            if src_client:
                counters = self._buffer[(src_client, device_id, bucket)]
                counters.bytes_out += record["bytes"]
                counters.packets_out += record["packets"]
            if dst_client:
                counters = self._buffer[(dst_client, device_id, bucket)]
                counters.bytes_in += record["bytes"]
                counters.packets_in += record["packets"]

    async def _maintenance_forever(self) -> None:
        # Un error en un ciclo (ej. de DB momentáneo) no debe matar la tarea
        # para siempre -- sin este try/except, una excepción acá deja de
        # refrescar la caché y de flushear el buffer en memoria sin ningún
        # aviso visible (pasó de verdad: un bug de tipos en _flush mataba
        # esta tarea en el primer ciclo con datos reales, en silencio).
        while True:
            try:
                await asyncio.to_thread(self._refresh_client_cache)
                await asyncio.sleep(FLUSH_INTERVAL_SECONDS)
                await asyncio.to_thread(self._flush)
            except Exception:  # noqa: BLE001
                logger.exception("Ciclo de mantenimiento del colector NetFlow falló.")
                await asyncio.sleep(FLUSH_INTERVAL_SECONDS)

    def _refresh_client_cache(self) -> None:
        db = SessionLocal()
        try:
            self._device_by_host = {d.host: d.id for d in db.query(MikrotikDevice).all()}
            clients_by_device: dict[uuid.UUID, dict[str, uuid.UUID]] = defaultdict(dict)
            for client in db.query(Client).filter(
                Client.ip_address.isnot(None), Client.mikrotik_device_id.isnot(None)
            ):
                clients_by_device[client.mikrotik_device_id][client.ip_address] = client.id
            self._clients_by_device = dict(clients_by_device)
        finally:
            db.close()

    def _flush(self) -> None:
        if not self._buffer:
            return
        pending, self._buffer = self._buffer, defaultdict(_Counters)
        db = SessionLocal()
        try:
            for (client_id, device_id, bucket_start), counters in pending.items():
                row = (
                    db.query(ClientTrafficUsage)
                    .filter(
                        ClientTrafficUsage.client_id == client_id,
                        ClientTrafficUsage.bucket_start == bucket_start,
                    )
                    .first()
                )
                if row is None:
                    row = ClientTrafficUsage(
                        client_id=client_id, device_id=device_id, bucket_start=bucket_start
                    )
                    db.add(row)
                # (row.x or 0): una fila recién construida en Python todavía
                # no tiene el default=0 del modelo aplicado -- eso solo pasa
                # al hacer INSERT -- así que sigue en None hasta el commit.
                row.bytes_in = (row.bytes_in or 0) + counters.bytes_in
                row.bytes_out = (row.bytes_out or 0) + counters.bytes_out
                row.packets_in = (row.packets_in or 0) + counters.packets_in
                row.packets_out = (row.packets_out or 0) + counters.packets_out
            db.commit()
        finally:
            db.close()


async def start_collector(port: int) -> tuple[asyncio.DatagramTransport, NetflowProtocol]:
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        NetflowProtocol, local_addr=("0.0.0.0", port)
    )
    logger.info("Colector NetFlow escuchando en UDP %d", port)
    return transport, protocol


def purge_old_buckets(db: Session, older_than_days: int = 90) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    deleted = (
        db.query(ClientTrafficUsage)
        .filter(ClientTrafficUsage.bucket_start < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
