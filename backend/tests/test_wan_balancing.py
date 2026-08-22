from contextlib import contextmanager

import pytest
from pydantic import ValidationError

from app.models.mikrotik_device import MikrotikDevice
from app.schemas.wan_balancing import PublicBlockPin, WanLinkInput
from app.services.mikrotik import device_service as device_service_module
from app.services.mikrotik.device_service import DeviceService, build_wan_balancing_plan


def _fake_device() -> MikrotikDevice:
    return MikrotikDevice(
        name="Router Lab",
        host="10.0.0.1",
        api_port=8728,
        api_use_tls=False,
        ssh_port=22,
        username="admin",
        encrypted_password="unused-in-test",
    )


def test_build_plan_requires_at_least_two_wans():
    with pytest.raises(ValueError):
        build_wan_balancing_plan("bridge-lan", [WanLinkInput(interface="ether1", gateway="1.1.1.1")])


def test_build_plan_rejects_public_block_pointing_to_unknown_wan():
    wans = [
        WanLinkInput(interface="ether1", gateway="1.1.1.1"),
        WanLinkInput(interface="ether2", gateway="2.2.2.2"),
    ]
    with pytest.raises(ValueError):
        build_wan_balancing_plan(
            "bridge-lan", wans, [PublicBlockPin(cidr="203.0.113.0/28", wan_interface="ether3")]
        )


def test_build_plan_order_and_content_two_wans_with_public_block():
    wans = [
        WanLinkInput(interface="ether1", gateway="10.10.1.1", distance=1),
        WanLinkInput(interface="ether2", gateway="10.10.2.1", distance=2),
    ]
    public_blocks = [PublicBlockPin(cidr="203.0.113.0/28", wan_interface="ether1")]

    plan = build_wan_balancing_plan("bridge-lan", wans, public_blocks)
    paths = [c.path for c in plan]

    # 2 tablas de ruteo, luego 1 regla de bloque público, luego 2x2 reglas PCC,
    # luego 2 rutas con routing-table, luego 2 rutas de tabla principal, luego 2 NAT.
    assert paths == [
        "/routing/table/add",
        "/routing/table/add",
        "/ip/firewall/mangle/add",  # bloque público fijo
        "/ip/firewall/mangle/add",  # PCC mark-connection ether1
        "/ip/firewall/mangle/add",  # PCC mark-routing ether1
        "/ip/firewall/mangle/add",  # PCC mark-connection ether2
        "/ip/firewall/mangle/add",  # PCC mark-routing ether2
        "/ip/route/add",  # ruta tabla to-ether1
        "/ip/route/add",  # ruta tabla to-ether2
        "/ip/route/add",  # ruta principal ether1
        "/ip/route/add",  # ruta principal ether2
        "/ip/firewall/nat/add",
        "/ip/firewall/nat/add",
    ]

    # El bloque público debe ir ANTES de las reglas PCC (para no entrar al hash).
    public_pin_index = paths.index("/ip/firewall/mangle/add")
    assert plan[public_pin_index].params["src-address"] == "203.0.113.0/28"
    assert plan[public_pin_index].params["new-routing-mark"] == "to-ether1"

    # Las tablas de ruteo se crean antes que cualquier cosa que las referencie.
    table_names = {plan[0].params["name"], plan[1].params["name"]}
    assert table_names == {"to-ether1", "to-ether2"}

    # La ruta de la tabla marcada usa routing-table, no un campo viejo tipo routing-mark.
    marked_route = next(c for c in plan if c.path == "/ip/route/add" and "routing-table" in c.params)
    assert marked_route.params["routing-table"] in ("to-ether1", "to-ether2")
    assert marked_route.params["check-gateway"] == "ping"

    # Ninguno de los comandos quedó "ejecutado" solo por construirse.
    assert all(not c.executed and c.error is None for c in plan)


def test_apply_wan_balancing_plan_dry_run_never_calls_api(monkeypatch):
    wans = [
        WanLinkInput(interface="ether1", gateway="10.10.1.1"),
        WanLinkInput(interface="ether2", gateway="10.10.2.1"),
    ]
    plan = build_wan_balancing_plan("bridge-lan", wans)

    def fail_if_called(**kwargs):
        raise AssertionError("dry_run=True no debe abrir conexión al equipo")

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fail_if_called)

    service = DeviceService(_fake_device(), password="whatever")
    results = service.apply_wan_balancing_plan(plan, dry_run=True)

    assert len(results) == len(plan)
    assert all(not r.executed for r in results)


def test_apply_wan_balancing_plan_stops_at_first_error(monkeypatch):
    wans = [
        WanLinkInput(interface="ether1", gateway="10.10.1.1"),
        WanLinkInput(interface="ether2", gateway="10.10.2.1"),
    ]
    plan = build_wan_balancing_plan("bridge-lan", wans)

    call_count = {"n": 0}

    class FailingApi:
        def __call__(self, cmd, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("falla simulada en el segundo comando")
            return iter([])

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FailingApi()

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="whatever")
    results = service.apply_wan_balancing_plan(plan, dry_run=False)

    assert len(results) == 2  # se detuvo justo después del error
    assert results[0].executed is True
    assert results[1].executed is False
    assert "falla simulada" in results[1].error


def test_wan_link_static_without_gateway_is_rejected():
    with pytest.raises(ValidationError):
        WanLinkInput(interface="ether1", connection_type="static")


def test_wan_link_pppoe_without_credentials_is_rejected():
    with pytest.raises(ValidationError):
        WanLinkInput(interface="ether1", connection_type="pppoe")


def test_wan_link_dhcp_needs_no_gateway():
    # No debe fallar: DHCP no requiere gateway ni credenciales.
    wan = WanLinkInput(interface="ether1", connection_type="dhcp")
    assert wan.gateway is None


def test_build_plan_mixed_connection_types():
    wans = [
        WanLinkInput(interface="ether1", connection_type="static", gateway="10.10.1.1", distance=1),
        WanLinkInput(interface="ether2", connection_type="dhcp", distance=2),
        WanLinkInput(
            interface="ether3",
            connection_type="pppoe",
            pppoe_username="isp_user",
            pppoe_password="isp_pass",
            distance=3,
        ),
    ]

    plan = build_wan_balancing_plan("bridge-lan", wans)
    paths = [c.path for c in plan]

    # Aprovisionamiento: 1 IP estática (ether1 no tiene 'address' así que no
    # genera comando), 1 dhcp-client, 1 pppoe-client.
    assert "/ip/dhcp-client/add" in paths
    assert "/interface/pppoe-client/add" in paths

    dhcp_cmd = next(c for c in plan if c.path == "/ip/dhcp-client/add")
    assert dhcp_cmd.params["interface"] == "ether2"
    assert dhcp_cmd.params["default-route-tables"] == "to-ether2,main"

    pppoe_cmd = next(c for c in plan if c.path == "/interface/pppoe-client/add")
    assert pppoe_cmd.params["name"] == "pppoe-ether3"
    assert pppoe_cmd.params["user"] == "isp_user"
    assert pppoe_cmd.params["add-default-route"] == "no"

    # Rutas de tabla marcada: solo ether1 (static) y ether3 (pppoe), NO ether2 (dhcp).
    marked_routes = [c for c in plan if c.path == "/ip/route/add" and "routing-table" in c.params]
    marked_interfaces_gateways = {c.params["gateway"] for c in marked_routes}
    assert marked_interfaces_gateways == {"10.10.1.1", "pppoe-ether3"}

    # La ruta PPPoE no debe llevar check-gateway=ping (es un enlace punto a punto).
    pppoe_route = next(c for c in marked_routes if c.params["gateway"] == "pppoe-ether3")
    assert "check-gateway" not in pppoe_route.params

    # La ruta static sí debe llevar check-gateway=ping.
    static_route = next(c for c in marked_routes if c.params["gateway"] == "10.10.1.1")
    assert static_route.params["check-gateway"] == "ping"

    # Rutas de tabla principal: mismo criterio, sin ether2.
    main_routes = [
        c for c in plan if c.path == "/ip/route/add" and "routing-table" not in c.params
    ]
    assert {c.params["gateway"] for c in main_routes} == {"10.10.1.1", "pppoe-ether3"}

    # NAT: las 3 WAN, sin importar el tipo de conexión.
    nat_out_interfaces = {c.params["out-interface"] for c in plan if c.path == "/ip/firewall/nat/add"}
    assert nat_out_interfaces == {"ether1", "ether2", "ether3"}


def test_build_plan_static_wan_provisions_ip_when_address_given():
    wans = [
        WanLinkInput(
            interface="ether1", connection_type="static", gateway="10.10.1.1", address="10.10.1.2/30"
        ),
        WanLinkInput(interface="ether2", connection_type="dhcp"),
    ]

    plan = build_wan_balancing_plan("bridge-lan", wans)
    ip_commands = [c for c in plan if c.path == "/ip/address/add"]

    assert len(ip_commands) == 1
    assert ip_commands[0].params == {"address": "10.10.1.2/30", "interface": "ether1"}
