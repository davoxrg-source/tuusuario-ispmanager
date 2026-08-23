import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TrafficUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: uuid.UUID
    bucket_start: datetime
    bytes_in: int
    bytes_out: int
    packets_in: int
    packets_out: int
