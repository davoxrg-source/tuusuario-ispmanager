import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.client import ClientStatus
from app.models.invoice import InvoiceStatus

# Schemas propios, no los internos (ClientRead/InvoiceRead/PlanRead)
# reusados -- este es un contrato aparte para consumo externo, no debe
# filtrar campos internos (ip_address, mikrotik_device_id, zone_id) ni
# romperse porque el modelo interno le agregó una columna. Mismo criterio
# que ClientPortalRead en la Fase 5a.


class ExternalClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    identification: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    status: ClientStatus
    plan_id: uuid.UUID | None = None
    is_online: bool


class ExternalInvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    period_start: date
    period_end: date
    due_date: date
    amount: float
    status: InvoiceStatus
    paid_at: datetime | None = None
    folio: str | None = None


class ExternalPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    download_speed_mbps: int
    upload_speed_mbps: int
    price: float
    currency: str
