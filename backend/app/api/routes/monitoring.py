import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.device_metric import DeviceMetric
from app.models.mikrotik_device import MikrotikDevice
from app.schemas.mikrotik_device import ActivePppSession
from app.schemas.monitoring import DeviceMetricRead
from app.services.mikrotik.device_service import DeviceService

router = APIRouter(prefix="/devices", tags=["monitoring"], dependencies=[Depends(get_current_user)])


@router.get("/{device_id}/metrics", response_model=list[DeviceMetricRead])
def get_device_metrics(
    device_id: uuid.UUID,
    limit: int = Query(default=200, le=2000),
    db: Session = Depends(get_db),
) -> list[DeviceMetric]:
    device = db.get(MikrotikDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")
    return (
        db.query(DeviceMetric)
        .filter(DeviceMetric.device_id == device_id)
        .order_by(DeviceMetric.recorded_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/{device_id}/active-sessions", response_model=list[ActivePppSession])
def get_active_sessions(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[ActivePppSession]:
    device = db.get(MikrotikDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")
    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)
    try:
        return service.get_active_sessions()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo consultar sesiones activas: {exc}")
