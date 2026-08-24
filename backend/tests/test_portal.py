import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.api.routes.portal import (
    create_my_ticket,
    get_my_ticket,
    list_my_invoices,
    list_my_tickets,
    report_payment,
    reply_to_my_ticket,
    update_my_profile,
)
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_report import PaymentReportStatus
from app.schemas.portal import ClientPortalProfileUpdate, PaymentReportCreate
from app.schemas.ticket import TicketCreate, TicketReplyCreate


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Portal", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def _make_invoice(db_session, client: Client, **overrides) -> Invoice:
    invoice = Invoice(
        client_id=client.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        due_date=date(2026, 2, 5),
        amount=50000,
        status=InvoiceStatus.PENDING,
    )
    for field, value in overrides.items():
        setattr(invoice, field, value)
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def test_list_my_invoices_only_shows_own(db_session):
    mine = _make_client(db_session, full_name="Cliente A")
    other = _make_client(db_session, full_name="Cliente B")
    _make_invoice(db_session, mine)
    _make_invoice(db_session, other)

    result = list_my_invoices(db_session, mine)

    assert len(result) == 1
    assert result[0].client_id == mine.id


def test_report_payment_creates_pending_report_without_touching_invoice(db_session):
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)

    report = report_payment(
        PaymentReportCreate(invoice_id=invoice.id, amount=50000, method="nequi", reference="ABC123"),
        db_session,
        client,
    )

    assert report.status == PaymentReportStatus.PENDING
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PENDING  # no se marcó pagada sola


def test_report_payment_for_other_clients_invoice_rejected(db_session):
    client = _make_client(db_session)
    other = _make_client(db_session)
    invoice = _make_invoice(db_session, other)

    with pytest.raises(HTTPException) as exc_info:
        report_payment(
            PaymentReportCreate(invoice_id=invoice.id, amount=50000, method="nequi"), db_session, client
        )
    assert exc_info.value.status_code == 404


def test_report_payment_on_already_paid_invoice_rejected(db_session):
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client, status=InvoiceStatus.PAID)

    with pytest.raises(HTTPException) as exc_info:
        report_payment(
            PaymentReportCreate(invoice_id=invoice.id, amount=50000, method="nequi"), db_session, client
        )
    assert exc_info.value.status_code == 400


def test_create_ticket_forces_own_client_id_ignoring_payload(db_session):
    client = _make_client(db_session)
    someone_elses_id = uuid.uuid4()

    ticket = create_my_ticket(
        TicketCreate(client_id=someone_elses_id, subject="No anda", description="Sin internet"),
        db_session,
        client,
    )

    assert ticket.client_id == client.id
    assert ticket.created_by_client_id == client.id
    assert ticket.created_by_user_id is None


def test_cannot_see_another_clients_ticket(db_session):
    client = _make_client(db_session)
    other = _make_client(db_session)
    other_ticket = create_my_ticket(
        TicketCreate(subject="Ticket ajeno", description="..."), db_session, other
    )

    with pytest.raises(HTTPException) as exc_info:
        get_my_ticket(other_ticket.id, db_session, client)
    assert exc_info.value.status_code == 404


def test_list_my_tickets_only_own(db_session):
    client = _make_client(db_session)
    other = _make_client(db_session)
    create_my_ticket(TicketCreate(subject="Mío", description="..."), db_session, client)
    create_my_ticket(TicketCreate(subject="Ajeno", description="..."), db_session, other)

    result = list_my_tickets(db_session, client)

    assert len(result) == 1
    assert result[0].subject == "Mío"


def test_reply_to_my_ticket_sets_author_client_id(db_session):
    client = _make_client(db_session)
    ticket = create_my_ticket(TicketCreate(subject="X", description="Y"), db_session, client)

    reply = reply_to_my_ticket(ticket.id, TicketReplyCreate(body="una respuesta"), db_session, client)

    assert reply.author_client_id == client.id
    assert reply.author_user_id is None


def test_update_my_profile_only_touches_allowed_fields(db_session):
    client = _make_client(db_session, full_name="No Cambia", identification="999")

    updated = update_my_profile(
        ClientPortalProfileUpdate(phone="3001234567", email="nuevo@correo.com"), db_session, client
    )

    assert updated.phone == "3001234567"
    assert updated.email == "nuevo@correo.com"
    assert updated.full_name == "No Cambia"  # no es editable desde acá
    assert updated.identification == "999"
