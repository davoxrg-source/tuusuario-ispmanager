import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.api.routes.external_api import (
    get_external_client,
    get_external_invoice,
    list_external_client_invoices,
    list_external_clients,
    list_external_plans,
)
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.plan import Plan


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


def test_list_external_clients_returns_curated_fields_only(db_session):
    client = _make_client(
        db_session, identification="123", email="c@compusoft-isp.com", ip_address="10.0.0.5"
    )

    result = list_external_clients(limit=100, offset=0, db=db_session)

    assert len(result) == 1
    # No es un test de shape de dict -- confirma que el modelo ORM crudo se
    # devuelve (Pydantic filtra vía response_model en la capa HTTP, no acá);
    # lo que sí se prueba directo es que el campo sensible no forma parte
    # del schema externo en absoluto.
    from app.schemas.external_api import ExternalClientRead

    assert "ip_address" not in ExternalClientRead.model_fields
    assert "identification" in ExternalClientRead.model_fields


def test_get_external_client_404_on_unknown_id(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_external_client(uuid.uuid4(), db_session)
    assert exc_info.value.status_code == 404


def test_list_external_client_invoices_scoped_to_client(db_session):
    client_a = _make_client(db_session)
    client_b = _make_client(db_session)
    _make_invoice(db_session, client_a)
    _make_invoice(db_session, client_b)

    result = list_external_client_invoices(client_a.id, db_session)

    assert len(result) == 1
    assert result[0].client_id == client_a.id


def test_get_external_invoice_404_on_unknown_id(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_external_invoice(uuid.uuid4(), db_session)
    assert exc_info.value.status_code == 404


def test_list_external_plans_returns_all(db_session):
    db_session.add(Plan(name=f"Plan-{uuid.uuid4()}", download_speed_mbps=10, upload_speed_mbps=5, price=50000))
    db_session.commit()

    result = list_external_plans(db_session)

    assert len(result) >= 1
