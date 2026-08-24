import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_current_client
from app.api.routes.portal_auth import change_password, login
from app.core.security import create_access_token, hash_password
from app.models.client import Client, ClientStatus
from app.schemas.portal import ChangePasswordRequest


def _make_client(db_session, **overrides) -> Client:
    client = Client(
        full_name="Cliente Portal",
        identification=str(uuid.uuid4())[:8],
        status=ClientStatus.ACTIVE,
        ip_address=None,
    )
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def test_login_success(db_session):
    client = _make_client(db_session, hashed_password=hash_password("segura123"))

    token = login(
        OAuth2PasswordRequestForm(username=client.identification, password="segura123"), db_session
    )

    assert token.access_token
    assert token.token_type == "bearer"


def test_login_wrong_password_rejected(db_session):
    client = _make_client(db_session, hashed_password=hash_password("segura123"))

    with pytest.raises(HTTPException) as exc_info:
        login(OAuth2PasswordRequestForm(username=client.identification, password="incorrecta"), db_session)
    assert exc_info.value.status_code == 401


def test_login_without_portal_activated_rejected(db_session):
    client = _make_client(db_session)  # hashed_password=None

    with pytest.raises(HTTPException) as exc_info:
        login(OAuth2PasswordRequestForm(username=client.identification, password="cualquiera"), db_session)
    assert exc_info.value.status_code == 401


def test_login_suspended_client_still_allowed(db_session):
    # Un cliente suspendido tiene que poder entrar a ver su saldo y reportar
    # el pago para reactivarse -- no se bloquea el login por estado.
    client = _make_client(
        db_session, hashed_password=hash_password("segura123"), status=ClientStatus.SUSPENDED
    )

    token = login(
        OAuth2PasswordRequestForm(username=client.identification, password="segura123"), db_session
    )
    assert token.access_token


def test_get_current_client_valid_token(db_session):
    client = _make_client(db_session, hashed_password=hash_password("segura123"))
    token = create_access_token(subject=str(client.id))

    resolved = get_current_client(token, db_session)

    assert resolved.id == client.id


def test_get_current_client_rejects_token_for_client_without_portal(db_session):
    client = _make_client(db_session)  # nunca se activó el portal
    token = create_access_token(subject=str(client.id))

    with pytest.raises(HTTPException) as exc_info:
        get_current_client(token, db_session)
    assert exc_info.value.status_code == 401


def test_change_password_updates_hash_and_allows_relogin(db_session):
    client = _make_client(db_session, hashed_password=hash_password("vieja123"))

    change_password(
        ChangePasswordRequest(current_password="vieja123", new_password="nueva456"), client, db_session
    )

    token = login(OAuth2PasswordRequestForm(username=client.identification, password="nueva456"), db_session)
    assert token.access_token
    with pytest.raises(HTTPException):
        login(OAuth2PasswordRequestForm(username=client.identification, password="vieja123"), db_session)


def test_change_password_wrong_current_rejected(db_session):
    client = _make_client(db_session, hashed_password=hash_password("vieja123"))

    with pytest.raises(HTTPException) as exc_info:
        change_password(
            ChangePasswordRequest(current_password="incorrecta", new_password="nueva456"),
            client,
            db_session,
        )
    assert exc_info.value.status_code == 400
