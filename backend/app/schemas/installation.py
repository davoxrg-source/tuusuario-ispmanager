import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.installation import InstallationStatus


class InstallationCreate(BaseModel):
    client_id: uuid.UUID
    assigned_technician_id: uuid.UUID | None = None
    scheduled_date: date
    status: InstallationStatus = InstallationStatus.SCHEDULED
    notes: str | None = None


class InstallationUpdate(BaseModel):
    client_id: uuid.UUID | None = None
    assigned_technician_id: uuid.UUID | None = None
    scheduled_date: date | None = None
    status: InstallationStatus | None = None
    notes: str | None = None


class InstallationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    assigned_technician_id: uuid.UUID | None = None
    scheduled_date: date
    status: InstallationStatus
    notes: str | None = None
    created_at: datetime


class RouteDistanceRequest(BaseModel):
    installation_ids: list[uuid.UUID]


class RouteLeg(BaseModel):
    from_id: uuid.UUID
    to_id: uuid.UUID
    km: float


class RouteDistanceRead(BaseModel):
    total_km: float
    legs: list[RouteLeg]
