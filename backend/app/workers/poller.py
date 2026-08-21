"""Tareas en background embebidas en el proceso de uvicorn (sin proceso separado).

- poll_devices_forever: cada DEVICE_POLL_INTERVAL_SECONDS, consulta cada Mikrotik
  activo y guarda un snapshot en device_metrics.
- run_daily_billing_forever: una vez al día, genera facturas del mes, marca
  vencidas y suspende clientes en mora.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.db.session import SessionLocal
from app.models.device_metric import DeviceMetric
from app.models.mikrotik_device import DeviceStatus, MikrotikDevice
from app.services.billing import invoicing
from app.services.mikrotik.device_service import DeviceService

logger = logging.getLogger(__name__)

DAY_SECONDS = 24 * 60 * 60


def _poll_device_once(db: Session, device: MikrotikDevice) -> None:
    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)
    try:
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
