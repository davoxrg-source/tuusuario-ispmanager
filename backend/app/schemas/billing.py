import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

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


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    amount: float
    method: str
    reference: str | None = None
    paid_at: datetime
