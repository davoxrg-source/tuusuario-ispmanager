import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_id: uuid.UUID
    recorded_at: datetime
    cpu_load_percent: int | None = None
    memory_used_bytes: int | None = None
    memory_total_bytes: int | None = None
    uptime_seconds: int | None = None
    active_ppp_sessions: int | None = None
    interfaces: dict | None = None
