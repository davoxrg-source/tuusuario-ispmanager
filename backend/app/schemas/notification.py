import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationChannel, NotificationStatus


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    channel: NotificationChannel
    event_type: str
    recipient: str
    subject: str
    status: NotificationStatus
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime


class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    """Calca la forma de PushSubscription.toJSON() del navegador."""

    endpoint: str
    keys: PushSubscriptionKeys


class VapidPublicKeyRead(BaseModel):
    public_key: str


class DeviceTokenCreate(BaseModel):
    """Token FCM que manda una app móvil nativa al activar notificaciones."""

    fcm_token: str
    platform: str = "android"
