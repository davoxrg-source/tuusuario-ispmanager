"""Generación mensual de facturas y corte por mora."""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.security import decrypt_secret
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.mikrotik_device import MikrotikDevice
from app.models.plan import Plan
from app.services.mikrotik.device_service import DeviceService

logger = logging.getLogger(__name__)

# Días de gracia tras el due_date antes de suspender por mora.
OVERDUE_GRACE_DAYS = 5


def _month_bounds(reference: date) -> tuple[date, date]:
    start = reference.replace(day=1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day)
    return start, end


def generate_monthly_invoices(db: Session, reference: date | None = None) -> list[Invoice]:
    """Crea una factura por cliente activo con plan, si aún no existe una para el período."""
    reference = reference or date.today()
    period_start, period_end = _month_bounds(reference)
    due_date = period_end

    created: list[Invoice] = []
    clients = (
        db.query(Client)
        .filter(Client.status == ClientStatus.ACTIVE, Client.plan_id.isnot(None))
        .all()
    )
    for client in clients:
        already_exists = (
            db.query(Invoice)
            .filter(Invoice.client_id == client.id, Invoice.period_start == period_start)
            .first()
        )
        if already_exists:
            continue

        plan = db.get(Plan, client.plan_id)
        if plan is None:
            continue

        invoice = Invoice(
            client_id=client.id,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            amount=plan.price,
            status=InvoiceStatus.PENDING,
        )
        db.add(invoice)
        created.append(invoice)

    db.commit()
    return created


def mark_overdue_invoices(db: Session, today: date | None = None) -> list[Invoice]:
    today = today or date.today()
    pending = (
        db.query(Invoice)
        .filter(Invoice.status == InvoiceStatus.PENDING, Invoice.due_date < today)
        .all()
    )
    for invoice in pending:
        invoice.status = InvoiceStatus.OVERDUE
    db.commit()
    return pending


def suspend_clients_with_overdue_invoices(db: Session, today: date | None = None) -> list[Client]:
    """Suspende (en BD y en el Mikrotik) a clientes con facturas vencidas más allá del período de gracia."""
    today = today or date.today()
    cutoff = today - timedelta(days=OVERDUE_GRACE_DAYS)

    overdue_client_ids = {
        row.client_id
        for row in (
            db.query(Invoice)
            .filter(Invoice.status == InvoiceStatus.OVERDUE, Invoice.due_date < cutoff)
            .all()
        )
    }
    if not overdue_client_ids:
        return []

    suspended: list[Client] = []
    clients = (
        db.query(Client)
        .filter(Client.id.in_(overdue_client_ids), Client.status == ClientStatus.ACTIVE)
        .all()
    )
    for client in clients:
        client.status = ClientStatus.SUSPENDED
        suspended.append(client)

        if client.ip_address and client.mikrotik_device_id:
            device = db.get(MikrotikDevice, client.mikrotik_device_id)
            if device:
                try:
                    service = DeviceService(device, decrypt_secret(device.encrypted_password))
                    service.suspend_client_ip(client.ip_address)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("No se pudo suspender en Mikrotik al cliente %s: %s", client.id, exc)

    db.commit()
    return suspended
