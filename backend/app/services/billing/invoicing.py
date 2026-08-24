"""Generación mensual de facturas, mora, prorrateo, cargo de reconexión y corte por mora."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.billing_settings import BillingSettings, ProrationTarget, ReconnectionFeeMode
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.plan import Plan
from app.services.clients.status import suspend_client_service
from app.services.notifications.service import notify_client


def _month_bounds(reference: date) -> tuple[date, date]:
    start = reference.replace(day=1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day)
    return start, end


def _next_folio(db: Session, settings: BillingSettings) -> str:
    """Folio secuencial global (todavía no existe el concepto de Zona para
    numerar por separado). Único llamador es el job diario -- un solo
    proceso, sin concurrencia real -- así que un incremento simple en la
    misma sesión alcanza, sin necesitar SELECT ... FOR UPDATE."""
    folio = f"{settings.invoice_folio_prefix}{settings.invoice_folio_next_number:06d}"
    settings.invoice_folio_next_number += 1
    return folio


def generate_monthly_invoices(
    db: Session, settings: BillingSettings, reference: date | None = None
) -> list[Invoice]:
    """Crea una factura por cliente activo con plan, si aún no existe una
    para el período y ya se abrió la ventana de generación (ver
    generate_invoice_days_before_due)."""
    reference = reference or date.today()
    period_start, period_end = _month_bounds(reference)
    due_date = period_end

    if (due_date - reference).days > settings.generate_invoice_days_before_due:
        return []

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

        amount = float(plan.price)
        if client.pending_credit:
            amount = max(amount - float(client.pending_credit), 0)
            client.pending_credit = 0
        if client.pending_reconnection_fee:
            amount += float(settings.reconnection_fee_amount)
            client.pending_reconnection_fee = False

        invoice = Invoice(
            client_id=client.id,
            period_start=period_start,
            period_end=period_end,
            due_date=due_date,
            amount=amount,
            status=InvoiceStatus.PENDING,
            folio=_next_folio(db, settings),
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


def apply_late_fees(db: Session, now: datetime, settings: BillingSettings) -> list[Invoice]:
    """Mora automática -- se aplica una sola vez por factura (guardia
    late_fee_applied_at) a partir de la hora configurada. El job diario
    corre en un ciclo fijo de 24h sin cron, así que "la hora configurada"
    se respeta a la próxima corrida que ya pasó esa hora, no de forma
    exacta -- ver nota en el plan de esta fase."""
    if not settings.late_fee_enabled or now.hour < settings.late_fee_apply_hour:
        return []

    overdue = (
        db.query(Invoice)
        .filter(Invoice.status == InvoiceStatus.OVERDUE, Invoice.late_fee_applied_at.is_(None))
        .all()
    )
    for invoice in overdue:
        fee = float(settings.late_fee_amount)
        invoice.late_fee_amount = fee
        invoice.amount = float(invoice.amount) + fee
        invoice.late_fee_applied_at = now
    db.commit()
    return overdue


def send_payment_reminders(db: Session, settings: BillingSettings, today: date) -> list[Invoice]:
    """Recordatorio de pago antes del vencimiento -- se manda una sola vez
    por factura (guardia reminder_sent_at, mismo patrón que
    late_fee_applied_at). Ventana abierta (due_date > today, no solo ==)
    para que un job que se saltó un día igual la agarre en la próxima
    corrida, en vez de perder el aviso para siempre."""
    if not settings.payment_reminder_enabled:
        return []

    cutoff = today + timedelta(days=settings.payment_reminder_days_before_due)
    due_soon = (
        db.query(Invoice)
        .filter(
            Invoice.status == InvoiceStatus.PENDING,
            Invoice.reminder_sent_at.is_(None),
            Invoice.due_date > today,
            Invoice.due_date <= cutoff,
        )
        .all()
    )
    for invoice in due_soon:
        invoice.reminder_sent_at = datetime.now(timezone.utc)
        db.commit()
        notify_client(
            db,
            invoice.client,
            event_type="invoice_due_reminder",
            subject="Tu factura vence pronto",
            body=(
                f"Tu factura de ${invoice.amount} vence el {invoice.due_date}. "
                "Podés reportar tu pago desde el portal."
            ),
        )
    return due_soon


def apply_proration_if_needed(
    db: Session, client: Client, invoice: Invoice, today: date, settings: BillingSettings
) -> None:
    """Prorrateo post-corte: solo se dispara al momento de suspender (no al
    generar la factura), sobre la factura que motiva el corte."""
    if not settings.proration_enabled:
        return

    days_in_period = (invoice.period_end - invoice.period_start).days + 1
    days_unused = max((invoice.period_end - today).days, 0)
    if days_unused < settings.proration_min_days:
        return

    daily_rate = float(invoice.amount) / days_in_period
    credit = round(daily_rate * days_unused, 2)

    if settings.proration_target == ProrationTarget.CURRENT_INVOICE:
        # Solo ajusta el monto -- no la marca pagada ni cambia si se
        # suspende o no. Mezclar "crédito aplicado" con "está pagada"
        # confundiría la reactivación automática (ver pay_invoice).
        invoice.amount = max(float(invoice.amount) - credit, 0)
    else:
        client.pending_credit = float(client.pending_credit) + credit


def apply_reconnection_fee(db: Session, client: Client, settings: BillingSettings) -> Invoice | None:
    if settings.reconnection_fee_mode == ReconnectionFeeMode.OFF:
        return None

    if settings.reconnection_fee_mode == ReconnectionFeeMode.ON_SUSPEND:
        today = date.today()
        invoice = Invoice(
            client_id=client.id,
            period_start=today,
            period_end=today,
            due_date=today,
            amount=float(settings.reconnection_fee_amount),
            status=InvoiceStatus.PENDING,
            folio=_next_folio(db, settings),
        )
        db.add(invoice)
        return invoice

    # ON_NEXT_INVOICE
    client.pending_reconnection_fee = True
    return None


def suspend_clients_with_overdue_invoices(
    db: Session, settings: BillingSettings, today: date | None = None
) -> list[Client]:
    """Suspende (en BD y en el Mikrotik) a clientes con facturas vencidas
    más allá del período de gracia configurado."""
    today = today or date.today()
    cutoff = today - timedelta(days=settings.suspend_days_after_due)

    overdue_invoices_by_client: dict = {}
    for row in (
        db.query(Invoice)
        .filter(Invoice.status == InvoiceStatus.OVERDUE, Invoice.due_date < cutoff)
        # Excluye facturas con una promesa de pago vigente (ver
        # POST /invoices/{id}/promise-to-pay) -- si la fecha prometida ya
        # pasó, deja de excluirse sola, sin código extra acá.
        .filter((Invoice.promise_to_pay_until.is_(None)) | (Invoice.promise_to_pay_until < today))
        .all()
    ):
        current = overdue_invoices_by_client.get(row.client_id)
        if current is None or row.period_end > current.period_end:
            overdue_invoices_by_client[row.client_id] = row

    if not overdue_invoices_by_client:
        return []

    suspended: list[Client] = []
    clients = (
        db.query(Client)
        .filter(Client.id.in_(overdue_invoices_by_client.keys()), Client.status == ClientStatus.ACTIVE)
        .all()
    )
    for client in clients:
        driving_invoice = overdue_invoices_by_client[client.id]
        apply_proration_if_needed(db, client, driving_invoice, today, settings)
        apply_reconnection_fee(db, client, settings)
        suspend_client_service(db, client)
        suspended.append(client)

    return suspended
