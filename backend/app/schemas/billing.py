import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.billing_settings import ProrationTarget, ReconnectionFeeMode
from app.models.invoice import InvoiceStatus


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    period_start: date
    period_end: date
    due_date: date
    amount: float
    status: InvoiceStatus
    paid_at: datetime | None = None
    promise_to_pay_until: date | None = None
    late_fee_amount: float = 0
    late_fee_applied_at: datetime | None = None
    folio: str | None = None


class InvoiceCreate(BaseModel):
    client_id: uuid.UUID
    period_start: date
    period_end: date
    due_date: date
    amount: float


class PromiseToPayCreate(BaseModel):
    until: date


class PaymentCreate(BaseModel):
    amount: float
    method: str
    reference: str | None = None
    payment_account_id: uuid.UUID | None = None


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: float
    method: str
    reference: str | None = None
    payment_account_id: uuid.UUID | None = None
    paid_at: datetime


class PaymentAccountCreate(BaseModel):
    name: str
    kind: str = "other"


class PaymentAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: str
    is_active: bool


class AccountBalanceRead(BaseModel):
    id: uuid.UUID
    name: str
    kind: str
    total: float


class BulkInvoiceCharge(BaseModel):
    invoice_ids: list[uuid.UUID]
    amount: float = Field(gt=0)


class BillingSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generate_invoice_days_before_due: int
    suspend_days_after_due: int
    proration_enabled: bool
    proration_min_days: int
    proration_target: ProrationTarget
    late_fee_enabled: bool
    late_fee_amount: float
    late_fee_apply_hour: int
    reconnection_fee_mode: ReconnectionFeeMode
    reconnection_fee_amount: float
    invoice_folio_prefix: str
    invoice_folio_next_number: int
    payment_reminder_enabled: bool
    payment_reminder_days_before_due: int


class BillingSettingsUpdate(BaseModel):
    generate_invoice_days_before_due: int | None = None
    suspend_days_after_due: int | None = None
    proration_enabled: bool | None = None
    proration_min_days: int | None = None
    proration_target: ProrationTarget | None = None
    late_fee_enabled: bool | None = None
    late_fee_amount: float | None = None
    late_fee_apply_hour: int | None = None
    reconnection_fee_mode: ReconnectionFeeMode | None = None
    reconnection_fee_amount: float | None = None
    invoice_folio_prefix: str | None = None
    invoice_folio_next_number: int | None = None
    payment_reminder_enabled: bool | None = None
    payment_reminder_days_before_due: int | None = None
