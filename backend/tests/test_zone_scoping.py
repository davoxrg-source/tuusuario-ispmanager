import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.api.deps import ensure_zone_access, zone_scope_filter_ids
from app.api.routes.billing import pay_invoice
from app.api.routes.clients import get_client, list_clients, suspend_client
from app.api.routes.devices import get_device, list_devices
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.mikrotik_device import MikrotikDevice
from app.models.user import User, UserRole
from app.schemas.billing import PaymentCreate

ADMIN = User(role=UserRole.ADMIN)


def _technician(*zones) -> User:
    tech = User(role=UserRole.TECHNICIAN)
    tech.zones = list(zones)
    return tech


def _make_zone(db_session, name: str):
    from app.api.routes.zones import create_zone
    from app.schemas.zone import ZoneCreate

    return create_zone(ZoneCreate(name=name), db_session)


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def _make_device(db_session, **overrides) -> MikrotikDevice:
    device = MikrotikDevice(
        name="Router Test", host="10.0.0.1", username="admin", encrypted_password="unused"
    )
    for field, value in overrides.items():
        setattr(device, field, value)
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


# --- ensure_zone_access / zone_scope_filter_ids, unitario ---


def test_ensure_zone_access_admin_bypasses_everything():
    ensure_zone_access(ADMIN, None, "no encontrado")
    ensure_zone_access(ADMIN, uuid.uuid4(), "no encontrado")  # zona que ni existe -- igual pasa


def test_ensure_zone_access_zero_zones_denies_all():
    tech = _technician()
    with pytest.raises(HTTPException) as exc_info:
        ensure_zone_access(tech, uuid.uuid4(), "no encontrado")
    assert exc_info.value.status_code == 404


def test_ensure_zone_access_none_zone_id_denied_for_non_admin(db_session):
    zone = _make_zone(db_session, "ZONA_A")
    tech = _technician(zone)
    with pytest.raises(HTTPException):
        ensure_zone_access(tech, None, "no encontrado")


def test_ensure_zone_access_matching_and_other_zone(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    zone_b = _make_zone(db_session, "ZONA_B")
    tech = _technician(zone_a)

    ensure_zone_access(tech, zone_a.id, "no encontrado")  # no lanza

    with pytest.raises(HTTPException):
        ensure_zone_access(tech, zone_b.id, "no encontrado")


def test_zone_scope_filter_ids_admin_returns_none():
    assert zone_scope_filter_ids(ADMIN) is None


def test_zone_scope_filter_ids_technician_returns_assigned_ids(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    tech = _technician(zone_a)
    assert zone_scope_filter_ids(tech) == [zone_a.id]


# --- integración por ruta ---


def test_get_client_in_other_zone_returns_404_for_technician(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    zone_b = _make_zone(db_session, "ZONA_B")
    client_b = _make_client(db_session, zone_id=zone_b.id)
    tech = _technician(zone_a)

    with pytest.raises(HTTPException) as exc_info:
        get_client(client_b.id, db_session, tech)
    assert exc_info.value.status_code == 404


def test_get_client_in_own_zone_allowed_for_technician(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    client_a = _make_client(db_session, zone_id=zone_a.id)
    tech = _technician(zone_a)

    result = get_client(client_a.id, db_session, tech)
    assert result.id == client_a.id


def test_list_clients_filters_by_technician_zone(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    zone_b = _make_zone(db_session, "ZONA_B")
    client_a = _make_client(db_session, zone_id=zone_a.id)
    _make_client(db_session, zone_id=zone_b.id)
    _make_client(db_session, zone_id=None)  # sin zona
    tech = _technician(zone_a)

    result = list_clients(db_session, tech)

    assert [c.id for c in result] == [client_a.id]


def test_suspend_client_in_other_zone_denied_for_technician(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    zone_b = _make_zone(db_session, "ZONA_B")
    client_b = _make_client(db_session, zone_id=zone_b.id)
    tech = _technician(zone_a)

    with pytest.raises(HTTPException) as exc_info:
        suspend_client(client_b.id, db_session, tech)
    assert exc_info.value.status_code == 404


def test_get_device_in_other_zone_returns_404_for_technician(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    zone_b = _make_zone(db_session, "ZONA_B")
    device_b = _make_device(db_session, zone_id=zone_b.id)
    tech = _technician(zone_a)

    with pytest.raises(HTTPException) as exc_info:
        get_device(device_b.id, db_session, tech)
    assert exc_info.value.status_code == 404


def test_list_devices_filters_by_technician_zone(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    device_a = _make_device(db_session, zone_id=zone_a.id)
    _make_device(db_session, name="Router Otro", zone_id=None)
    tech = _technician(zone_a)

    result = list_devices(db_session, tech)

    assert [d.id for d in result] == [device_a.id]


def test_pay_invoice_for_client_in_other_zone_denied(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    zone_b = _make_zone(db_session, "ZONA_B")
    client_b = _make_client(db_session, zone_id=zone_b.id)
    invoice = Invoice(
        client_id=client_b.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        due_date=date(2026, 3, 31),
        amount=300,
        status=InvoiceStatus.PENDING,
    )
    db_session.add(invoice)
    db_session.commit()
    tech = _technician(zone_a)

    with pytest.raises(HTTPException) as exc_info:
        pay_invoice(invoice.id, PaymentCreate(amount=300, method="manual"), db_session, tech)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Factura no encontrada."


def test_admin_unaffected_by_zone_scoping(db_session):
    zone_a = _make_zone(db_session, "ZONA_A")
    client_a = _make_client(db_session, zone_id=zone_a.id)
    client_none = _make_client(db_session, zone_id=None)
    device_a = _make_device(db_session, zone_id=zone_a.id)

    # ADMIN ve todo, sin importar la zona ni la ausencia de ella.
    assert get_client(client_a.id, db_session, ADMIN).id == client_a.id
    assert get_client(client_none.id, db_session, ADMIN).id == client_none.id
    assert get_device(device_a.id, db_session, ADMIN).id == device_a.id
    assert {c.id for c in list_clients(db_session, ADMIN)} == {client_a.id, client_none.id}
