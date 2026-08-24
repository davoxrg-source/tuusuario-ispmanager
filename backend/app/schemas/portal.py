import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.client import ClientStatus
from app.models.payment_report import PaymentReportStatus


class ClientPortalRead(BaseModel):
    """Subconjunto de Client para el propio cliente -- sin ip_address,
    mikrotik_device_id ni legacy_contract_id (control exclusivo de staff)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    identification: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    plan_id: uuid.UUID | None = None
    status: ClientStatus
    is_online: bool
    last_seen_at: datetime | None = None
    pending_credit: float
    pending_reconnection_fee: bool


class ClientPortalProfileUpdate(BaseModel):
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class PaymentReportCreate(BaseModel):
    invoice_id: uuid.UUID
    amount: float
    method: str
    reference: str | None = None
    note: str | None = None


class PaymentReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    client_id: uuid.UUID
    amount: float
    method: str
    reference: str | None = None
    note: str | None = None
    status: PaymentReportStatus
    reported_at: datetime
    reviewed_by_user_id: uuid.UUID | None = None
    reviewed_at: datetime | None = None
