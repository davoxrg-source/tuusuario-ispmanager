"""Importa Base y todos los modelos para que Alembic detecte el esquema completo."""

from app.db.base_class import Base
from app.models import (  # noqa: F401
    ApiKey,
    BillingSettings,
    Client,
    Contract,
    ContractTemplate,
    DeviceMetric,
    Installation,
    Invoice,
    InventoryItem,
    InventoryMovement,
    MikrotikDevice,
    Notification,
    Payment,
    PaymentAccount,
    PaymentReport,
    Plan,
    PollAttempt,
    PushSubscription,
    Supplier,
    User,
    WompiTransaction,
    Zone,
)
