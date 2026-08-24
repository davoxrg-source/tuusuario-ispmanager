from datetime import date, timedelta
from unittest.mock import patch

from app.models.billing_settings import BillingSettings
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.services.billing.invoicing import send_payment_reminders


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def _make_invoice(db_session, client: Client, due_date: date, **overrides) -> Invoice:
    invoice = Invoice(
        client_id=client.id,
        period_start=due_date - timedelta(days=30),
        period_end=due_date,
        due_date=due_date,
        amount=40000,
        status=InvoiceStatus.PENDING,
    )
    for field, value in overrides.items():
        setattr(invoice, field, value)
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def _settings(db_session, **overrides) -> BillingSettings:
    settings = db_session.query(BillingSettings).first()
    for field, value in overrides.items():
        setattr(settings, field, value)
    db_session.commit()
    db_session.refresh(settings)
    return settings


def test_disabled_by_default_sends_nothing(db_session):
    client = _make_client(db_session)
    _make_invoice(db_session, client, date.today() + timedelta(days=2))
    settings = _settings(db_session, payment_reminder_enabled=False)

    with patch("app.services.billing.invoicing.notify_client") as mock_notify:
        sent = send_payment_reminders(db_session, settings, date.today())

    assert sent == []
    mock_notify.assert_not_called()


def test_sends_once_for_invoice_due_within_window(db_session):
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client, date.today() + timedelta(days=2))
    settings = _settings(db_session, payment_reminder_enabled=True, payment_reminder_days_before_due=3)

    with patch("app.services.billing.invoicing.notify_client") as mock_notify:
        sent = send_payment_reminders(db_session, settings, date.today())

    assert len(sent) == 1
    assert sent[0].id == invoice.id
    mock_notify.assert_called_once()
    db_session.refresh(invoice)
    assert invoice.reminder_sent_at is not None


def test_does_not_resend_once_guard_is_set(db_session):
    client = _make_client(db_session)
    _make_invoice(db_session, client, date.today() + timedelta(days=2))
    settings = _settings(db_session, payment_reminder_enabled=True, payment_reminder_days_before_due=3)

    with patch("app.services.billing.invoicing.notify_client"):
        send_payment_reminders(db_session, settings, date.today())
        second_run = send_payment_reminders(db_session, settings, date.today())

    assert second_run == []


def test_ignores_invoices_outside_the_window(db_session):
    client = _make_client(db_session)
    _make_invoice(db_session, client, date.today() + timedelta(days=10))  # muy lejos todavía
    settings = _settings(db_session, payment_reminder_enabled=True, payment_reminder_days_before_due=3)

    with patch("app.services.billing.invoicing.notify_client") as mock_notify:
        sent = send_payment_reminders(db_session, settings, date.today())

    assert sent == []
    mock_notify.assert_not_called()


def test_ignores_already_paid_invoices(db_session):
    client = _make_client(db_session)
    _make_invoice(db_session, client, date.today() + timedelta(days=2), status=InvoiceStatus.PAID)
    settings = _settings(db_session, payment_reminder_enabled=True, payment_reminder_days_before_due=3)

    sent = send_payment_reminders(db_session, settings, date.today())

    assert sent == []
