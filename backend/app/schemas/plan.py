import uuid

from pydantic import BaseModel, ConfigDict


class PlanBase(BaseModel):
    name: str
    download_speed_mbps: int
    upload_speed_mbps: int
    price: float
    currency: str = "USD"
    guaranteed_floor_percent: int = 9


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    name: str | None = None
    download_speed_mbps: int | None = None
    upload_speed_mbps: int | None = None
    price: float | None = None
    currency: str | None = None
    guaranteed_floor_percent: int | None = None


class PlanRead(PlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
