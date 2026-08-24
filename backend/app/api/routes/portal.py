import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_client
from app.db.session import get_db
from app.models.client import Client
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_report import PaymentReport
from app.models.ticket import Ticket, TicketReply
from app.schemas.billing import InvoiceRead
from app.schemas.portal import (
    ClientPortalProfileUpdate,
    ClientPortalRead,
    PaymentReportCreate,
    PaymentReportRead,
)
from app.schemas.ticket import TicketCreate, TicketReplyCreate, TicketReplyRead, TicketRead

router = APIRouter(prefix="/portal", tags=["portal"], dependencies=[Depends(get_current_client)])


@router.get("/invoices", response_model=list[InvoiceRead])
def list_my_invoices(
    db: Session = Depends(get_db), current_client: Client = Depends(get_current_client)
) -> list[Invoice]:
    return (
        db.query(Invoice)
        .filter(Invoice.client_id == current_client.id)
        .order_by(Invoice.due_date.desc())
        .all()
    )


@router.post("/payment-reports", response_model=PaymentReportRead, status_code=201)
def report_payment(
    payload: PaymentReportCreate,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> PaymentReport:
    invoice = db.get(Invoice, payload.invoice_id)
    if invoice is None or invoice.client_id != current_client.id:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="La factura ya está pagada.")
    report = PaymentReport(
        invoice_id=invoice.id,
        client_id=current_client.id,
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
        note=payload.note,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/tickets", response_model=list[TicketRead])
def list_my_tickets(
    db: Session = Depends(get_db), current_client: Client = Depends(get_current_client)
) -> list[Ticket]:
    return (
        db.query(Ticket)
        .filter(Ticket.client_id == current_client.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )


@router.post("/tickets", response_model=TicketRead, status_code=201)
def create_my_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> Ticket:
    # client_id/created_by_client_id se fuerzan desde la sesión -- nunca del
    # body, para que un cliente no pueda abrir un ticket a nombre de otro.
    data = payload.model_dump(exclude={"client_id", "assigned_to_user_id"})
    ticket = Ticket(**data, client_id=current_client.id, created_by_client_id=current_client.id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def _get_my_ticket_or_404(db: Session, ticket_id: uuid.UUID, current_client: Client) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.client_id != current_client.id:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    return ticket


@router.get("/tickets/{ticket_id}", response_model=TicketRead)
def get_my_ticket(
    ticket_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> Ticket:
    return _get_my_ticket_or_404(db, ticket_id, current_client)


@router.get("/tickets/{ticket_id}/replies", response_model=list[TicketReplyRead])
def list_my_ticket_replies(
    ticket_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> list[TicketReply]:
    _get_my_ticket_or_404(db, ticket_id, current_client)
    return (
        db.query(TicketReply)
        .filter(TicketReply.ticket_id == ticket_id)
        .order_by(TicketReply.created_at)
        .all()
    )


@router.post("/tickets/{ticket_id}/reply", response_model=TicketReplyRead, status_code=201)
def reply_to_my_ticket(
    ticket_id: uuid.UUID,
    payload: TicketReplyCreate,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> TicketReply:
    _get_my_ticket_or_404(db, ticket_id, current_client)
    reply = TicketReply(ticket_id=ticket_id, author_client_id=current_client.id, body=payload.body)
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply


@router.patch("/profile", response_model=ClientPortalRead)
def update_my_profile(
    payload: ClientPortalProfileUpdate,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> Client:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_client, field, value)
    db.commit()
    db.refresh(current_client)
    return current_client
