import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.hotspot import HotspotVoucherStatus


class HotspotProfileCreate(BaseModel):
    name: str
    duration_hours: int | None = None
    data_limit_mb: int | None = None
    price: float
    currency: str = "USD"


class HotspotProfileUpdate(BaseModel):
    name: str | None = None
    duration_hours: int | None = None
    data_limit_mb: int | None = None
    price: float | None = None
    currency: str | None = None


class HotspotProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    duration_hours: int | None = None
    data_limit_mb: int | None = None
    price: float
    currency: str


class HotspotVoucherBatchCreate(BaseModel):
    profile_id: uuid.UUID
    quantity: int


class HotspotVoucherRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    profile_id: uuid.UUID
    code: str
    price: float
    status: HotspotVoucherStatus
    batch_id: uuid.UUID
    sold_at: datetime | None = None
    sold_by_user_id: uuid.UUID | None = None
    voided_at: datetime | None = None
    created_at: datetime
