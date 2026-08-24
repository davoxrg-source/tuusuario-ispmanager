import uuid

from pydantic import BaseModel, ConfigDict


class ZoneBase(BaseModel):
    name: str
    description: str | None = None


class ZoneCreate(ZoneBase):
    pass


class ZoneUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ZoneRead(ZoneBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
