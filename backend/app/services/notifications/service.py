from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.device_token import DeviceOwnerType, DeviceToken
from app.models.notification import Notification, NotificationChannel, NotificationStatus
from app.models.user import User
from app.services.notifications.email_provider import send_email
from app.services.notifications.fcm_provider import send_fcm
from app.services.notifications.push_provider import send_push


def notify_client(db: Session, client: Client, *, event_type: str, subject: str, body: str) -> list[Notification]:
    """Único punto de entrada para avisarle algo a un cliente -- intenta
    correo (si tiene email cargado), Web Push (una vez por cada suscripción
    activa del navegador) y FCM (una vez por cada token de la app móvil),
    cada intento genera su propia fila de Notification (éxito o fracaso,
    nunca se pierde silencioso). Una suscripción/token expirado se borra solo."""
    notifications: list[Notification] = []

    if client.email:
        sent, error = send_email(client.email, subject, body)
        notifications.append(
            _record(
                db, NotificationChannel.EMAIL, event_type, client.email, subject, body, sent, error,
                client_id=client.id,
            )
        )

    for subscription in list(client.push_subscriptions):
        result = send_push(subscription, subject, body)
        notifications.append(
            _record(
                db, NotificationChannel.PUSH, event_type, subscription.endpoint, subject, body,
                result.success, result.error, client_id=client.id,
            )
        )
        if result.expired:
            db.delete(subscription)
            db.commit()

    for device_token in _device_tokens(db, DeviceOwnerType.CLIENT, client.id):
        result = send_fcm(device_token.fcm_token, subject, body)
        notifications.append(
            _record(
                db, NotificationChannel.FCM, event_type, device_token.fcm_token, subject, body,
                result.success, result.error, client_id=client.id,
            )
        )
        if result.expired:
            db.delete(device_token)
            db.commit()

    return notifications


def notify_user(db: Session, user: User, *, event_type: str, subject: str, body: str) -> list[Notification]:
    """Equivalente a notify_client() pero para el staff -- hoy solo por FCM
    (la app móvil de técnicos), ya que no hay ningún flujo de correo/Web
    Push dirigido a User todavía. Cierra un gap real: antes de esto no
    existía ninguna notificación al personal (ej. "te asignaron una
    instalación nueva")."""
    notifications: list[Notification] = []

    for device_token in _device_tokens(db, DeviceOwnerType.USER, user.id):
        result = send_fcm(device_token.fcm_token, subject, body)
        notifications.append(
            _record(
                db, NotificationChannel.FCM, event_type, device_token.fcm_token, subject, body,
                result.success, result.error, user_id=user.id,
            )
        )
        if result.expired:
            db.delete(device_token)
            db.commit()

    return notifications


def _device_tokens(db: Session, owner_type: DeviceOwnerType, owner_id) -> list[DeviceToken]:
    return (
        db.query(DeviceToken)
        .filter(DeviceToken.owner_type == owner_type, DeviceToken.owner_id == owner_id)
        .all()
    )


def _record(
    db: Session,
    channel: NotificationChannel,
    event_type: str,
    recipient: str,
    subject: str,
    body: str,
    sent: bool,
    error: str | None,
    *,
    client_id=None,
    user_id=None,
) -> Notification:
    notification = Notification(
        client_id=client_id,
        user_id=user_id,
        channel=channel,
        event_type=event_type,
        recipient=recipient,
        subject=subject,
        body=body,
        status=NotificationStatus.SENT if sent else NotificationStatus.FAILED,
        error_message=error,
        sent_at=datetime.now(timezone.utc) if sent else None,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification
