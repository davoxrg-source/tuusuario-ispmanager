import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.client import Client, ClientStatus
from app.models.mikrotik_device import MikrotikDevice
from app.models.plan import Plan
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


def _sync_client_qos(
    db: Session,
    client: Client,
    old_plan_id: uuid.UUID | None,
    old_ip: str | None,
    old_device_id: uuid.UUID | None,
) -> None:
    """Deja el QoS del cliente al día con lo que quedó guardado: lo saca del
    address-list de su plan/equipo/IP anterior si algo de eso cambió, y
    siempre lo asegura en el del actual (idempotente -- no crea nada nuevo
    si ya estaba). Se llama en cada alta y cada edición, no solo cuando
    cambia algo puntual: así "guardar cliente" siempre deja el QoS
    aplicado, sin necesitar un botón aparte para eso."""
    target_changed = (
        client.plan_id != old_plan_id
        or client.ip_address != old_ip
        or client.mikrotik_device_id != old_device_id
    )
    if target_changed and old_plan_id and old_ip and old_device_id:
        old_device = db.get(MikrotikDevice, old_device_id)
        old_plan = db.get(Plan, old_plan_id)
        if old_device and old_plan:
            try:
                old_service = DeviceService(old_device, decrypt_secret(old_device.encrypted_password))
                old_service.remove_client_qos_ip(old_plan, old_ip)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo sacar al cliente %s del QoS anterior: %s", client.id, exc)

    if client.plan_id and client.ip_address and client.mikrotik_device_id:
        service = _device_service_for(db, client)
        plan = db.get(Plan, client.plan_id)
        if service and plan:
            try:
                service.provision_client_qos_ip(plan, client.ip_address)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo aplicar el QoS al cliente %s: %s", client.id, exc)


def _sync_client_public_ip(
    db: Session,
    client: Client,
    old_public_ip: str | None,
    old_provider_iface: str | None,
    old_lan_iface: str | None,
    old_device_id: uuid.UUID | None,
) -> None:
    """Mismo criterio que _sync_client_qos: deja la entrega de IP pública
    por proxy-ARP al día con lo guardado -- retira la anterior si algo
    cambió, aplica la actual si están los 3 campos + equipo. No toca
    arp=proxy-arp de la interfaz del proveedor al retirar (puede haber
    otros clientes usándola, ver DeviceService.remove_client_public_ip)."""
    target_changed = (
        client.public_ip_address != old_public_ip
        or client.public_ip_provider_interface != old_provider_iface
        or client.public_ip_lan_interface != old_lan_iface
        or client.mikrotik_device_id != old_device_id
    )
    if target_changed and old_public_ip and old_device_id:
        old_device = db.get(MikrotikDevice, old_device_id)
        if old_device:
            try:
                old_service = DeviceService(old_device, decrypt_secret(old_device.encrypted_password))
                old_service.remove_client_public_ip(old_public_ip)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo retirar la IP pública anterior del cliente %s: %s", client.id, exc)

    if client.public_ip_address and client.public_ip_provider_interface and client.public_ip_lan_interface:
        service = _device_service_for(db, client)
        if service:
            try:
                service.provision_client_public_ip(
                    client.public_ip_address,
                    client.public_ip_provider_interface,
                    client.public_ip_lan_interface,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo aplicar la IP pública al cliente %s: %s", client.id, exc)


@router.post("", response_model=ClientRead, status_code=201)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> Client:
    client = Client(**payload.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    _sync_client_qos(db, client, old_plan_id=None, old_ip=None, old_device_id=None)
    _sync_client_public_ip(
        db, client, old_public_ip=None, old_provider_iface=None, old_lan_iface=None, old_device_id=None
    )
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    return _get_client_or_404(db, client_id)


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(client_id: uuid.UUID, payload: ClientUpdate, db: Session = Depends(get_db)) -> Client:
    """Guardar un cliente siempre deja su QoS al día (ver _sync_client_qos):
    si cambió plan/IP/equipo, lo saca de la lista vieja y lo pone en la
    nueva; si no cambió nada de eso, igual se asegura de que esté
    provisionado (por si nunca lo estuvo). Sin esto, cambiar de plan dejaba
    la IP en las DOS listas -- y como las reglas mangle del plan viejo se
    crearon primero, seguían ganando y el cliente quedaba shapeado con la
    velocidad anterior (bug real, visto en producción antes de este fix)."""
    client = _get_client_or_404(db, client_id)
    old_plan_id, old_ip, old_device_id = client.plan_id, client.ip_address, client.mikrotik_device_id
    old_public_ip = client.public_ip_address
    old_provider_iface = client.public_ip_provider_interface
    old_lan_iface = client.public_ip_lan_interface

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)

    _sync_client_qos(db, client, old_plan_id, old_ip, old_device_id)
    _sync_client_public_ip(db, client, old_public_ip, old_provider_iface, old_lan_iface, old_device_id)
    return client


@router.delete("/{client_id}", status_code=204)
def delete_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    client = _get_client_or_404(db, client_id)
    db.delete(client)
    db.commit()


@router.post("/{client_id}/suspend", response_model=ClientRead)
def suspend_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    """Corta el tráfico del cliente agregando su IP al address-list de
    bloqueo (ver services/mikrotik/suspension.py) — la regla de firewall se
    crea sola la primera vez que hace falta, no requiere un paso aparte."""
    client = _get_client_or_404(db, client_id)
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


@router.post("/{client_id}/reactivate", response_model=ClientRead)
def reactivate_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    client = _get_client_or_404(db, client_id)
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


def _wrap_router_error(exc: Exception, action: str) -> HTTPException:
    return HTTPException(status_code=502, detail=f"No se pudo {action}: {exc}")


def _client_plan_and_ip(db: Session, client: Client) -> tuple[Plan, str]:
    if not client.ip_address:
        raise HTTPException(status_code=400, detail="El cliente no tiene IP asignada.")
    if client.plan_id is None:
        raise HTTPException(status_code=400, detail="El cliente no tiene plan asignado.")
    plan = db.get(Plan, client.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    return plan, client.ip_address


@router.post(
    "/{client_id}/qos/provision",
    response_model=ClientRead,
    dependencies=[Depends(require_admin)],
)
def provision_client_qos(client_id: uuid.UUID, db: Session = Depends(get_db)) -> Client:
    """Agrega la IP del cliente al address-list de su plan — es lo único
    que hace falta para que empiece a recibir shaping. Requiere que el plan
    ya tenga su infraestructura QoS aplicada (ver
    /devices/{id}/qos-plans/{plan_id}/apply en interfaces.py); si no, el
    cliente queda en la lista pero sin ninguna cola que lo esté mirando."""
    client = _get_client_or_404(db, client_id)
    plan, client_ip = _client_plan_and_ip(db, client)
    service = _device_service_for(db, client)
    if service is None:
        raise HTTPException(status_code=400, detail="El cliente no tiene equipo Mikrotik asignado.")
    try:
        service.provision_client_qos_ip(plan, client_ip)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "aplicar el QoS")
    return client


@router.delete("/{client_id}/qos", status_code=204, dependencies=[Depends(require_admin)])
def remove_client_qos(client_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    """Saca la IP del cliente del address-list de su plan actual (ej. antes
    de cambiarlo de plan, de IP, o al dar de baja el contrato)."""
    client = _get_client_or_404(db, client_id)
    plan, client_ip = _client_plan_and_ip(db, client)
    service = _device_service_for(db, client)
    if service is None:
        raise HTTPException(status_code=400, detail="El cliente no tiene equipo Mikrotik asignado.")
    try:
        service.remove_client_qos_ip(plan, client_ip)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "quitar el QoS")
