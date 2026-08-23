from contextlib import contextmanager

from app.models.mikrotik_device import MikrotikDevice
from app.services.mikrotik import suspension
from app.services.mikrotik.device_service import DeviceService

# Reemplaza el corte por PPPoE (este despliegue no usa PPPoE -- confirmado
# migrando los 770 contratos reales desde sequreisp_production, todos con
# pppoe_active NULL). Sintaxis de /ip/firewall/filter verificada contra un
# CCR2004 real (RouterOS 7.24) antes de escribir este módulo.


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


def test_ensure_suspension_bootstrap_creates_rule_only_if_missing(monkeypatch):
    calls: list[str] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            if cmd == "/ip/firewall/filter/print":
                calls.append(cmd)
                return iter([])  # todavía no existe la regla
            if cmd == "/ip/firewall/filter/add":
                calls.append(cmd)
                assert kwargs["action"] == "drop"
                assert kwargs["src-address-list"] == suspension.SUSPENDED_ADDRESS_LIST
                return iter([])
            raise AssertionError(f"comando no esperado: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    service.ensure_suspension_bootstrap()

    assert calls == ["/ip/firewall/filter/print", "/ip/firewall/filter/add"]


def test_ensure_suspension_bootstrap_is_a_noop_if_rule_already_exists(monkeypatch):
    class FakeApi:
        def __call__(self, cmd, **kwargs):
            if cmd == "/ip/firewall/filter/print":
                return iter([{".id": "*1", "comment": suspension.FILTER_RULE_COMMENT}])
            raise AssertionError(f"no debería llamar a {cmd} si la regla ya existe")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    service.ensure_suspension_bootstrap()  # no debe lanzar ni intentar crear de nuevo


def test_suspend_client_ip_ensures_bootstrap_then_adds_to_list(monkeypatch):
    calls: list[str] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            calls.append(cmd)
            if cmd == "/ip/firewall/filter/print":
                return iter([{".id": "*1", "comment": suspension.FILTER_RULE_COMMENT}])
            if cmd == "/ip/firewall/address-list/print":
                return iter([])
            if cmd == "/ip/firewall/address-list/add":
                assert kwargs["list"] == suspension.SUSPENDED_ADDRESS_LIST
                assert kwargs["address"] == "10.0.0.5"
                return iter([])
            raise AssertionError(f"comando no esperado: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    service.suspend_client_ip("10.0.0.5")

    assert calls == [
        "/ip/firewall/filter/print",
        "/ip/firewall/address-list/print",
        "/ip/firewall/address-list/add",
    ]


def test_reactivate_client_ip_removes_from_list(monkeypatch):
    removed: list[str] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            if cmd == "/ip/firewall/address-list/print":
                return iter([{".id": "*1", "list": suspension.SUSPENDED_ADDRESS_LIST, "address": "10.0.0.5"}])
            if cmd == "/ip/firewall/address-list/remove":
                removed.append(kwargs[".id"])
                return iter([])
            raise AssertionError(f"comando no esperado: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    result = service.reactivate_client_ip("10.0.0.5")

    assert result is True
    assert removed == ["*1"]
