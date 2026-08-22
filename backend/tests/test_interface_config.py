from contextlib import contextmanager

from app.models.mikrotik_device import MikrotikDevice
from app.services.mikrotik import device_service as device_service_module
from app.services.mikrotik.device_service import DeviceService


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


class RecordingApi:
    """Fake que registra cada comando/kwargs enviado, sin tocar un equipo real."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.responses: dict[str, list[dict]] = {}

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return iter(self.responses.get(cmd, []))


def _patch_api(monkeypatch, fake_api: RecordingApi):
    @contextmanager
    def fake_api_connection(**kwargs):
        yield fake_api

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)


def test_list_interfaces_returns_raw_rows(monkeypatch):
    fake_api = RecordingApi()
    fake_api.responses["/interface/print"] = [
        {".id": "*2", "name": "ether1", "type": "ether", "mtu": 1500, "mac-address": "AA:BB:CC:DD:EE:FF",
         "running": True, "disabled": False},
    ]
    _patch_api(monkeypatch, fake_api)
    service = DeviceService(_fake_device(), password="whatever")

    rows = service.list_interfaces()

    assert rows[0]["name"] == "ether1"
    assert rows[0]["mac-address"] == "AA:BB:CC:DD:EE:FF"


def test_add_ip_address_sends_correct_command(monkeypatch):
    fake_api = RecordingApi()
    _patch_api(monkeypatch, fake_api)
    service = DeviceService(_fake_device(), password="whatever")

    service.add_ip_address("ether1", "192.168.1.1/24")

    assert fake_api.calls == [("/ip/address/add", {"address": "192.168.1.1/24", "interface": "ether1"})]


def test_remove_ip_address_sends_correct_command(monkeypatch):
    fake_api = RecordingApi()
    _patch_api(monkeypatch, fake_api)
    service = DeviceService(_fake_device(), password="whatever")

    service.remove_ip_address("*5")

    assert fake_api.calls == [("/ip/address/remove", {".id": "*5"})]


def test_create_bridge_sends_correct_command(monkeypatch):
    fake_api = RecordingApi()
    _patch_api(monkeypatch, fake_api)
    service = DeviceService(_fake_device(), password="whatever")

    service.create_bridge("bridge-lan")

    assert fake_api.calls == [("/interface/bridge/add", {"name": "bridge-lan"})]


def test_add_bridge_port_sends_correct_command(monkeypatch):
    fake_api = RecordingApi()
    _patch_api(monkeypatch, fake_api)
    service = DeviceService(_fake_device(), password="whatever")

    service.add_bridge_port("bridge-lan", "ether2")

    assert fake_api.calls == [
        ("/interface/bridge/port/add", {"bridge": "bridge-lan", "interface": "ether2"})
    ]


def test_setup_pppoe_server_sends_pool_profile_and_server_in_order(monkeypatch):
    fake_api = RecordingApi()
    _patch_api(monkeypatch, fake_api)
    service = DeviceService(_fake_device(), password="whatever")

    service.setup_pppoe_server(
        interface="ether1",
        service_name="isp-pppoe",
        pool_start="10.10.10.2",
        pool_end="10.10.10.254",
        profile_name="clientes",
        local_address="10.10.10.1",
    )

    assert fake_api.calls == [
        ("/ip/pool/add", {"name": "clientes-pool", "ranges": "10.10.10.2-10.10.10.254"}),
        (
            "/ppp/profile/add",
            {"name": "clientes", "local-address": "10.10.10.1", "remote-address": "clientes-pool"},
        ),
        (
            "/interface/pppoe-server/server/add",
            {
                "interface": "ether1",
                "service-name": "isp-pppoe",
                "default-profile": "clientes",
                "disabled": "no",
            },
        ),
    ]
