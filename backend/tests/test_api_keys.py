import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_current_api_key
from app.api.routes.api_keys import create_api_key, list_api_keys, revoke_api_key
from app.models.user import User, UserRole
from app.schemas.api_key import ApiKeyCreate


def _make_admin(db_session) -> User:
    admin = User(
        full_name="Admin", email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x", role=UserRole.ADMIN
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_create_api_key_returns_plaintext_once_and_it_authenticates(db_session):
    admin = _make_admin(db_session)

    result = create_api_key(ApiKeyCreate(name="Contabilidad externa"), db_session, admin)

    assert result.key.startswith("isp_live_")
    assert result.key_prefix == result.key[:12]

    resolved = get_current_api_key(_creds(result.key), db_session)
    assert resolved.id == result.id
    assert resolved.last_used_at is not None


def test_list_api_keys_never_exposes_the_real_key(db_session):
    admin = _make_admin(db_session)
    create_api_key(ApiKeyCreate(name="Test"), db_session, admin)

    keys = list_api_keys(db_session)

    assert len(keys) == 1
    assert not hasattr(keys[0], "key")  # ApiKeyRead no tiene ese campo, a diferencia de ApiKeyCreateResult


def test_revoked_api_key_cannot_authenticate(db_session):
    admin = _make_admin(db_session)
    result = create_api_key(ApiKeyCreate(name="Test"), db_session, admin)

    revoke_api_key(result.id, db_session)

    with pytest.raises(HTTPException) as exc_info:
        get_current_api_key(_creds(result.key), db_session)
    assert exc_info.value.status_code == 401


def test_get_current_api_key_rejects_unknown_token(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_current_api_key(_creds("isp_live_esto-no-existe"), db_session)
    assert exc_info.value.status_code == 401


def test_get_current_api_key_rejects_missing_credentials(db_session):
    with pytest.raises(HTTPException) as exc_info:
        get_current_api_key(None, db_session)
    assert exc_info.value.status_code == 401
