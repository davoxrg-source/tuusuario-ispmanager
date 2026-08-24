import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.ticket import TicketCategory, TicketPriority, TicketStatus


class TicketReplyCreate(BaseModel):
    body: str


class TicketReplyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    author_user_id: uuid.UUID | None
    author_client_id: uuid.UUID | None
    body: str
    created_at: datetime


class TicketCreate(BaseModel):
    client_id: uuid.UUID | None = None
    subject: str
    description: str
    priority: TicketPriority = TicketPriority.MEDIUM
    category: TicketCategory = TicketCategory.OTHER
    assigned_to_user_id: uuid.UUID | None = None


class TicketUpdate(BaseModel):
    subject: str | None = None
    description: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    category: TicketCategory | None = None
    assigned_to_user_id: uuid.UUID | None = None


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    created_by_client_id: uuid.UUID | None
    assigned_to_user_id: uuid.UUID | None
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    created_at: datetime
    updated_at: datetime


class TicketMeta(BaseModel):
    statuses: list[str]
    priorities: list[str]
    categories: list[str]
