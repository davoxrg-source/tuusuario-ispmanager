from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.notification import Notification, NotificationChannel, NotificationStatus
from app.services.notifications.email_provider import send_email
from app.services.notifications.push_provider import send_push


def notify_client(db: Session, client: Client, *, event_type: str, subject: str, body: str) -> list[Notification]:
    """Único punto de entrada para avisarle algo a un cliente -- intenta
    correo (si tiene email cargado) y push (una vez por cada suscripción
    activa), cada intento genera su propia fila de Notification (éxito o
    fracaso, nunca se pierde silencioso). Una suscripción push expirada se
    borra sola."""
    notifications: list[Notification] = []

    if client.email:
        sent, error = send_email(client.email, subject, body)
        notifications.append(
            _record(db, client, NotificationChannel.EMAIL, event_type, client.email, subject, body, sent, error)
        )

    for subscription in list(client.push_subscriptions):
        result = send_push(subscription, subject, body)
        notifications.append(
            _record(
                db,
                client,
                NotificationChannel.PUSH,
                event_type,
                subscription.endpoint,
                subject,
                body,
                result.success,
                result.error,
            )
        )
        if result.expired:
            db.delete(subscription)
            db.commit()

    return notifications


def _record(
    db: Session,
    client: Client,
    channel: NotificationChannel,
    event_type: str,
    recipient: str,
    subject: str,
    body: str,
    sent: bool,
    error: str | None,
) -> Notification:
    notification = Notification(
        client_id=client.id,
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
