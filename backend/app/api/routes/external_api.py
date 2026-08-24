import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_api_key
from app.db.session import get_db
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.plan import Plan
from app.schemas.external_api import ExternalClientRead, ExternalInvoiceRead, ExternalPlanRead

# Superficie curada y estable para integraciones externas -- namespace
# propio /v1, separado del resto de la API interna (que no tiene versión
# porque puede cambiar libremente). Solo lectura, solo clientes/facturas/
# planes (alcance confirmado con el usuario, ver plan de la Fase 5d).
router = APIRouter(prefix="/v1", tags=["v1-external-api"], dependencies=[Depends(get_current_api_key)])


@router.get("/clients", response_model=list[ExternalClientRead])
def list_external_clients(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Client]:
    return db.query(Client).order_by(Client.full_name).offset(offset).limit(limit).all()


@router.get("/clients/{client_id}", response_model=ExternalClientRead)
def get_external_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return client


@router.get("/clients/{client_id}/invoices", response_model=list[ExternalInvoiceRead])
def list_external_client_invoices(client_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Invoice]:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return (
        db.query(Invoice)
        .filter(Invoice.client_id == client_id)
        .order_by(Invoice.due_date.desc())
        .all()
    )


@router.get("/invoices/{invoice_id}", response_model=ExternalInvoiceRead)
def get_external_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db)) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    return invoice


@router.get("/plans", response_model=list[ExternalPlanRead])
def list_external_plans(db: Session = Depends(get_db)) -> list[Plan]:
    return db.query(Plan).order_by(Plan.name).all()
