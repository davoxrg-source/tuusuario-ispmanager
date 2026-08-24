import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import ensure_zone_access, get_current_user, require_admin
from app.db.session import get_db
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.payment_account import PaymentAccount
from app.models.payment_report import PaymentReport, PaymentReportStatus
from app.models.user import User
from app.schemas.billing import (
    AccountBalanceRead,
    BulkInvoiceCharge,
    InvoiceCreate,
    InvoiceRead,
    PaymentAccountCreate,
    PaymentAccountRead,
    PaymentCreate,
    PaymentRead,
    PromiseToPayCreate,
)
from app.schemas.common import BulkActionResult, BulkActionResultItem
from app.schemas.portal import PaymentReportRead
from app.services.clients.status import reactivate_client_service

# Tope razonable a la prórroga que se puede otorgar de una vez -- evita que
# una promesa de pago deje una factura vencida sin cortar indefinidamente.
MAX_PROMISE_TO_PAY_DAYS = 30

router = APIRouter(tags=["billing"], dependencies=[Depends(get_current_user)])


@router.get("/invoices", response_model=list[InvoiceRead])
def list_invoices(db: Session = Depends(get_db)) -> list[Invoice]:
    return db.query(Invoice).order_by(Invoice.due_date.desc()).all()


@router.post("/invoices", response_model=InvoiceRead, status_code=201)
def create_invoice(payload: InvoiceCreate, db: Session = Depends(get_db)) -> Invoice:
    invoice = Invoice(**payload.model_dump())
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


# Registrada antes de "/invoices/{invoice_id}/..." a propósito -- mismo
# motivo que las rutas /clients/bulk/*: si fuera después, FastAPI intentaría
# parsear "bulk" como un invoice_id (UUID) y devolvería 422.
@router.post("/invoices/bulk/charge", response_model=BulkActionResult, dependencies=[Depends(require_admin)])
def bulk_charge_invoices(payload: BulkInvoiceCharge, db: Session = Depends(get_db)) -> BulkActionResult:
    results: list[BulkActionResultItem] = []
    for invoice_id in payload.invoice_ids:
        try:
            invoice = db.get(Invoice, invoice_id)
            if invoice is None:
                raise HTTPException(status_code=404, detail="Factura no encontrada.")
            if invoice.status == InvoiceStatus.PAID:
                raise HTTPException(status_code=400, detail="La factura ya está pagada.")
            invoice.amount = float(invoice.amount) + payload.amount
            db.commit()
            results.append(BulkActionResultItem(id=invoice_id, ok=True))
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            results.append(BulkActionResultItem(id=invoice_id, ok=False, detail=detail))
    return BulkActionResult(results=results)


@router.get("/clients/{client_id}/invoices", response_model=list[InvoiceRead])
def list_client_invoices(
    client_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[Invoice]:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    ensure_zone_access(current_user, client.zone_id, "Cliente no encontrado.")
    return (
        db.query(Invoice)
        .filter(Invoice.client_id == client_id)
        .order_by(Invoice.due_date.desc())
        .all()
    )


def _mark_invoice_paid(db: Session, invoice: Invoice, payment: PaymentCreate) -> Invoice:
    """Crea el Payment, marca la Invoice pagada, y reactiva al cliente si
    corresponde -- compartida entre pay_invoice (staff marca pagado
    directo) y confirm_payment_report (staff confirma un pago que el
    cliente reportó desde el portal). Asume que ya se validó que la
    factura no estaba pagada."""
    db.add(Payment(invoice_id=invoice.id, **payment.model_dump()))
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)

    # Reactivación automática: si el cliente estaba suspendido y esta era su
    # última factura pendiente/vencida (incluida una factura de reconexión,
    # si el modo de cobro es "al suspender" -- es solo otra fila más acá),
    # se reactiva sin que nadie tenga que hacerlo a mano.
    client = invoice.client
    if client.status == ClientStatus.SUSPENDED:
        other_unpaid = (
            db.query(Invoice)
            .filter(
                Invoice.client_id == client.id,
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
            )
            .count()
        )
        if other_unpaid == 0:
            reactivate_client_service(db, client)

    return invoice


@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceRead)
def pay_invoice(
    invoice_id: uuid.UUID,
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    ensure_zone_access(current_user, invoice.client.zone_id, "Factura no encontrada.")
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="La factura ya está pagada.")
    return _mark_invoice_paid(db, invoice, payload)


@router.post("/invoices/{invoice_id}/promise-to-pay", response_model=InvoiceRead)
def grant_promise_to_pay(
    invoice_id: uuid.UUID,
    payload: PromiseToPayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    ensure_zone_access(current_user, invoice.client.zone_id, "Factura no encontrada.")
    if invoice.status not in (InvoiceStatus.PENDING, InvoiceStatus.OVERDUE):
        raise HTTPException(
            status_code=400, detail="Solo se puede otorgar prórroga a facturas pendientes o vencidas."
        )

    today = date.today()
    if payload.until <= today:
        raise HTTPException(status_code=400, detail="La fecha de prórroga debe ser futura.")
    if payload.until > today + timedelta(days=MAX_PROMISE_TO_PAY_DAYS):
        raise HTTPException(
            status_code=400,
            detail=f"La prórroga no puede superar los {MAX_PROMISE_TO_PAY_DAYS} días.",
        )

    invoice.promise_to_pay_until = payload.until
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentRead])
def list_invoice_payments(invoice_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Payment]:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    return db.query(Payment).filter(Payment.invoice_id == invoice_id).order_by(Payment.paid_at.desc()).all()


@router.get("/payment-accounts", response_model=list[PaymentAccountRead])
def list_payment_accounts(db: Session = Depends(get_db)) -> list[PaymentAccount]:
    return db.query(PaymentAccount).order_by(PaymentAccount.name).all()


@router.post("/payment-accounts", response_model=PaymentAccountRead, status_code=201)
def create_payment_account(payload: PaymentAccountCreate, db: Session = Depends(get_db)) -> PaymentAccount:
    account = PaymentAccount(**payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/billing/balance-by-account", response_model=list[AccountBalanceRead])
def balance_by_account(db: Session = Depends(get_db)) -> list[AccountBalanceRead]:
    rows = (
        db.query(
            PaymentAccount.id,
            PaymentAccount.name,
            PaymentAccount.kind,
            func.coalesce(func.sum(Payment.amount), 0).label("total"),
        )
        .outerjoin(Payment, Payment.payment_account_id == PaymentAccount.id)
        .group_by(PaymentAccount.id)
        .order_by(PaymentAccount.name)
        .all()
    )
    return [
        AccountBalanceRead(id=row.id, name=row.name, kind=row.kind, total=float(row.total)) for row in rows
    ]


@router.get("/payment-reports", response_model=list[PaymentReportRead])
def list_payment_reports(
    status_filter: PaymentReportStatus | None = None, db: Session = Depends(get_db)
) -> list[PaymentReport]:
    query = db.query(PaymentReport)
    if status_filter is not None:
        query = query.filter(PaymentReport.status == status_filter)
    return query.order_by(PaymentReport.reported_at.desc()).all()


@router.post("/payment-reports/{report_id}/confirm", response_model=InvoiceRead)
def confirm_payment_report(
    report_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
) -> Invoice:
    """Confirma que el pago que el cliente reportó desde el portal
    efectivamente llegó -- reutiliza la misma lógica que pay_invoice, no la
    duplica. Nunca se confía ciegamente en lo que reporta el cliente."""
    report = db.get(PaymentReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Reporte de pago no encontrado.")
    if report.status != PaymentReportStatus.PENDING:
        raise HTTPException(status_code=400, detail="Este reporte ya fue revisado.")
    invoice = report.invoice
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="La factura ya está pagada.")

    payment = PaymentCreate(amount=report.amount, method=report.method, reference=report.reference)
    _mark_invoice_paid(db, invoice, payment)

    report.status = PaymentReportStatus.CONFIRMED
    report.reviewed_by_user_id = current_user.id
    report.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return invoice


@router.post("/payment-reports/{report_id}/reject", response_model=PaymentReportRead)
def reject_payment_report(
    report_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_admin)
) -> PaymentReport:
    report = db.get(PaymentReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Reporte de pago no encontrado.")
    if report.status != PaymentReportStatus.PENDING:
        raise HTTPException(status_code=400, detail="Este reporte ya fue revisado.")
    report.status = PaymentReportStatus.REJECTED
    report.reviewed_by_user_id = current_user.id
    report.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)
    return report
