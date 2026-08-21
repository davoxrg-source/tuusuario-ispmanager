import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.schemas.billing import InvoiceCreate, InvoiceRead, PaymentCreate, PaymentRead

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


@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentRead])
def list_invoice_payments(invoice_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Payment]:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    return db.query(Payment).filter(Payment.invoice_id == invoice_id).order_by(Payment.paid_at.desc()).all()
