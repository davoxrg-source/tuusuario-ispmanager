import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.contract import ContractStatus


class ContractTemplateCreate(BaseModel):
    name: str
    body: str


class ContractTemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None


class ContractTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    body: str


class ContractCreate(BaseModel):
    client_id: uuid.UUID
    template_id: uuid.UUID


class ContractUpdate(BaseModel):
    rendered_body: str


class ContractSignRequest(BaseModel):
    signer_name: str
    signer_identification: str | None = None
    # PNG en base64 (data URI) dibujado en el SignaturePad del frontend.
    signature_image: str


class ContractRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    rendered_body: str
    status: ContractStatus
    signer_name: str | None = None
    signer_identification: str | None = None
    signature_image: str | None = None
    signed_at: datetime | None = None
    signer_ip: str | None = None
    witnessed_by_user_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID
    created_at: datetime
