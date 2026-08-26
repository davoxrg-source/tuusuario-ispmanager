import uuid
from unittest.mock import patch

from app.models.device_token import DeviceOwnerType, DeviceToken
from app.models.notification import NotificationChannel, NotificationStatus
from app.models.user import User, UserRole
from app.services.notifications.fcm_provider import PushResult as FcmResult
from app.services.notifications.service import notify_user


def _make_user(db_session, role=UserRole.TECHNICIAN) -> User:
    user = User(
        full_name="Staff Test", email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x", role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_notify_user_without_device_token_returns_empty(db_session):
    user = _make_user(db_session)

    notifications = notify_user(db_session, user, event_type="test", subject="Asunto", body="Cuerpo")

    assert notifications == []


def test_notify_user_sends_fcm_to_each_device_token(db_session):
    user = _make_user(db_session)
    token = DeviceToken(owner_type=DeviceOwnerType.USER, owner_id=user.id, fcm_token="staff-fcm-1")
    db_session.add(token)
    db_session.commit()

    with patch(
        "app.services.notifications.service.send_fcm",
        return_value=FcmResult(success=True, error=None),
    ):
        notifications = notify_user(db_session, user, event_type="test", subject="Asunto", body="Cuerpo")

    assert len(notifications) == 1
    assert notifications[0].channel == NotificationChannel.FCM
    assert notifications[0].status == NotificationStatus.SENT
    assert notifications[0].user_id == user.id
    assert notifications[0].client_id is None


def test_notify_user_deletes_expired_fcm_token(db_session):
    user = _make_user(db_session)
    token = DeviceToken(owner_type=DeviceOwnerType.USER, owner_id=user.id, fcm_token="staff-fcm-2")
    db_session.add(token)
    db_session.commit()
    token_id = token.id

    with patch(
        "app.services.notifications.service.send_fcm",
        return_value=FcmResult(success=False, error="Token expirado.", expired=True),
    ):
        notify_user(db_session, user, event_type="test", subject="Asunto", body="Cuerpo")

    assert db_session.get(DeviceToken, token_id) is None
