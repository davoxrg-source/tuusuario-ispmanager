import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.inventory import MovementReason


class SupplierCreate(BaseModel):
    name: str
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class SupplierUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None = None
    email: str | None = None
    notes: str | None = None


class InventoryItemCreate(BaseModel):
    name: str
    category: str = "otro"
    unit_cost: float | None = None
    supplier_id: uuid.UUID | None = None
    notes: str | None = None


class InventoryItemUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    unit_cost: float | None = None
    supplier_id: uuid.UUID | None = None
    notes: str | None = None


class InventoryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    quantity: int
    unit_cost: float | None = None
    supplier_id: uuid.UUID | None = None
    notes: str | None = None


class InventoryMovementCreate(BaseModel):
    item_id: uuid.UUID
    reason: MovementReason
    quantity_delta: int
    assigned_to_user_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    note: str | None = None


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    reason: MovementReason
    quantity_delta: int
    assigned_to_user_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    note: str | None = None
    created_by_user_id: uuid.UUID
    created_at: datetime


class TechnicianBalanceRead(BaseModel):
    user_id: uuid.UUID
    user_name: str
    item_id: uuid.UUID
    item_name: str
    balance: int
