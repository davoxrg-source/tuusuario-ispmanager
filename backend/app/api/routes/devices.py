import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import ensure_zone_access, get_current_user, require_admin, zone_scope_filter_ids
from app.core.security import decrypt_secret, encrypt_secret
from app.db.session import get_db
from app.models.mikrotik_device import DeviceStatus, MikrotikDevice
from app.models.user import User
from app.schemas.mikrotik_device import (
    ConnectionTestResult,
    DeviceResourceStatus,
    DiscoveredDeviceRead,
    MikrotikDeviceCreate,
    MikrotikDeviceRead,
    MikrotikDeviceUpdate,
    ResetConfigurationRequest,
)
from app.services.mikrotik import discovery
from app.services.mikrotik.device_service import DeviceService

router = APIRouter(prefix="/devices", tags=["devices"], dependencies=[Depends(get_current_user)])


def _get_device_or_404(db: Session, device_id: uuid.UUID) -> MikrotikDevice:
    device = db.get(MikrotikDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")
    return device


@router.get("", response_model=list[MikrotikDeviceRead])
def list_devices(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[MikrotikDevice]:
    query = db.query(MikrotikDevice)
    zone_ids = zone_scope_filter_ids(current_user)
    if zone_ids is not None:
        query = query.filter(MikrotikDevice.zone_id.in_(zone_ids))
    return query.order_by(MikrotikDevice.name).all()


@router.get("/discovered", response_model=list[DiscoveredDeviceRead])
def list_discovered_devices() -> list[DiscoveredDeviceRead]:
    """Equipos Mikrotik vistos en la red local vía MNDP en los últimos segundos.

    Requiere que este servidor esté en el mismo segmento L2 que los equipos;
    si no aparece nada, revisa que /ip neighbor discovery-settings esté
    habilitado en el router y que no haya un firewall bloqueando el broadcast.
    """
    return [
        DiscoveredDeviceRead(
            mac_address=d.mac_address,
            ip_address=d.ip_address,
            identity=d.identity,
            version=d.version,
            platform=d.platform,
            seen_seconds_ago=round(time.time() - d.seen_at, 1),
        )
        for d in discovery.listener.list_discovered()
    ]


@router.post("", response_model=MikrotikDeviceRead, status_code=201, dependencies=[Depends(require_admin)])
def create_device(payload: MikrotikDeviceCreate, db: Session = Depends(get_db)) -> MikrotikDevice:
    data = payload.model_dump(exclude={"password"})
    device = MikrotikDevice(**data, encrypted_password=encrypt_secret(payload.password))
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("/{device_id}", response_model=MikrotikDeviceRead)
def get_device(
    device_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> MikrotikDevice:
    device = _get_device_or_404(db, device_id)
    ensure_zone_access(current_user, device.zone_id, "Dispositivo no encontrado.")
    return device


@router.patch("/{device_id}", response_model=MikrotikDeviceRead, dependencies=[Depends(require_admin)])
def update_device(
    device_id: uuid.UUID, payload: MikrotikDeviceUpdate, db: Session = Depends(get_db)
) -> MikrotikDevice:
    device = _get_device_or_404(db, device_id)
    data = payload.model_dump(exclude_unset=True)
    password = data.pop("password", None)
    for field, value in data.items():
        setattr(device, field, value)
    if password:
        device.encrypted_password = encrypt_secret(password)
    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_device(device_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    device = _get_device_or_404(db, device_id)
    db.delete(device)
    db.commit()


@router.post("/{device_id}/test-connection", response_model=ConnectionTestResult)
def test_connection(device_id: uuid.UUID, db: Session = Depends(get_db)) -> ConnectionTestResult:
    device = _get_device_or_404(db, device_id)
    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)
    result = service.test_connection(db=db)

    device.status = DeviceStatus.ONLINE if result.success else DeviceStatus.OFFLINE
    device.last_seen_at = func.now() if result.success else device.last_seen_at
    if result.routeros_version:
        device.routeros_version = result.routeros_version
    db.commit()
    return result


@router.get("/{device_id}/status", response_model=DeviceResourceStatus)
def get_device_status(device_id: uuid.UUID, db: Session = Depends(get_db)) -> DeviceResourceStatus:
    device = _get_device_or_404(db, device_id)
    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)
    try:
        return service.get_status()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo obtener el estado del equipo: {exc}")


@router.post("/{device_id}/reboot", status_code=202, dependencies=[Depends(require_admin)])
def reboot_device(device_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    device = _get_device_or_404(db, device_id)
    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)
    try:
        service.reboot()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo reiniciar el equipo: {exc}")
    return {"detail": "Reinicio enviado."}


@router.post(
    "/{device_id}/reset-to-defaults", status_code=202, dependencies=[Depends(require_admin)]
)
def reset_device_to_defaults(
    device_id: uuid.UUID, payload: ResetConfigurationRequest, db: Session = Depends(get_db)
) -> dict:
    """ACCIÓN DESTRUCTIVA: borra toda la configuración del equipo y lo reinicia.

    Exige repetir el nombre exacto del equipo en `confirm_name` como
    confirmación explícita — no basta un simple `true/false`.
    """
    device = _get_device_or_404(db, device_id)
    if payload.confirm_name != device.name:
        raise HTTPException(
            status_code=400,
            detail="El nombre de confirmación no coincide con el nombre del equipo.",
        )

    password = decrypt_secret(device.encrypted_password)
    service = DeviceService(device, password)
    try:
        service.reset_to_factory_defaults(no_defaults=payload.no_defaults)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo restablecer el equipo: {exc}")

    device.status = DeviceStatus.UNKNOWN
    db.commit()
    return {
        "detail": (
            "Reset a configuración de fábrica enviado. El equipo se reiniciará y puede "
            "quedar sin ninguna IP asignada — búscalo en 'Detectados en la red' por su MAC."
        )
    }
