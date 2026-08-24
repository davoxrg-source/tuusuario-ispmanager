"""Tareas en background embebidas en el proceso de uvicorn (sin proceso separado).

- poll_devices_forever: cada DEVICE_POLL_INTERVAL_SECONDS, consulta cada Mikrotik
  activo, guarda un snapshot en device_metrics, y chequea colas QoS
  trabadas (ver services/mikrotik/qos_health.py) -- avisa por log si la
  misma cola sigue trabada 2 ciclos seguidos.
- poll_client_online_status_forever: cada CLIENT_ARP_POLL_INTERVAL_SECONDS
  (por defecto 60s, mucho más seguido que el polling general de arriba),
  lee solo la tabla ARP de cada equipo y actualiza Client.is_online de sus
  clientes (conectividad real, no facturación) -- loop aparte porque este
  dato se quiere ver al día mucho más rápido que las métricas/QoS.
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
from app.models.poll_attempt import PollAttempt, PollAttemptStatus, PollJobType
from app.services.billing import invoicing
from app.services.billing.settings import get_billing_settings
from app.services.mikrotik.device_service import DeviceService
from app.services.netflow.collector import purge_old_buckets
from app.workers.retry import AttemptOutcome, run_with_retries

logger = logging.getLogger(__name__)

DAY_SECONDS = 24 * 60 * 60

# Colas vistas trabadas en el ciclo ANTERIOR, por equipo -- para no avisar
# por una lectura sola (podría ser una casualidad de timing). Vive en
# memoria del proceso a propósito: si el backend se reinicia, empieza de
# cero, que es aceptable para una alerta operativa (no es auditoría).
_previously_stuck: dict[str, set[str]] = {}


def _record_attempt(
    db: Session, *, job_type: PollJobType, device_id, outcome: AttemptOutcome
) -> None:
    """Persiste un intento (éxito o fallo) de un job de background -- ver
    app/models/poll_attempt.py. Se llama después de CADA intento, no solo
    del resultado final, así queda visible el reintento en curso aunque el
    proceso muera a mitad de camino."""
    db.rollback()  # defensivo: si fn() dejó la sesión en tx abortada
    db.add(
        PollAttempt(
            device_id=device_id,
            job_type=job_type,
            attempt_number=outcome.attempt_number,
            max_attempts=outcome.max_attempts,
            status=PollAttemptStatus.SUCCESS if outcome.succeeded else PollAttemptStatus.FAILURE,
            error_message=str(outcome.error)[:2000] if outcome.error else None,
            duration_ms=outcome.duration_ms,
        )
    )
    db.commit()


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


def _update_client_online_status(
    db: Session,
    device: MikrotikDevice,
    service: DeviceService,
    *,
    max_attempts: int,
    backoff_base_seconds: float,
    backoff_max_seconds: float,
) -> None:
    """Marca online/offline a cada cliente de este equipo según si su IP
    responde ARP ahora mismo (pinga cada una para forzar una lectura
    fresca, no una entrada 'stale' en caché -- ver
    DeviceService.get_online_ip_set) -- es conectividad real, distinta del
    `status` administrativo/de facturación del cliente."""
    clients = db.query(Client).filter(Client.mikrotik_device_id == device.id).all()
    candidate_ips = [c.ip_address for c in clients if c.ip_address]

    try:
        online_ips = run_with_retries(
            lambda: service.get_online_ip_set(candidate_ips),
            max_attempts=max_attempts,
            backoff_base_seconds=backoff_base_seconds,
            backoff_max_seconds=backoff_max_seconds,
            on_attempt=lambda outcome: _record_attempt(
                db, job_type=PollJobType.CLIENT_ONLINE_STATUS, device_id=device.id, outcome=outcome
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo leer la tabla ARP de %s: %s", device.name, exc)
        return

    now = datetime.now(timezone.utc)
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
    settings = get_settings()

    def _fetch():
        try:
            return service.get_status(), service.get_interfaces_snapshot()
        except Exception:
            # La IP guardada no respondió: si hay MAC registrada, intentamos
            # redescubrir la IP actual por MNDP antes de marcar el equipo offline.
            new_host = service.resolve_host_via_mac(db)
            if not new_host:
                raise
            return service.get_status(), service.get_interfaces_snapshot()

    try:
        status, interfaces = run_with_retries(
            _fetch,
            max_attempts=settings.poller_retry_max_attempts,
            backoff_base_seconds=settings.poller_retry_backoff_base_seconds,
            backoff_max_seconds=settings.poller_retry_backoff_max_seconds,
            on_attempt=lambda outcome: _record_attempt(
                db, job_type=PollJobType.DEVICE_POLL, device_id=device.id, outcome=outcome
            ),
        )

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
    settings = get_settings()

    def _job():
        today = date.today()
        billing_settings = get_billing_settings(db)
        created = invoicing.generate_monthly_invoices(db, billing_settings, today)
        overdue = invoicing.mark_overdue_invoices(db, today)
        suspended = invoicing.suspend_clients_with_overdue_invoices(db, billing_settings, today)
        late_fee_applied = invoicing.apply_late_fees(db, datetime.now(timezone.utc), billing_settings)
        logger.info(
            "Job de facturación: %d facturas creadas, %d marcadas vencidas, %d clientes suspendidos, "
            "%d moras aplicadas.",
            len(created),
            len(overdue),
            len(suspended),
            len(late_fee_applied),
        )

    try:
        run_with_retries(
            _job,
            max_attempts=settings.daily_billing_max_attempts,
            backoff_base_seconds=0,
            backoff_max_seconds=0,
            on_attempt=lambda outcome: _record_attempt(
                db, job_type=PollJobType.DAILY_BILLING, device_id=None, outcome=outcome
            ),
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


def _poll_client_online_status_once(db: Session, device: MikrotikDevice) -> None:
    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)
    settings = get_settings()
    _update_client_online_status(
        db,
        device,
        service,
        max_attempts=settings.poller_retry_max_attempts,
        backoff_base_seconds=settings.poller_retry_backoff_base_seconds,
        backoff_max_seconds=settings.poller_retry_backoff_max_seconds,
    )
    db.commit()


def _poll_all_clients_online_status() -> None:
    db = SessionLocal()
    try:
        devices = db.query(MikrotikDevice).all()
        for device in devices:
            _poll_client_online_status_once(db, device)
    finally:
        db.close()


async def poll_client_online_status_forever() -> None:
    settings = get_settings()
    while True:
        try:
            await asyncio.to_thread(_poll_all_clients_online_status)
        except Exception:  # noqa: BLE001
            logger.exception("Ciclo de estado de conexión de clientes falló.")
        await asyncio.sleep(settings.client_arp_poll_interval_seconds)


async def run_daily_billing_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(_run_daily_billing)
        except Exception:  # noqa: BLE001
            logger.exception("Job diario de facturación falló.")
        await asyncio.sleep(DAY_SECONDS)


def _run_traffic_maintenance() -> None:
    db = SessionLocal()
    settings = get_settings()

    def _job():
        deleted = purge_old_buckets(db, older_than_days=settings.netflow_retention_days)
        if deleted:
            logger.info("Purga de uso de tráfico: %d buckets viejos eliminados.", deleted)

    try:
        run_with_retries(
            _job,
            max_attempts=settings.traffic_maintenance_max_attempts,
            backoff_base_seconds=0,
            backoff_max_seconds=0,
            on_attempt=lambda outcome: _record_attempt(
                db, job_type=PollJobType.TRAFFIC_MAINTENANCE, device_id=None, outcome=outcome
            ),
        )
    finally:
        db.close()


async def run_traffic_maintenance_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(_run_traffic_maintenance)
        except Exception:  # noqa: BLE001
            logger.exception("Purga de uso de tráfico falló.")
        await asyncio.sleep(DAY_SECONDS)


def _run_payment_reminders() -> None:
    db = SessionLocal()
    settings = get_settings()

    def _job():
        billing_settings = get_billing_settings(db)
        sent = invoicing.send_payment_reminders(db, billing_settings, date.today())
        if sent:
            logger.info("Recordatorios de pago: %d factura(s) avisadas.", len(sent))

    try:
        run_with_retries(
            _job,
            max_attempts=1,
            backoff_base_seconds=0,
            backoff_max_seconds=0,
            on_attempt=lambda outcome: _record_attempt(
                db, job_type=PollJobType.PAYMENT_REMINDERS, device_id=None, outcome=outcome
            ),
        )
    finally:
        db.close()


async def run_payment_reminders_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(_run_payment_reminders)
        except Exception:  # noqa: BLE001
            logger.exception("Job de recordatorios de pago falló.")
        await asyncio.sleep(DAY_SECONDS)
