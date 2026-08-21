import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import decrypt_secret, encrypt_secret
from app.db.session import get_db
from app.models.client import Client, ClientStatus
from app.models.mikrotik_device import MikrotikDevice
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.services.mikrotik.device_service import DeviceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(get_current_user)])


def _get_client_or_404(db: Session, client_id: uuid.UUID) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    return client


def _device_service_for(db: Session, client: Client) -> DeviceService | None:
    if client.mikrotik_device_id is None:
        return None
    device = db.get(MikrotikDevice, client.mikrotik_device_id)
    if device is None:
        return None
    return DeviceService(device, decrypt_secret(device.encrypted_password))


@router.get("", response_model=list[ClientRead])
def list_clients(db: Session = Depends(get_db)) -> list[Client]:
    return db.query(Client).order_by(Client.full_name).all()


@router.post("", response_model=ClientRead, status_code=201)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> Client:
    data = payload.model_dump(exclude={"pppoe_password"})
    client = Client(**data)
    if payload.pppoe_password:
        client.encrypted_pppoe_password = encrypt_secret(payload.pppoe_password)
    db.add(client)
    db.commit()
    db.refresh(client)

    if client.pppoe_username and payload.pppoe_password:
        service = _device_service_for(db, client)
        if service:
            try:
                service.create_pppoe_secret(client.pppoe_username, payload.pppoe_password)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo crear el secreto PPPoE en el Mikrotik: %s", exc)

    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    return _get_client_or_404(db, client_id)


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(client_id: uuid.UUID, payload: ClientUpdate, db: Session = Depends(get_db)) -> Client:
    client = _get_client_or_404(db, client_id)
    data = payload.model_dump(exclude_unset=True)
    pppoe_password = data.pop("pppoe_password", None)
    for field, value in data.items():
        setattr(client, field, value)
    if pppoe_password:
        client.encrypted_pppoe_password = encrypt_secret(pppoe_password)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    client = _get_client_or_404(db, client_id)
    db.delete(client)
    db.commit()


@router.post("/{client_id}/suspend", response_model=ClientRead)
def suspend_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    client = _get_client_or_404(db, client_id)
    client.status = ClientStatus.SUSPENDED
    db.commit()
    db.refresh(client)

    if client.pppoe_username:
        service = _device_service_for(db, client)
        if service:
            try:
                service.set_client_enabled(client.pppoe_username, enabled=False)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo deshabilitar el secreto PPPoE en el Mikrotik: %s", exc)
    return client


@router.post("/{client_id}/reactivate", response_model=ClientRead)
def reactivate_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    client = _get_client_or_404(db, client_id)
    client.status = ClientStatus.ACTIVE
    db.commit()
    db.refresh(client)

    if client.pppoe_username:
        service = _device_service_for(db, client)
        if service:
            try:
                service.set_client_enabled(client.pppoe_username, enabled=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo habilitar el secreto PPPoE en el Mikrotik: %s", exc)
    return client
