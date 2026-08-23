"""Tareas en background embebidas en el proceso de uvicorn (sin proceso separado).

- poll_devices_forever: cada DEVICE_POLL_INTERVAL_SECONDS, consulta cada Mikrotik
  activo, guarda un snapshot en device_metrics, chequea colas QoS
  trabadas (ver services/mikrotik/qos_health.py) -- avisa por log si la
  misma cola sigue trabada 2 ciclos seguidos -- y actualiza Client.is_online
  de cada cliente del equipo según su tabla ARP (conectividad real, no
  facturación).
- run_daily_billing_forever: una vez al día, genera facturas del mes, marca
  vencidas y suspende clientes en mora.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.device_metric import DeviceMetric
from app.models.mikrotik_device import DeviceStatus, MikrotikDevice
from app.services.billing import invoicing
from app.services.mikrotik.device_service import DeviceService
from app.services.netflow.collector import purge_old_buckets

logger = logging.getLogger(__name__)

DAY_SECONDS = 24 * 60 * 60

# Colas vistas trabadas en el ciclo ANTERIOR, por equipo -- para no avisar
# por una lectura sola (podría ser una casualidad de timing). Vive en
# memoria del proceso a propósito: si el backend se reinicia, empieza de
# cero, que es aceptable para una alerta operativa (no es auditoría).
_previously_stuck: dict[str, set[str]] = {}


def _check_qos_health(device: MikrotikDevice, service: DeviceService) -> None:
    device_key = str(device.id)
    try:
        stuck_now = set(service.find_stuck_qos_queues())
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo chequear salud de QoS en %s: %s", device.name, exc)
        return

    confirmed = stuck_now & _previously_stuck.get(device_key, set())
    if confirmed:
        logger.warning(
            "QoS: %d cola(s) trabada(s) en %s hace 2+ ciclos seguidos (rate=0 con "
            "backlog sin drenar) -- ver services/mikrotik/qos_health.py, probablemente "
            "necesite reiniciar el equipo: %s",
            len(confirmed), device.name, ", ".join(sorted(confirmed)),
        )
    _previously_stuck[device_key] = stuck_now


def _update_client_online_status(db: Session, device: MikrotikDevice, service: DeviceService) -> None:
    """Marca online/offline a cada cliente de este equipo según si su IP
    tiene una entrada ARP 'complete' ahora mismo (ver
    DeviceService.get_online_ip_set) -- es conectividad real, distinta del
    `status` administrativo/de facturación del cliente."""
    try:
        online_ips = service.get_online_ip_set()
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo leer la tabla ARP de %s: %s", device.name, exc)
        return

    now = datetime.now(timezone.utc)
    clients = db.query(Client).filter(Client.mikrotik_device_id == device.id).all()
    for client in clients:
        client.is_online = bool(client.ip_address and client.ip_address in online_ips)
        if client.is_online:
            client.last_seen_at = now


def _ensure_traffic_flow(device: MikrotikDevice, service: DeviceService) -> None:
    """Auto-configura el export NetFlow del equipo hacia este backend, una
    sola vez por equipo (ver MikrotikDevice.traffic_flow_configured) -- el
    operador no tiene que entrar manualmente a Winbox a habilitarlo."""
    settings = get_settings()
    if not settings.netflow_public_host or device.traffic_flow_configured:
        return
    try:
        service.enable_traffic_flow(settings.netflow_public_host, settings.netflow_collector_port)
        device.traffic_flow_configured = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo habilitar traffic-flow en %s: %s", device.name, exc)


def _poll_device_once(db: Session, device: MikrotikDevice) -> None:
    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)
    try:
        try:
            status = service.get_status()
            interfaces = service.get_interfaces_snapshot()
        except Exception:
            # La IP guardada no respondió: si hay MAC registrada, intentamos
            # redescubrir la IP actual por MNDP antes de marcar el equipo offline.
            new_host = service.resolve_host_via_mac(db)
            if not new_host:
                raise
            status = service.get_status()
            interfaces = service.get_interfaces_snapshot()

        device.status = DeviceStatus.ONLINE
        db.add(
            DeviceMetric(
                device_id=device.id,
                cpu_load_percent=status.cpu_load_percent,
                memory_used_bytes=status.memory_used_bytes,
                memory_total_bytes=status.memory_total_bytes,
                uptime_seconds=status.uptime_seconds,
                active_ppp_sessions=status.active_ppp_sessions,
                interfaces={"list": interfaces},
            )
        )
        _check_qos_health(device, service)
        _ensure_traffic_flow(device, service)
        _update_client_online_status(db, device, service)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Polling falló para dispositivo %s (%s): %s", device.name, device.host, exc)
        device.status = DeviceStatus.OFFLINE
    db.commit()


def _poll_all_devices() -> None:
    db = SessionLocal()
    try:
        devices = db.query(MikrotikDevice).all()
        for device in devices:
            _poll_device_once(db, device)
    finally:
        db.close()


def _run_daily_billing() -> None:
    db = SessionLocal()
    try:
        today = date.today()
        created = invoicing.generate_monthly_invoices(db, today)
        overdue = invoicing.mark_overdue_invoices(db, today)
        suspended = invoicing.suspend_clients_with_overdue_invoices(db, today)
        logger.info(
            "Job de facturación: %d facturas creadas, %d marcadas vencidas, %d clientes suspendidos.",
            len(created),
            len(overdue),
            len(suspended),
        )
    finally:
        db.close()


async def poll_devices_forever() -> None:
    settings = get_settings()
    while True:
        try:
            await asyncio.to_thread(_poll_all_devices)
        except Exception:  # noqa: BLE001
            logger.exception("Ciclo de polling de dispositivos falló.")
        await asyncio.sleep(settings.device_poll_interval_seconds)


async def run_daily_billing_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(_run_daily_billing)
        except Exception:  # noqa: BLE001
            logger.exception("Job diario de facturación falló.")
        await asyncio.sleep(DAY_SECONDS)


def _run_traffic_maintenance() -> None:
    db = SessionLocal()
    try:
        settings = get_settings()
        deleted = purge_old_buckets(db, older_than_days=settings.netflow_retention_days)
        if deleted:
            logger.info("Purga de uso de tráfico: %d buckets viejos eliminados.", deleted)
    finally:
        db.close()


async def run_traffic_maintenance_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(_run_traffic_maintenance)
        except Exception:  # noqa: BLE001
            logger.exception("Purga de uso de tráfico falló.")
        await asyncio.sleep(DAY_SECONDS)
