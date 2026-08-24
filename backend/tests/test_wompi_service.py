import hashlib
from datetime import date, timedelta

import pytest

from app.core.config import get_settings
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.wompi_transaction import WompiTransaction, WompiTransactionStatus
from app.services.wompi.service import create_checkout, handle_webhook


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


def _configure_wompi(monkeypatch, **overrides):
    settings = get_settings()
    defaults = {
        "wompi_public_key": "pub_test_abc",
        "wompi_integrity_secret": "test_integrity_secret",
        "wompi_events_secret": "test_events_secret",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setattr(settings, key, value)
    return settings


def _webhook_payload(reference: str, status: str, amount_in_cents: int, secret: str) -> dict:
    properties = ["transaction.id", "transaction.status", "transaction.reference", "transaction.amount_in_cents"]
    transaction = {
        "id": "01-999",
        "status": status,
        "reference": reference,
        "amount_in_cents": amount_in_cents,
    }
    timestamp = 1530291411
    concat = "01-999" + status + reference + str(amount_in_cents) + str(timestamp) + secret
    checksum = hashlib.sha256(concat.encode()).hexdigest()
    return {
        "data": {"transaction": transaction},
        "signature": {"properties": properties, "checksum": checksum},
        "timestamp": timestamp,
    }


def test_create_checkout_without_wompi_configured_raises(db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "wompi_public_key", "")
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)

    with pytest.raises(ValueError):
        create_checkout(db_session, invoice, "https://example.com/redirect")


def test_create_checkout_generates_unique_reference_and_url(db_session, monkeypatch):
    _configure_wompi(monkeypatch)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client, amount=45000)

    tx1, url1 = create_checkout(db_session, invoice, "https://example.com/redirect")
    tx2, url2 = create_checkout(db_session, invoice, "https://example.com/redirect")

    assert tx1.reference != tx2.reference  # cada intento tiene su propia referencia
    assert "pub_test_abc" in url1
    assert "amount-in-cents=4500000" in url1  # 45000 pesos -> 4500000 centavos
    assert tx1.status == WompiTransactionStatus.PENDING


def test_handle_webhook_invalid_signature_raises(db_session, monkeypatch):
    _configure_wompi(monkeypatch)
    payload = _webhook_payload("REF-X", "APPROVED", 100, "secreto_incorrecto")

    with pytest.raises(ValueError):
        handle_webhook(db_session, payload)


def test_handle_webhook_approved_marks_invoice_paid_and_reactivates(db_session, monkeypatch):
    settings = _configure_wompi(monkeypatch)
    client = _make_client(db_session, status=ClientStatus.SUSPENDED)
    invoice = _make_invoice(db_session, client, amount=45000)
    tx, _ = create_checkout(db_session, invoice, "https://example.com/redirect")

    payload = _webhook_payload(tx.reference, "APPROVED", tx.amount_in_cents, settings.wompi_events_secret)
    handle_webhook(db_session, payload)

    db_session.refresh(invoice)
    db_session.refresh(tx)
    db_session.refresh(client)
    assert invoice.status == InvoiceStatus.PAID
    assert tx.status == WompiTransactionStatus.APPROVED
    assert tx.wompi_transaction_id == "01-999"
    assert client.status == ClientStatus.ACTIVE  # reactivación automática, misma lógica que los otros 2 caminos


def test_handle_webhook_declined_does_not_mark_paid(db_session, monkeypatch):
    settings = _configure_wompi(monkeypatch)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)
    tx, _ = create_checkout(db_session, invoice, "https://example.com/redirect")

    payload = _webhook_payload(tx.reference, "DECLINED", tx.amount_in_cents, settings.wompi_events_secret)
    handle_webhook(db_session, payload)

    db_session.refresh(invoice)
    db_session.refresh(tx)
    assert invoice.status == InvoiceStatus.PENDING
    assert tx.status == WompiTransactionStatus.DECLINED


def test_handle_webhook_is_idempotent_on_retry(db_session, monkeypatch):
    settings = _configure_wompi(monkeypatch)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)
    tx, _ = create_checkout(db_session, invoice, "https://example.com/redirect")
    payload = _webhook_payload(tx.reference, "APPROVED", tx.amount_in_cents, settings.wompi_events_secret)

    handle_webhook(db_session, payload)
    handle_webhook(db_session, payload)  # Wompi reintenta hasta 3 veces -- no debe duplicar el Payment

    db_session.refresh(invoice)
    assert len(invoice.payments) == 1


def test_handle_webhook_rejects_payload_where_reference_is_not_signed(db_session, monkeypatch):
    # Aunque el checksum general valide, si "transaction.reference" no está
    # en signature.properties no se puede confiar en a qué factura apunta
    # -- ver comentario en handle_webhook.
    settings = _configure_wompi(monkeypatch)
    client = _make_client(db_session)
    invoice = _make_invoice(db_session, client)
    tx, _ = create_checkout(db_session, invoice, "https://example.com/redirect")

    payload = _webhook_payload(tx.reference, "APPROVED", tx.amount_in_cents, settings.wompi_events_secret)
    payload["signature"]["properties"] = ["transaction.id", "transaction.status", "transaction.amount_in_cents"]
    # Recalcula el checksum SIN reference en la concatenación, para que siga
    # siendo "válido" según properties -- el ataque real sería justamente
    # este: un checksum legítimo que no protege el campo reference.
    concat = "01-999" + "APPROVED" + str(tx.amount_in_cents) + str(payload["timestamp"]) + settings.wompi_events_secret
    payload["signature"]["checksum"] = hashlib.sha256(concat.encode()).hexdigest()

    with pytest.raises(ValueError):
        handle_webhook(db_session, payload)

    db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.PENDING


def test_handle_webhook_unknown_reference_is_ignored_quietly(db_session, monkeypatch):
    settings = _configure_wompi(monkeypatch)
    payload = _webhook_payload("REF-NUNCA-EXISTIO", "APPROVED", 1000, settings.wompi_events_secret)

    handle_webhook(db_session, payload)  # no debe tirar excepción

    assert db_session.query(WompiTransaction).count() == 0
