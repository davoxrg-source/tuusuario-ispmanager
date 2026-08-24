import json
import logging
from dataclasses import dataclass

from pywebpush import WebPushException, webpush

from app.core.config import get_settings
from app.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


@dataclass
class PushResult:
    success: bool
    error: str | None
    # Una suscripción "expirada" (404/410 -- el navegador la revocó) no
    # tiene sentido reintentarla: el llamador la borra en vez de dejarla
    # fallando para siempre en cada intento futuro.
    expired: bool = False


def send_push(subscription: PushSubscription, title: str, body: str) -> PushResult:
    settings = get_settings()
    if not settings.vapid_public_key or not settings.vapid_private_key:
        return PushResult(success=False, error="VAPID no configurado.")

    subscription_info = {
        "endpoint": subscription.endpoint,
        "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
    }
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
        return PushResult(success=True, error=None)
    except WebPushException as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        if status_code in (404, 410):
            return PushResult(success=False, error="Suscripción expirada.", expired=True)
        logger.warning("No se pudo mandar push a %s: %s", subscription.endpoint, exc)
        return PushResult(success=False, error=str(exc)[:2000])
