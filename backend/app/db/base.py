"""Importa Base y todos los modelos para que Alembic detecte el esquema completo."""

from app.db.base_class import Base
from app.models import (  # noqa: F401
    BillingSettings,
    Client,
    DeviceMetric,
    Invoice,
    MikrotikDevice,
    Payment,
    PaymentAccount,
    Plan,
    PollAttempt,
    User,
)
