from contextlib import contextmanager

from app.models.mikrotik_device import MikrotikDevice
from app.services.mikrotik import device_service as device_service_module
from app.services.mikrotik.device_service import DeviceService


class RecordingApi:
    """Simula /interface/ethernet, /ip/route y /ip/firewall/nat para probar
    provision_client_public_ip / remove_client_public_ip sin un equipo real."""

    def __init__(self, arp_mode: str = "enabled", masquerade_rule_id: str | None = "*10"):
        self.calls: list[tuple[str, dict]] = []
        self.arp_mode = arp_mode
        self.masquerade_rule_id = masquerade_rule_id

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        if cmd == "/interface/ethernet/print":
            return iter([{".id": "*1", "name": "eth10", "arp": self.arp_mode}])
        if cmd == "/ip/firewall/nat/print":
            if self.masquerade_rule_id:
                return iter(
                    [{".id": self.masquerade_rule_id, "action": "masquerade", "out-interface": "eth10"}]
                )
            return iter([])
        if cmd == "/ip/route/print":
            return iter([{".id": "*5", "dst-address": "190.71.83.43/32"}])
        return iter([])

    def calls_for(self, cmd: str) -> list[dict]:
        return [kwargs for c, kwargs in self.calls if c == cmd]


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


def _patch_api_connection(monkeypatch, fake_api: RecordingApi):
    @contextmanager
    def fake_api_connection(**kwargs):
        yield fake_api

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)


def test_provision_enables_proxy_arp_when_not_already_set(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    fake = RecordingApi(arp_mode="enabled")
    _patch_api_connection(monkeypatch, fake)

    service.provision_client_public_ip("190.71.83.43", "eth10", "eth0")

    set_calls = fake.calls_for("/interface/ethernet/set")
    assert set_calls == [{".id": "*1", "arp": "proxy-arp"}]


def test_provision_skips_set_when_already_proxy_arp(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    fake = RecordingApi(arp_mode="proxy-arp")
    _patch_api_connection(monkeypatch, fake)

    service.provision_client_public_ip("190.71.83.43", "eth10", "eth0")

    assert fake.calls_for("/interface/ethernet/set") == []


def test_provision_adds_route_to_the_lan_interface(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    fake = RecordingApi()
    _patch_api_connection(monkeypatch, fake)

    service.provision_client_public_ip("190.71.83.43", "eth10", "eth0")

    assert fake.calls_for("/ip/route/add") == [{"dst-address": "190.71.83.43/32", "gateway": "eth0"}]


def test_provision_inserts_nat_accept_before_existing_masquerade(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    fake = RecordingApi(masquerade_rule_id="*10")
    _patch_api_connection(monkeypatch, fake)

    service.provision_client_public_ip("190.71.83.43", "eth10", "eth0")

    assert fake.calls_for("/ip/firewall/nat/add") == [
        {"chain": "srcnat", "action": "accept", "src-address": "190.71.83.43/32", "place-before": "*10"}
    ]


def test_provision_nat_accept_has_no_place_before_without_masquerade(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    fake = RecordingApi(masquerade_rule_id=None)
    _patch_api_connection(monkeypatch, fake)

    service.provision_client_public_ip("190.71.83.43", "eth10", "eth0")

    assert fake.calls_for("/ip/firewall/nat/add") == [
        {"chain": "srcnat", "action": "accept", "src-address": "190.71.83.43/32"}
    ]


def test_remove_deletes_route_but_leaves_proxy_arp_alone(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    fake = RecordingApi()
    _patch_api_connection(monkeypatch, fake)

    service.remove_client_public_ip("190.71.83.43")

    assert fake.calls_for("/ip/route/remove") == [{".id": "*5"}]
    # nunca toca arp=proxy-arp de la interfaz al retirar un cliente -- otros
    # clientes pueden estar usando el mismo bloque/proveedor.
    assert fake.calls_for("/interface/ethernet/set") == []


def test_remove_finds_nat_rule_by_bare_ip_without_slash_32(monkeypatch):
    """RouterOS normaliza 'x.x.x.x/32' a 'x.x.x.x' en src-address de una
    regla NAT (a diferencia de una ruta, que sí conserva el '/32') --
    verificado contra un CCR2004 real. remove_client_public_ip debe buscar
    por la IP sin máscara, no por '<ip>/32'."""
    service = DeviceService(_fake_device(), password="whatever")

    class SimpleNatApi:
        def __init__(self):
            self.calls: list[tuple[str, dict]] = []

        def __call__(self, cmd, **kwargs):
            self.calls.append((cmd, kwargs))
            if cmd == "/ip/firewall/nat/print":
                return iter([{".id": "*20", "action": "accept", "src-address": "190.71.83.43"}])
            if cmd == "/ip/route/print":
                return iter([])
            return iter([])

        def calls_for(self, cmd: str) -> list[dict]:
            return [kwargs for c, kwargs in self.calls if c == cmd]

    fake = SimpleNatApi()
    _patch_api_connection(monkeypatch, fake)

    service.remove_client_public_ip("190.71.83.43")

    assert fake.calls_for("/ip/firewall/nat/remove") == [{".id": "*20"}]
