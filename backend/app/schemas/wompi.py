import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.wompi_transaction import WompiTransactionStatus


class CheckoutUrlRead(BaseModel):
    checkout_url: str
    reference: str


class WompiTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    reference: str
    wompi_transaction_id: str | None = None
    amount_in_cents: int
    status: WompiTransactionStatus
    created_at: datetime
    updated_at: datetime
