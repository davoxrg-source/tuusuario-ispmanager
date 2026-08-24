from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.billing_settings import BillingSettings
from app.schemas.billing import BillingSettingsRead, BillingSettingsUpdate
from app.services.billing.settings import get_billing_settings

router = APIRouter(
    prefix="/billing-settings", tags=["billing"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=BillingSettingsRead)
def read_billing_settings(db: Session = Depends(get_db)) -> BillingSettings:
    return get_billing_settings(db)


@router.patch("", response_model=BillingSettingsRead, dependencies=[Depends(require_admin)])
def update_billing_settings(
    payload: BillingSettingsUpdate, db: Session = Depends(get_db)
) -> BillingSettings:
    settings = get_billing_settings(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
