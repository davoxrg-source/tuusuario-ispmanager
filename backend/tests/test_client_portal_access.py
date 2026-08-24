import pytest
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.api.routes.clients import activate_client_portal, revoke_client_portal
from app.api.routes.portal_auth import login
from app.models.client import Client, ClientStatus
from app.models.notification import Notification


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def test_activate_portal_generates_password_that_logs_in(db_session):
    client = _make_client(db_session, identification="1002003000")
    assert client.portal_active is False

    result = activate_client_portal(client.id, db_session)

    db_session.refresh(client)
    assert client.portal_active is True
    token = login(OAuth2PasswordRequestForm(username="1002003000", password=result.password), db_session)
    assert token.access_token


def test_activate_portal_notifies_client_with_email_on_file(db_session):
    client = _make_client(db_session, identification="1002003099", email="cliente@compusoft-isp.com")

    activate_client_portal(client.id, db_session)

    notifications = db_session.query(Notification).filter(Notification.client_id == client.id).all()
    assert len(notifications) == 1
    assert notifications[0].event_type == "portal_activated"


def test_activate_portal_without_email_sends_no_notification(db_session):
    client = _make_client(db_session, identification="1002003098")  # sin email

    activate_client_portal(client.id, db_session)

    notifications = db_session.query(Notification).filter(Notification.client_id == client.id).all()
    assert notifications == []


def test_activate_portal_without_identification_rejected(db_session):
    client = _make_client(db_session)  # sin identification

    with pytest.raises(HTTPException) as exc_info:
        activate_client_portal(client.id, db_session)
    assert exc_info.value.status_code == 400


def test_reactivate_generates_new_password_invalidating_old_one(db_session):
    client = _make_client(db_session, identification="1002003001")
    first = activate_client_portal(client.id, db_session)
    second = activate_client_portal(client.id, db_session)

    assert first.password != second.password
    with pytest.raises(HTTPException):
        login(OAuth2PasswordRequestForm(username="1002003001", password=first.password), db_session)
    token = login(
        OAuth2PasswordRequestForm(username="1002003001", password=second.password), db_session
    )
    assert token.access_token


def test_revoke_portal_blocks_login(db_session):
    client = _make_client(db_session, identification="1002003002")
    result = activate_client_portal(client.id, db_session)

    revoke_client_portal(client.id, db_session)

    db_session.refresh(client)
    assert client.portal_active is False
    with pytest.raises(HTTPException):
        login(
            OAuth2PasswordRequestForm(username="1002003002", password=result.password), db_session
        )
