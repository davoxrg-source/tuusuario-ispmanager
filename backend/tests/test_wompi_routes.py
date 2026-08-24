import hashlib
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes.portal import get_checkout_url
from app.api.routes.webhooks import wompi_webhook
from app.core.config import get_settings
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus


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
        period_start=date.today(),
        period_end=date.today() + timedelta(days=30),
        due_date=date.today() + timedelta(days=10),
        amount=45000,
        status=InvoiceStatus.PENDING,
    )
    for field, value in overrides.items():
        setattr(invoice, field, value)
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def _fake_request() -> Request:
    scope = {"type": "http", "client": ("10.0.0.5", 12345), "headers": [], "scheme": "http", "server": ("10.0.0.10", 8000)}
    return Request(scope)


def _configure_wompi(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "wompi_public_key", "pub_test_abc")
    monkeypatch.setattr(settings, "wompi_integrity_secret", "test_integrity_secret")
    monkeypatch.setattr(settings, "wompi_events_secret", "test_events_secret")
    return settings


def test_get_checkout_url_scoped_to_own_invoice(db_session, monkeypatch):
    _configure_wompi(monkeypatch)
    mine = _make_client(db_session)
    other = _make_client(db_session)
    invoice = _make_invoice(db_session, other)

    with pytest.raises(HTTPException) as exc_info:
        get_checkout_url(invoice.id, _fake_request(), db_session, mine)
    assert exc_info.value.status_code == 404


def test_get_checkout_url_returns_a_valid_link(db_session, monkeypatch):
    _configure_wompi(monkeypatch)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)

    result = get_checkout_url(invoice.id, _fake_request(), db_session, client)

    assert result.checkout_url.startswith("https://checkout.wompi.co/p/?")
    assert result.reference


def test_get_checkout_url_on_paid_invoice_rejected(db_session, monkeypatch):
    _configure_wompi(monkeypatch)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client, status=InvoiceStatus.PAID)

    with pytest.raises(HTTPException) as exc_info:
        get_checkout_url(invoice.id, _fake_request(), db_session, client)
    assert exc_info.value.status_code == 400


def test_get_checkout_url_without_wompi_configured_returns_400(db_session):
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)

    with pytest.raises(HTTPException) as exc_info:
        get_checkout_url(invoice.id, _fake_request(), db_session, client)
    assert exc_info.value.status_code == 400


def test_webhook_route_accepts_valid_signature(db_session, monkeypatch):
    settings = _configure_wompi(monkeypatch)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)
    from app.services.wompi.service import create_checkout

    tx, _ = create_checkout(db_session, invoice, "https://example.com/redirect")

    properties = ["transaction.id", "transaction.status", "transaction.reference", "transaction.amount_in_cents"]
    timestamp = 1530291411
    concat = "01-999" + "APPROVED" + tx.reference + str(tx.amount_in_cents) + str(timestamp) + settings.wompi_events_secret
    payload = {
        "data": {
            "transaction": {
                "id": "01-999",
                "status": "APPROVED",
                "reference": tx.reference,
                "amount_in_cents": tx.amount_in_cents,
            }
        },
        "signature": {"properties": properties, "checksum": hashlib.sha256(concat.encode()).hexdigest()},
        "timestamp": timestamp,
    }

    result = wompi_webhook(payload, db_session)
    assert result == {"status": "ok"}
    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PAID


def test_webhook_route_rejects_invalid_signature_with_400(db_session, monkeypatch):
    _configure_wompi(monkeypatch)
    payload = {
        "data": {"transaction": {"id": "01-1", "status": "APPROVED", "reference": "REF-X", "amount_in_cents": 1}},
        "signature": {"properties": ["transaction.id"], "checksum": "no-es-un-checksum-valido"},
        "timestamp": 1,
    }

    with pytest.raises(HTTPException) as exc_info:
        wompi_webhook(payload, db_session)
    assert exc_info.value.status_code == 400
