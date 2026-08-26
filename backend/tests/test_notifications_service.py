import uuid
from unittest.mock import patch

from app.models.client import Client, ClientStatus
from app.models.device_token import DeviceOwnerType, DeviceToken
from app.models.notification import NotificationChannel, NotificationStatus
from app.models.push_subscription import PushSubscription
from app.services.notifications.fcm_provider import PushResult as FcmResult
from app.services.notifications.push_provider import PushResult
from app.services.notifications.service import notify_client


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def test_notify_client_without_smtp_configured_logs_failure(db_session):
    client = _make_client(db_session, email="cliente@compusoft-isp.com")

    notifications = notify_client(db_session, client, event_type="test", subject="Asunto", body="Cuerpo")

    assert len(notifications) == 1
    assert notifications[0].channel == NotificationChannel.EMAIL
    assert notifications[0].status == NotificationStatus.FAILED
    assert "SMTP" in notifications[0].error_message


def test_notify_client_with_email_provider_success_is_recorded(db_session):
    client = _make_client(db_session, email="cliente@compusoft-isp.com")

    with patch("app.services.notifications.service.send_email", return_value=(True, None)):
        notifications = notify_client(db_session, client, event_type="test", subject="Asunto", body="Cuerpo")

    assert notifications[0].status == NotificationStatus.SENT
    assert notifications[0].recipient == "cliente@compusoft-isp.com"
    assert notifications[0].sent_at is not None


def test_notify_client_without_email_skips_email_channel(db_session):
    client = _make_client(db_session)  # sin email

    notifications = notify_client(db_session, client, event_type="test", subject="Asunto", body="Cuerpo")

    assert notifications == []


def test_notify_client_sends_push_to_each_subscription(db_session):
    client = _make_client(db_session)
    sub = PushSubscription(client_id=client.id, endpoint="https://push.example/1", p256dh="k", auth="a")
    db_session.add(sub)
    db_session.commit()

    with patch(
        "app.services.notifications.service.send_push",
        return_value=PushResult(success=True, error=None),
    ):
        notifications = notify_client(db_session, client, event_type="test", subject="Asunto", body="Cuerpo")

    assert len(notifications) == 1
    assert notifications[0].channel == NotificationChannel.PUSH
    assert notifications[0].status == NotificationStatus.SENT


def test_notify_client_deletes_expired_push_subscription(db_session):
    client = _make_client(db_session)
    sub = PushSubscription(client_id=client.id, endpoint="https://push.example/2", p256dh="k", auth="a")
    db_session.add(sub)
    db_session.commit()
    sub_id = sub.id

    with patch(
        "app.services.notifications.service.send_push",
        return_value=PushResult(success=False, error="Suscripción expirada.", expired=True),
    ):
        notifications = notify_client(db_session, client, event_type="test", subject="Asunto", body="Cuerpo")

    assert notifications[0].status == NotificationStatus.FAILED
    assert db_session.get(PushSubscription, sub_id) is None


def test_notify_client_sends_fcm_to_each_device_token(db_session):
    client = _make_client(db_session)
    token = DeviceToken(owner_type=DeviceOwnerType.CLIENT, owner_id=client.id, fcm_token="fcm-1")
    db_session.add(token)
    db_session.commit()

    with patch(
        "app.services.notifications.service.send_fcm",
        return_value=FcmResult(success=True, error=None),
    ):
        notifications = notify_client(db_session, client, event_type="test", subject="Asunto", body="Cuerpo")

    assert len(notifications) == 1
    assert notifications[0].channel == NotificationChannel.FCM
    assert notifications[0].status == NotificationStatus.SENT
    assert notifications[0].client_id == client.id


def test_notify_client_deletes_expired_fcm_token(db_session):
    client = _make_client(db_session)
    token = DeviceToken(owner_type=DeviceOwnerType.CLIENT, owner_id=client.id, fcm_token="fcm-2")
    db_session.add(token)
    db_session.commit()
    token_id = token.id

    with patch(
        "app.services.notifications.service.send_fcm",
        return_value=FcmResult(success=False, error="Token expirado.", expired=True),
    ):
        notify_client(db_session, client, event_type="test", subject="Asunto", body="Cuerpo")

    assert db_session.get(DeviceToken, token_id) is None


def test_notify_client_only_notifies_own_device_tokens(db_session):
    client_a = _make_client(db_session)
    client_b = _make_client(db_session)
    db_session.add(DeviceToken(owner_type=DeviceOwnerType.CLIENT, owner_id=client_b.id, fcm_token="fcm-b"))
    db_session.commit()

    notifications = notify_client(db_session, client_a, event_type="test", subject="Asunto", body="Cuerpo")

    assert notifications == []
