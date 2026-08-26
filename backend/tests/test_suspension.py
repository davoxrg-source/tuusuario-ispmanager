from contextlib import contextmanager

import pytest

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


def test_ensure_suspension_bootstrap_creates_all_5_rules_only_if_missing(monkeypatch):
    calls: list[str] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            calls.append(cmd)
            if cmd in ("/ip/firewall/filter/print", "/ip/firewall/nat/print"):
                return iter([])  # todavía no existe ninguna regla
            if cmd == "/ip/firewall/filter/add":
                assert "place-before" not in kwargs  # drop todavía no existe cuando se agregan
                assert kwargs["src-address-list"] == suspension.SUSPENDED_ADDRESS_LIST
                return iter([])
            if cmd == "/ip/firewall/nat/add":
                assert kwargs["src-address-list"] == suspension.SUSPENDED_ADDRESS_LIST
                assert kwargs["action"] in ("dst-nat", "masquerade")
                return iter([])
            raise AssertionError(f"comando no esperado: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    service.ensure_suspension_bootstrap(notice_server_ip="10.0.0.9")

    assert calls == [
        "/ip/firewall/filter/print",  # drop
        "/ip/firewall/filter/print",  # dns
        "/ip/firewall/filter/print",  # notice-accept
        "/ip/firewall/nat/print",  # notice dnat
        "/ip/firewall/nat/print",  # notice srcnat (hairpin)
        "/ip/firewall/filter/add",  # dns
        "/ip/firewall/filter/add",  # notice-accept
        "/ip/firewall/filter/add",  # drop
        "/ip/firewall/nat/add",  # notice dnat
        "/ip/firewall/nat/add",  # notice srcnat (hairpin)
    ]


def test_ensure_suspension_bootstrap_is_a_noop_if_all_5_rules_already_exist(monkeypatch):
    class FakeApi:
        def __call__(self, cmd, **kwargs):
            if cmd == "/ip/firewall/filter/print":
                return iter(
                    [
                        {".id": "*1", "comment": suspension.FILTER_RULE_COMMENT},
                        {".id": "*3", "comment": suspension.DNS_ACCEPT_RULE_COMMENT},
                        {".id": "*4", "comment": suspension.NOTICE_ACCEPT_RULE_COMMENT},
                    ]
                )
            if cmd == "/ip/firewall/nat/print":
                return iter(
                    [
                        {".id": "*2", "comment": suspension.NOTICE_RULE_COMMENT},
                        {".id": "*5", "comment": suspension.NOTICE_SRCNAT_RULE_COMMENT},
                    ]
                )
            raise AssertionError(f"no debería llamar a {cmd} si las 5 reglas ya existen")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    service.ensure_suspension_bootstrap()  # no debe lanzar ni intentar crear de nuevo


def test_ensure_suspension_bootstrap_without_notice_ip_raises_on_first_run(monkeypatch):
    class FakeApi:
        def __call__(self, cmd, **kwargs):
            if cmd in ("/ip/firewall/filter/print", "/ip/firewall/nat/print"):
                return iter([])
            raise AssertionError(f"no debería crear nada sin notice_server_ip en el primer bootstrap: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    with pytest.raises(ValueError):
        service.ensure_suspension_bootstrap()  # sin notice_server_ip y sin nada creado todavía


def test_ensure_suspension_bootstrap_inserts_accept_rules_before_existing_drop(monkeypatch):
    """Gotchas reales encontrados en vivo (3, en orden): (1) el drop bloqueaba
    hasta DNS, sin resolver nombre no hay conexión HTTP que redirigir; (2) el
    DNAT redirigía bien pero el drop igual tiraba el paquete ya redirigido
    porque matchea por IP de origen, no de destino; (3) con el drop y el
    accept ya resueltos, la respuesta del servidor del aviso se iba directo
    por ARP al cliente (misma red L2) en vez de volver a pasar por el
    router, así que el cliente la descartaba (hairpin NAT) -- confirmado con
    /ip/firewall/connection/print mostrando tcp-state=syn-sent para siempre.
    Los 2 accept nuevos tienen que insertarse con place-before apuntando al
    .id real del drop existente, si no nunca se evaluarían."""
    calls: list[str] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            calls.append(cmd)
            if cmd == "/ip/firewall/filter/print":
                return iter([{".id": "*1", "comment": suspension.FILTER_RULE_COMMENT}])
            if cmd == "/ip/firewall/nat/print":
                return iter(
                    [
                        {".id": "*2", "comment": suspension.NOTICE_RULE_COMMENT},
                        {".id": "*5", "comment": suspension.NOTICE_SRCNAT_RULE_COMMENT},
                    ]
                )
            if cmd == "/ip/firewall/filter/add":
                assert kwargs["action"] == "accept"
                assert kwargs["place-before"] == "*1"
                return iter([])
            raise AssertionError(f"comando no esperado: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    service.ensure_suspension_bootstrap(notice_server_ip="10.0.0.9")

    assert calls == [
        "/ip/firewall/filter/print",
        "/ip/firewall/filter/print",
        "/ip/firewall/filter/print",
        "/ip/firewall/nat/print",
        "/ip/firewall/nat/print",
        "/ip/firewall/filter/add",  # dns, con place-before
        "/ip/firewall/filter/add",  # notice-accept, con place-before
    ]


def test_ensure_suspension_bootstrap_degrades_gracefully_without_notice_ip_if_something_exists(monkeypatch):
    class FakeApi:
        def __call__(self, cmd, **kwargs):
            if cmd == "/ip/firewall/filter/print":
                return iter([{".id": "*1", "comment": suspension.FILTER_RULE_COMMENT}])
            if cmd == "/ip/firewall/nat/print":
                return iter([])  # el aviso todavía no existe
            if cmd == "/ip/firewall/filter/add":
                assert kwargs["action"] == "accept"
                assert kwargs["dst-port"] == "53"  # solo DNS -- el resto del aviso necesita la IP
                return iter([])
            raise AssertionError(f"comando no esperado sin notice_server_ip: {cmd}")

    @contextmanager
    def fake_api_connection(**kwargs):
        yield FakeApi()

    import app.services.mikrotik.device_service as device_service_module

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)

    service = DeviceService(_fake_device(), password="unused")
    service.ensure_suspension_bootstrap()  # no debe lanzar -- crea DNS, deja el resto pendiente


def test_suspend_client_ip_ensures_bootstrap_then_adds_to_list(monkeypatch):
    calls: list[str] = []

    class FakeApi:
        def __call__(self, cmd, **kwargs):
            calls.append(cmd)
            if cmd == "/ip/firewall/filter/print":
                return iter(
                    [
                        {".id": "*1", "comment": suspension.FILTER_RULE_COMMENT},
                        {".id": "*3", "comment": suspension.DNS_ACCEPT_RULE_COMMENT},
                        {".id": "*4", "comment": suspension.NOTICE_ACCEPT_RULE_COMMENT},
                    ]
                )
            if cmd == "/ip/firewall/nat/print":
                return iter(
                    [
                        {".id": "*2", "comment": suspension.NOTICE_RULE_COMMENT},
                        {".id": "*5", "comment": suspension.NOTICE_SRCNAT_RULE_COMMENT},
                    ]
                )
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
        "/ip/firewall/filter/print",
        "/ip/firewall/filter/print",
        "/ip/firewall/nat/print",
        "/ip/firewall/nat/print",
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
