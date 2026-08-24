from sqlalchemy.orm import Session

from app.models.billing_settings import BillingSettings


def get_billing_settings(db: Session) -> BillingSettings:
    """La migración 0014 siembra una única fila -- el fallback de acá es
    solo defensivo, no el camino normal."""
    settings = db.query(BillingSettings).first()
    if settings is None:
        settings = BillingSettings()
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings
