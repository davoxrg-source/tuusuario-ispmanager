import uuid

from app.api.routes.notifications import create_device_token as staff_create_device_token
from app.api.routes.notifications import delete_device_token as staff_delete_device_token
from app.api.routes.portal import create_device_token, delete_device_token
from app.models.client import Client, ClientStatus
from app.models.device_token import DeviceOwnerType, DeviceToken
from app.models.user import User, UserRole
from app.schemas.notification import DeviceTokenCreate


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def _make_user(db_session, role=UserRole.TECHNICIAN) -> User:
    user = User(
        full_name="Staff Test", email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x", role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_client_create_device_token_persists_it(db_session):
    client = _make_client(db_session)

    create_device_token(DeviceTokenCreate(fcm_token="tok-abc"), db_session, client)

    tokens = db_session.query(DeviceToken).filter(DeviceToken.owner_id == client.id).all()
    assert len(tokens) == 1
    assert tokens[0].owner_type == DeviceOwnerType.CLIENT
    assert tokens[0].fcm_token == "tok-abc"
    assert tokens[0].platform == "android"


def test_client_create_device_token_upserts_by_token(db_session):
    client_a = _make_client(db_session)
    client_b = _make_client(db_session)

    create_device_token(DeviceTokenCreate(fcm_token="shared-tok"), db_session, client_a)
    create_device_token(DeviceTokenCreate(fcm_token="shared-tok"), db_session, client_b)

    tokens = db_session.query(DeviceToken).filter(DeviceToken.fcm_token == "shared-tok").all()
    assert len(tokens) == 1
    assert tokens[0].owner_id == client_b.id


def test_client_delete_device_token_scoped_to_own_client(db_session):
    client_a = _make_client(db_session)
    client_b = _make_client(db_session)
    create_device_token(DeviceTokenCreate(fcm_token="tok-x"), db_session, client_a)

    delete_device_token("tok-x", db_session, client_b)

    assert db_session.query(DeviceToken).filter(DeviceToken.owner_id == client_a.id).count() == 1


def test_client_delete_device_token_own_removes_it(db_session):
    client = _make_client(db_session)
    create_device_token(DeviceTokenCreate(fcm_token="tok-y"), db_session, client)

    delete_device_token("tok-y", db_session, client)

    assert db_session.query(DeviceToken).filter(DeviceToken.owner_id == client.id).count() == 0


def test_staff_create_device_token_persists_it(db_session):
    user = _make_user(db_session)

    staff_create_device_token(DeviceTokenCreate(fcm_token="staff-tok"), db_session, user)

    tokens = db_session.query(DeviceToken).filter(DeviceToken.owner_id == user.id).all()
    assert len(tokens) == 1
    assert tokens[0].owner_type == DeviceOwnerType.USER


def test_staff_and_client_tokens_do_not_collide_on_owner_id_reuse(db_session):
    # No hay FK real -- un client_id y un user_id distintos pero con el
    # mismo valor UUID (imposible en la práctica, pero vale probar que el
    # filtro por owner_type los distingue igual) no deberían mezclarse.
    client = _make_client(db_session)
    create_device_token(DeviceTokenCreate(fcm_token="tok-client-only"), db_session, client)

    staff_tokens = (
        db_session.query(DeviceToken)
        .filter(DeviceToken.owner_type == DeviceOwnerType.USER, DeviceToken.owner_id == client.id)
        .all()
    )
    assert staff_tokens == []
