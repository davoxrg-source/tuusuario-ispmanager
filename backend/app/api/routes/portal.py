import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_client
from app.core.config import get_settings
from app.db.session import get_db
from app.models.client import Client
from app.models.device_token import DeviceOwnerType, DeviceToken
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_report import PaymentReport
from app.models.push_subscription import PushSubscription
from app.models.ticket import Ticket, TicketReply
from app.schemas.billing import InvoiceRead
from app.schemas.notification import DeviceTokenCreate, PushSubscriptionCreate, VapidPublicKeyRead
from app.schemas.portal import (
    ClientPortalProfileUpdate,
    ClientPortalRead,
    PaymentReportCreate,
    PaymentReportRead,
)
from app.schemas.ticket import TicketCreate, TicketReplyCreate, TicketReplyRead, TicketRead
from app.schemas.wompi import CheckoutUrlRead
from app.services.wompi.service import create_checkout

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


@router.post("/invoices/{invoice_id}/checkout-url", response_model=CheckoutUrlRead)
def get_checkout_url(
    invoice_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> CheckoutUrlRead:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None or invoice.client_id != current_client.id:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    if invoice.status == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="La factura ya está pagada.")

    # El redirect es solo informativo (ver docstring de handle_webhook) --
    # el ?wompi_id= es un parámetro propio, no de Wompi, para que
    # Invoices.tsx muestre "estamos confirmando tu pago" en vez de asumir
    # que ya se acreditó.
    redirect_url = f"{str(request.base_url).rstrip('/')}/portal/facturas?wompi_id={invoice_id}"
    try:
        transaction, checkout_url = create_checkout(db, invoice, redirect_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CheckoutUrlRead(checkout_url=checkout_url, reference=transaction.reference)


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


@router.get("/vapid-public-key", response_model=VapidPublicKeyRead)
def get_vapid_public_key() -> VapidPublicKeyRead:
    return VapidPublicKeyRead(public_key=get_settings().vapid_public_key)


@router.post("/push-subscriptions", status_code=204)
def create_push_subscription(
    payload: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> None:
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    if existing:
        existing.client_id = current_client.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    else:
        db.add(
            PushSubscription(
                client_id=current_client.id,
                endpoint=payload.endpoint,
                p256dh=payload.keys.p256dh,
                auth=payload.keys.auth,
            )
        )
    db.commit()


@router.delete("/push-subscriptions", status_code=204)
def delete_push_subscription(
    endpoint: str,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> None:
    # endpoint como query param, no como body -- evita las inconsistencias
    # de clientes HTTP con DELETE+body (ej. axios necesita { data: ... }
    # explícito, fácil de olvidar).
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == endpoint, PushSubscription.client_id == current_client.id
    ).delete()
    db.commit()


@router.post("/device-tokens", status_code=204)
def create_device_token(
    payload: DeviceTokenCreate,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> None:
    """Token FCM de la app móvil de clientes -- ver
    app/services/notifications/fcm_provider.py. Mismo patrón upsert-por-
    token que create_push_subscription (reinstalar la app en otro celular
    no debe dejar 2 tokens huérfanos apuntando al mismo dispositivo viejo)."""
    existing = db.query(DeviceToken).filter(DeviceToken.fcm_token == payload.fcm_token).first()
    if existing:
        existing.owner_type = DeviceOwnerType.CLIENT
        existing.owner_id = current_client.id
        existing.platform = payload.platform
    else:
        db.add(
            DeviceToken(
                owner_type=DeviceOwnerType.CLIENT,
                owner_id=current_client.id,
                fcm_token=payload.fcm_token,
                platform=payload.platform,
            )
        )
    db.commit()


@router.delete("/device-tokens", status_code=204)
def delete_device_token(
    fcm_token: str,
    db: Session = Depends(get_db),
    current_client: Client = Depends(get_current_client),
) -> None:
    db.query(DeviceToken).filter(
        DeviceToken.fcm_token == fcm_token,
        DeviceToken.owner_type == DeviceOwnerType.CLIENT,
        DeviceToken.owner_id == current_client.id,
    ).delete()
    db.commit()
