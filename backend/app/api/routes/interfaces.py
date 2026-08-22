import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.security import decrypt_secret
from app.db.session import get_db
from app.models.mikrotik_device import MikrotikDevice
from app.models.plan import Plan
from app.schemas.interface import (
    BridgeCreate,
    BridgePortCreate,
    BridgePortRead,
    BridgeRead,
    InterfaceRead,
    IpAddressCreate,
    IpAddressRead,
    PppoeServerSetupRequest,
)
from app.schemas.qos import QosPlanBootstrapRequest, QosPlanBootstrapResponse
from app.schemas.wan_balancing import WanBalancingRequest, WanBalancingResponse
from app.services.mikrotik import qos
from app.services.mikrotik.device_service import DeviceService, build_wan_balancing_plan

router = APIRouter(prefix="/devices", tags=["interfaces"], dependencies=[Depends(get_current_user)])


def _service_for(db: Session, device_id: uuid.UUID) -> DeviceService:
    device = db.get(MikrotikDevice, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado.")
    password = decrypt_secret(device.encrypted_password)
    return DeviceService(device, password)


def _wrap_router_error(exc: Exception, action: str) -> HTTPException:
    return HTTPException(status_code=502, detail=f"No se pudo {action}: {exc}")


@router.get("/{device_id}/interfaces", response_model=list[InterfaceRead])
def list_interfaces(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[InterfaceRead]:
    service = _service_for(db, device_id)
    try:
        rows = service.list_interfaces()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener las interfaces")
    return [
        InterfaceRead(
            id=row.get(".id", ""),
            name=row.get("name", ""),
            type=row.get("type", ""),
            running=bool(row.get("running")),
            disabled=bool(row.get("disabled")),
            mac_address=row.get("mac-address"),
            mtu=row.get("mtu"),
        )
        for row in rows
    ]


@router.get("/{device_id}/ip-addresses", response_model=list[IpAddressRead])
def list_ip_addresses(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[IpAddressRead]:
    service = _service_for(db, device_id)
    try:
        rows = service.list_ip_addresses()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener las direcciones IP")
    return [
        IpAddressRead(
            id=row.get(".id", ""),
            address=row.get("address", ""),
            network=row.get("network"),
            interface=row.get("interface", ""),
            disabled=bool(row.get("disabled")),
        )
        for row in rows
    ]


@router.post(
    "/{device_id}/ip-addresses", status_code=201, dependencies=[Depends(require_admin)]
)
def add_ip_address(device_id: uuid.UUID, payload: IpAddressCreate, db: Session = Depends(get_db)) -> dict:
    service = _service_for(db, device_id)
    try:
        service.add_ip_address(payload.interface, payload.address)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "agregar la dirección IP")
    return {"detail": "Dirección IP agregada."}


@router.delete(
    "/{device_id}/ip-addresses/{ip_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def remove_ip_address(device_id: uuid.UUID, ip_id: str, db: Session = Depends(get_db)) -> None:
    service = _service_for(db, device_id)
    try:
        service.remove_ip_address(ip_id)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "eliminar la dirección IP")


@router.get("/{device_id}/bridges", response_model=list[BridgeRead])
def list_bridges(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[BridgeRead]:
    service = _service_for(db, device_id)
    try:
        rows = service.list_bridges()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener los bridges")
    return [
        BridgeRead(id=row.get(".id", ""), name=row.get("name", ""), disabled=bool(row.get("disabled")))
        for row in rows
    ]


@router.post("/{device_id}/bridges", status_code=201, dependencies=[Depends(require_admin)])
def create_bridge(device_id: uuid.UUID, payload: BridgeCreate, db: Session = Depends(get_db)) -> dict:
    service = _service_for(db, device_id)
    try:
        service.create_bridge(payload.name)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "crear el bridge")
    return {"detail": "Bridge creado."}


@router.delete(
    "/{device_id}/bridges/{bridge_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def remove_bridge(device_id: uuid.UUID, bridge_id: str, db: Session = Depends(get_db)) -> None:
    service = _service_for(db, device_id)
    try:
        service.remove_bridge(bridge_id)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "eliminar el bridge")


@router.get("/{device_id}/bridge-ports", response_model=list[BridgePortRead])
def list_bridge_ports(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[BridgePortRead]:
    service = _service_for(db, device_id)
    try:
        rows = service.list_bridge_ports()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener los puertos de bridge")
    return [
        BridgePortRead(id=row.get(".id", ""), interface=row.get("interface", ""), bridge=row.get("bridge", ""))
        for row in rows
    ]


@router.post(
    "/{device_id}/bridges/{bridge_name}/ports",
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def add_bridge_port(
    device_id: uuid.UUID, bridge_name: str, payload: BridgePortCreate, db: Session = Depends(get_db)
) -> dict:
    service = _service_for(db, device_id)
    try:
        service.add_bridge_port(bridge_name, payload.interface)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "agregar el puerto al bridge")
    return {"detail": "Puerto agregado al bridge."}


@router.delete(
    "/{device_id}/bridge-ports/{port_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def remove_bridge_port(device_id: uuid.UUID, port_id: str, db: Session = Depends(get_db)) -> None:
    service = _service_for(db, device_id)
    try:
        service.remove_bridge_port(port_id)
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "quitar el puerto del bridge")


@router.post("/{device_id}/pppoe-server", status_code=201, dependencies=[Depends(require_admin)])
def setup_pppoe_server(
    device_id: uuid.UUID, payload: PppoeServerSetupRequest, db: Session = Depends(get_db)
) -> dict:
    service = _service_for(db, device_id)
    try:
        service.setup_pppoe_server(
            interface=payload.interface,
            service_name=payload.service_name,
            pool_start=payload.pool_start,
            pool_end=payload.pool_end,
            profile_name=payload.profile_name,
            local_address=payload.local_address,
        )
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "configurar el servidor PPPoE")
    return {"detail": "Servidor PPPoE configurado."}


@router.get("/{device_id}/routes")
def list_routes(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    service = _service_for(db, device_id)
    try:
        return service.list_routes()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener las rutas")


@router.get("/{device_id}/mangle-rules")
def list_mangle_rules(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    service = _service_for(db, device_id)
    try:
        return service.list_mangle_rules()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener las reglas de mangle")


@router.get("/{device_id}/nat-rules")
def list_nat_rules(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    service = _service_for(db, device_id)
    try:
        return service.list_nat_rules()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener las reglas NAT")


@router.get("/{device_id}/dhcp-clients")
def list_dhcp_clients(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    service = _service_for(db, device_id)
    try:
        return service.list_dhcp_clients()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener los clientes DHCP")


@router.get("/{device_id}/pppoe-clients")
def list_pppoe_clients(device_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    service = _service_for(db, device_id)
    try:
        return service.list_pppoe_clients()
    except Exception as exc:  # noqa: BLE001
        raise _wrap_router_error(exc, "obtener los clientes PPPoE")


@router.post(
    "/{device_id}/wan-balancing/preview",
    response_model=WanBalancingResponse,
    dependencies=[Depends(require_admin)],
)
def preview_wan_balancing(
    device_id: uuid.UUID, payload: WanBalancingRequest, db: Session = Depends(get_db)
) -> WanBalancingResponse:
    # No necesita conexión al equipo: solo arma la lista de comandos.
    _service_for(db, device_id)
    try:
        plan = build_wan_balancing_plan(payload.lan_interface, payload.wans, payload.public_blocks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return WanBalancingResponse(commands=plan, applied=False)


@router.post(
    "/{device_id}/wan-balancing/apply",
    response_model=WanBalancingResponse,
    dependencies=[Depends(require_admin)],
)
def apply_wan_balancing(
    device_id: uuid.UUID, payload: WanBalancingRequest, db: Session = Depends(get_db)
) -> WanBalancingResponse:
    """Ejecuta de verdad el plan de balanceo/failover. El frontend solo debe
    llamar a este endpoint después de mostrarle al usuario el resultado de
    /wan-balancing/preview con los mismos datos — esta acción puede tumbar
    la salida a internet del equipo si algo está mal configurado."""
    service = _service_for(db, device_id)
    try:
        plan = build_wan_balancing_plan(payload.lan_interface, payload.wans, payload.public_blocks)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    results = service.apply_wan_balancing_plan(plan, dry_run=False)
    all_ok = all(r.executed for r in results) and len(results) == len(plan)
    return WanBalancingResponse(commands=results, applied=all_ok)


def _plan_or_404(db: Session, plan_id: uuid.UUID) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    return plan


def _build_plan_bootstrap(db: Session, plan_id: uuid.UUID, payload: QosPlanBootstrapRequest):
    plan = _plan_or_404(db, plan_id)
    return qos.build_plan_bootstrap_plan(
        plan,
        lan_interface=payload.lan_interface,
        wan_interface=payload.wan_interface,
        priority_tcp_ports=payload.priority_tcp_ports or None,
        priority_udp_ports=payload.priority_udp_ports or None,
        realtime_tcp_max_size=payload.realtime_tcp_max_size,
        realtime_udp_max_size=payload.realtime_udp_max_size,
    )


@router.post(
    "/{device_id}/qos-plans/{plan_id}/preview",
    response_model=QosPlanBootstrapResponse,
)
def preview_qos_plan_bootstrap(
    device_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: QosPlanBootstrapRequest,
    db: Session = Depends(get_db),
) -> QosPlanBootstrapResponse:
    """Arma (sin ejecutar nada) toda la infraestructura QoS de UN plan:
    address-list + PCQ + mangle + queue tree. Se aplica UNA VEZ por plan por
    equipo, sin importar cuántos clientes tenga — después, cada cliente se
    aprovisiona con POST /clients/{id}/qos/provision (una sola llamada, no
    crea ningún objeto nuevo). Ver services/mikrotik/qos.py."""
    _service_for(db, device_id)
    plan = _build_plan_bootstrap(db, plan_id, payload)
    return QosPlanBootstrapResponse(commands=plan, applied=False)


@router.post(
    "/{device_id}/qos-plans/{plan_id}/apply",
    response_model=QosPlanBootstrapResponse,
    dependencies=[Depends(require_admin)],
)
def apply_qos_plan_bootstrap(
    device_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: QosPlanBootstrapRequest,
    db: Session = Depends(get_db),
) -> QosPlanBootstrapResponse:
    service = _service_for(db, device_id)
    plan = _build_plan_bootstrap(db, plan_id, payload)
    results = service.apply_command_plan(plan, dry_run=False)
    all_ok = all(r.executed for r in results) and len(results) == len(plan)
    return QosPlanBootstrapResponse(commands=results, applied=all_ok)


@router.delete(
    "/{device_id}/qos-plans/{plan_id}",
    status_code=204,
    dependencies=[Depends(require_admin)],
)
def remove_qos_plan_bootstrap(
    device_id: uuid.UUID, plan_id: uuid.UUID, db: Session = Depends(get_db)
) -> None:
    """Desmonta toda la infraestructura QoS del plan (queue tree, PCQ,
    address-list) — ej. antes de rearmarla con otros parámetros."""
    service = _service_for(db, device_id)
    plan = _plan_or_404(db, plan_id)
    service.remove_plan_qos(plan)
