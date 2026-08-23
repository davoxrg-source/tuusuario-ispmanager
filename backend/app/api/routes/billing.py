import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.schemas.billing import InvoiceCreate, InvoiceRead, PaymentCreate, PaymentRead, PromiseToPayCreate

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


@router.get("/clients/{client_id}/invoices", response_model=list[InvoiceRead])
def list_client_invoices(client_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Invoice]:
    return (
        db.query(Invoice)
        .filter(Invoice.client_id == client_id)
        .order_by(Invoice.due_date.desc())
        .all()
    )


@router.post("/invoices/{invoice_id}/pay", response_model=InvoiceRead)
def pay_invoice(invoice_id: uuid.UUID, payload: PaymentCreate, db: Session = Depends(get_db)) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="La factura ya está pagada.")

    payment = Payment(invoice_id=invoice.id, **payload.model_dump())
    db.add(payment)
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/invoices/{invoice_id}/promise-to-pay", response_model=InvoiceRead)
def grant_promise_to_pay(
    invoice_id: uuid.UUID, payload: PromiseToPayCreate, db: Session = Depends(get_db)
) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
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
