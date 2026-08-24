import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.api.routes.billing import confirm_payment_report, list_payment_reports, reject_payment_report
from app.api.routes.portal import report_payment
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_report import PaymentReportStatus
from app.models.user import User, UserRole
from app.schemas.portal import PaymentReportCreate


def _make_admin(db_session) -> User:
    admin = User(
        full_name="Admin", email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x", role=UserRole.ADMIN
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
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
        amount=45000,
        status=InvoiceStatus.PENDING,
    )
    for field, value in overrides.items():
        setattr(invoice, field, value)
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def test_confirm_payment_report_marks_invoice_paid_and_reactivates(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session, status=ClientStatus.SUSPENDED)
    invoice = _make_invoice(db_session, client)
    report = report_payment(
        PaymentReportCreate(invoice_id=invoice.id, amount=45000, method="nequi", reference="XYZ"),
        db_session,
        client,
    )

    invoice_after = confirm_payment_report(report.id, db_session, admin)

    assert invoice_after.status == InvoiceStatus.PAID
    db_session.refresh(client)
    assert client.status == ClientStatus.ACTIVE  # reactivación automática, misma lógica que pay_invoice
    db_session.refresh(report)
    assert report.status == PaymentReportStatus.CONFIRMED
    assert report.reviewed_by_user_id == admin.id
    assert report.reviewed_at is not None


def test_reject_payment_report_does_not_touch_invoice(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)
    report = report_payment(
        PaymentReportCreate(invoice_id=invoice.id, amount=45000, method="nequi"), db_session, client
    )

    rejected = reject_payment_report(report.id, db_session, admin)

    assert rejected.status == PaymentReportStatus.REJECTED
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PENDING


def test_reviewing_an_already_reviewed_report_rejected(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)
    report = report_payment(
        PaymentReportCreate(invoice_id=invoice.id, amount=45000, method="nequi"), db_session, client
    )
    reject_payment_report(report.id, db_session, admin)

    with pytest.raises(HTTPException) as exc_info:
        confirm_payment_report(report.id, db_session, admin)
    assert exc_info.value.status_code == 400


def test_list_payment_reports_filters_by_status(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session)
    invoice_a = _make_invoice(db_session, client)
    invoice_b = _make_invoice(db_session, client)
    report_a = report_payment(
        PaymentReportCreate(invoice_id=invoice_a.id, amount=45000, method="nequi"), db_session, client
    )
    report_payment(PaymentReportCreate(invoice_id=invoice_b.id, amount=45000, method="nequi"), db_session, client)
    confirm_payment_report(report_a.id, db_session, admin)

    pending = list_payment_reports(PaymentReportStatus.PENDING, db_session)
    confirmed = list_payment_reports(PaymentReportStatus.CONFIRMED, db_session)

    assert len(pending) == 1
    assert len(confirmed) == 1
    assert confirmed[0].id == report_a.id
