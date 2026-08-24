from app.models.billing_settings import BillingSettings
from app.services.billing.settings import get_billing_settings


def test_get_billing_settings_returns_seeded_row(db_session):
    settings = get_billing_settings(db_session)
    assert settings is not None
    assert isinstance(settings, BillingSettings)


def test_get_billing_settings_creates_row_if_missing(db_session):
    existing = db_session.query(BillingSettings).first()
    db_session.delete(existing)
    db_session.commit()
    assert db_session.query(BillingSettings).first() is None

    settings = get_billing_settings(db_session)

    assert settings is not None
    assert db_session.query(BillingSettings).count() == 1
