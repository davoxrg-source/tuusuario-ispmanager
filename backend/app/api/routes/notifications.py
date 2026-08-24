import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.notification import Notification, NotificationChannel, NotificationStatus
from app.schemas.notification import NotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(get_current_user)])


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
