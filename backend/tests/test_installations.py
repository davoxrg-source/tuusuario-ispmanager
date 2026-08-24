import uuid
from datetime import date

import pytest
from fastapi import HTTPException

from app.api.routes.clients import delete_client
from app.api.routes.installations import (
    calculate_route_distance,
    create_installation,
    delete_installation,
    list_installations,
    update_installation,
)
from app.models.client import Client, ClientStatus
from app.models.installation import InstallationStatus
from app.models.user import User, UserRole
from app.schemas.installation import InstallationCreate, InstallationUpdate, RouteDistanceRequest


def _make_admin(db_session) -> User:
    admin = User(full_name="Admin", email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x", role=UserRole.ADMIN)
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


def test_installation_crud(db_session):
    client = _make_client(db_session)

    installation = create_installation(
        InstallationCreate(client_id=client.id, scheduled_date=date(2026, 9, 1)), db_session
    )
    assert installation.status == InstallationStatus.SCHEDULED

    updated = update_installation(
        installation.id, InstallationUpdate(status=InstallationStatus.COMPLETED), db_session
    )
    assert updated.status == InstallationStatus.COMPLETED

    assert [i.id for i in list_installations(db_session)] == [installation.id]


def test_deleting_client_cascades_to_installations(db_session):
    client = _make_client(db_session)
    installation = create_installation(
        InstallationCreate(client_id=client.id, scheduled_date=date(2026, 9, 1)), db_session
    )

    admin = _make_admin(db_session)
    delete_client(client.id, db_session, admin)

    from app.api.routes.installations import _get_installation_or_404

    with pytest.raises(HTTPException) as exc_info:
        _get_installation_or_404(db_session, installation.id)
    assert exc_info.value.status_code == 404


def test_route_distance_known_points(db_session):
    tulua = _make_client(db_session, latitude=4.0847, longitude=-76.1954)
    palmira = _make_client(db_session, latitude=3.5322, longitude=-76.3033)
    inst_a = create_installation(
        InstallationCreate(client_id=tulua.id, scheduled_date=date(2026, 9, 1)), db_session
    )
    inst_b = create_installation(
        InstallationCreate(client_id=palmira.id, scheduled_date=date(2026, 9, 1)), db_session
    )

    result = calculate_route_distance(
        RouteDistanceRequest(installation_ids=[inst_a.id, inst_b.id]), db_session
    )

    assert 60 < result.total_km < 70
    assert len(result.legs) == 1
    assert result.legs[0].from_id == inst_a.id
    assert result.legs[0].to_id == inst_b.id


def test_route_distance_rejects_missing_coordinates(db_session):
    with_coords = _make_client(db_session, latitude=4.0, longitude=-76.0)
    without_coords = _make_client(db_session)
    inst_a = create_installation(
        InstallationCreate(client_id=with_coords.id, scheduled_date=date(2026, 9, 1)), db_session
    )
    inst_b = create_installation(
        InstallationCreate(client_id=without_coords.id, scheduled_date=date(2026, 9, 1)), db_session
    )

    with pytest.raises(HTTPException) as exc_info:
        calculate_route_distance(
            RouteDistanceRequest(installation_ids=[inst_a.id, inst_b.id]), db_session
        )
    assert exc_info.value.status_code == 400
    assert str(inst_b.id) in exc_info.value.detail


def test_route_distance_unknown_installation_id_returns_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        calculate_route_distance(RouteDistanceRequest(installation_ids=[uuid.uuid4()]), db_session)
    assert exc_info.value.status_code == 404
