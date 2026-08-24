import logging

from sqlalchemy.orm import Session

from app.core.security import decrypt_secret
from app.models.client import Client, ClientStatus
from app.models.mikrotik_device import MikrotikDevice
from app.services.mikrotik.device_service import DeviceService

logger = logging.getLogger(__name__)


def _device_service_for(db: Session, client: Client) -> DeviceService | None:
    if client.mikrotik_device_id is None:
        return None
    device = db.get(MikrotikDevice, client.mikrotik_device_id)
    if device is None:
        return None
    return DeviceService(device, decrypt_secret(device.encrypted_password))


def suspend_client_service(db: Session, client: Client) -> Client:
    """Corta el tráfico del cliente agregando su IP al address-list de
    bloqueo (ver services/mikrotik/suspension.py) -- la regla de firewall se
    crea sola la primera vez que hace falta, no requiere un paso aparte.
    Compartida entre POST /clients/{id}/suspend, las acciones masivas, y el
    corte automático por mora."""
    client.status = ClientStatus.SUSPENDED
    db.commit()
    db.refresh(client)

    if client.ip_address:
        service = _device_service_for(db, client)
        if service:
            try:
                service.suspend_client_ip(client.ip_address)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo bloquear al cliente %s en el Mikrotik: %s", client.id, exc)
    return client


def reactivate_client_service(db: Session, client: Client) -> Client:
    """Compartida entre POST /clients/{id}/reactivate, las acciones
    masivas, y la reactivación automática al pagar (ver pay_invoice)."""
    client.status = ClientStatus.ACTIVE
    db.commit()
    db.refresh(client)

    if client.ip_address:
        service = _device_service_for(db, client)
        if service:
            try:
                service.reactivate_client_ip(client.ip_address)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo reactivar al cliente %s en el Mikrotik: %s", client.id, exc)
    return client
