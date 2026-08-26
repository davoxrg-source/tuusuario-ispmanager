import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.device_token import DeviceOwnerType, DeviceToken
from app.models.notification import Notification, NotificationChannel, NotificationStatus
from app.models.user import User
from app.schemas.notification import DeviceTokenCreate, NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(get_current_user)])

# Router separado (sin prefijo /notifications): device-tokens es su propio
# recurso, mismo criterio que /hotspot-vouchers no anida bajo nada.
device_tokens_router = APIRouter(
    prefix="/device-tokens", tags=["notifications"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    client_id: uuid.UUID | None = None,
    status_filter: NotificationStatus | None = None,
    channel: NotificationChannel | None = None,
    db: Session = Depends(get_db),
) -> list[Notification]:
    query = db.query(Notification)
    if client_id is not None:
        query = query.filter(Notification.client_id == client_id)
    if status_filter is not None:
        query = query.filter(Notification.status == status_filter)
    if channel is not None:
        query = query.filter(Notification.channel == channel)
    return query.order_by(Notification.created_at.desc()).limit(200).all()


@device_tokens_router.post("", status_code=204)
def create_device_token(
    payload: DeviceTokenCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Token FCM de la app móvil de staff -- equivalente al de
    POST /portal/device-tokens pero para User en vez de Client."""
    existing = db.query(DeviceToken).filter(DeviceToken.fcm_token == payload.fcm_token).first()
    if existing:
        existing.owner_type = DeviceOwnerType.USER
        existing.owner_id = current_user.id
        existing.platform = payload.platform
    else:
        db.add(
            DeviceToken(
                owner_type=DeviceOwnerType.USER,
                owner_id=current_user.id,
                fcm_token=payload.fcm_token,
                platform=payload.platform,
            )
        )
    db.commit()


@device_tokens_router.delete("", status_code=204)
def delete_device_token(
    fcm_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    db.query(DeviceToken).filter(
        DeviceToken.fcm_token == fcm_token,
        DeviceToken.owner_type == DeviceOwnerType.USER,
        DeviceToken.owner_id == current_user.id,
    ).delete()
    db.commit()
