import uuid

from pydantic import BaseModel


class BulkActionResultItem(BaseModel):
    id: uuid.UUID
    ok: bool
    detail: str | None = None


class BulkActionResult(BaseModel):
    results: list[BulkActionResultItem]
