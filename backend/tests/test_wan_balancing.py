from contextlib import contextmanager

import pytest

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
