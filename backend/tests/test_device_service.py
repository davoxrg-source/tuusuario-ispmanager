import time
from contextlib import contextmanager

from app.models.mikrotik_device import MikrotikDevice
from app.services.mikrotik import device_service as device_service_module
from app.services.mikrotik import discovery
from app.services.mikrotik.device_service import DeviceService
from app.services.mikrotik.discovery import DiscoveredDevice


class FakeRouterOsApi:
    """Simula las respuestas de librouteros para las rutas que usa DeviceService."""

    def __call__(self, cmd, **kwargs):
        if cmd == "/system/identity/print":
            return iter([{"name": "lab-router"}])
        if cmd == "/system/resource/print":
            return iter(
                [
                    {
                        "version": "7.15",
                        "cpu-load": "12",
                        "total-memory": "134217728",
                        "free-memory": "100000000",
                        "uptime": "1w2d3h4m5s",
                    }
                ]
            )
        if cmd == "/ppp/active/print":
            return iter([{"name": "cliente1"}, {"name": "cliente2"}])
        if cmd == "/interface/print":
            return iter(
                [
                    {"name": "ether1", "rx-byte": "1000", "tx-byte": "2000", "running": "true"},
                    {"name": "ether2", "rx-byte": "500", "tx-byte": "700", "running": "false"},
                ]
            )
        if cmd == "/ppp/secret/print":
            return iter([{".id": "*1", "name": "cliente1", "disabled": "false"}])
        raise AssertionError(f"comando no esperado en el fake: {cmd}")


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


def _patch_api_connection(monkeypatch, fake_api: FakeRouterOsApi):
    @contextmanager
    def fake_api_connection(**kwargs):
        yield fake_api

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)


def test_test_connection_success_via_api(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    _patch_api_connection(monkeypatch, FakeRouterOsApi())

    result = service.test_connection()

    assert result.success is True
    assert result.method == "api"
    assert result.identity == "lab-router"
    assert result.routeros_version == "7.15"
    assert result.uptime_seconds == 1 * 604800 + 2 * 86400 + 3 * 3600 + 4 * 60 + 5


def test_get_status_reports_active_sessions(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    _patch_api_connection(monkeypatch, FakeRouterOsApi())

    status = service.get_status()

    assert status.cpu_load_percent == 12
    assert status.active_ppp_sessions == 2
    assert status.memory_total_bytes == 134217728
    assert status.memory_used_bytes == 134217728 - 100000000


def test_get_interfaces_snapshot(monkeypatch):
    service = DeviceService(_fake_device(), password="whatever")
    _patch_api_connection(monkeypatch, FakeRouterOsApi())

    interfaces = service.get_interfaces_snapshot()

    assert interfaces == [
        {"name": "ether1", "rx_bytes": 1000, "tx_bytes": 2000, "running": True},
        {"name": "ether2", "rx_bytes": 500, "tx_bytes": 700, "running": False},
    ]


class _FakeDb:
    """db falso: solo necesitamos que .commit() no truene."""

    def commit(self) -> None:
        pass


def test_test_connection_auto_heals_ip_via_mac(monkeypatch):
    device = MikrotikDevice(
        name="Router Lab",
        host="10.0.0.1",  # IP vieja, ya no responde
        mac_address="00:0C:42:01:02:03",
        api_port=8728,
        api_use_tls=False,
        ssh_port=22,
        username="admin",
        encrypted_password="unused-in-test",
    )
    service = DeviceService(device, password="whatever")

    @contextmanager
    def fake_api_connection(**kwargs):
        if kwargs["host"] != "10.0.0.2":
            raise device_service_module.api_client.RouterOsApiError("no responde en la IP vieja")
        yield FakeRouterOsApi()

    @contextmanager
    def fake_ssh_connection(**kwargs):
        raise device_service_module.ssh_client.RouterOsSshError("ssh tampoco disponible")
        yield  # pragma: no cover - nunca se alcanza, mantiene la función como generador

    monkeypatch.setattr(device_service_module.api_client, "api_connection", fake_api_connection)
    monkeypatch.setattr(device_service_module.ssh_client, "ssh_connection", fake_ssh_connection)
    monkeypatch.setattr(
        discovery.listener,
        "get_by_mac",
        lambda mac: DiscoveredDevice(
            mac_address=mac, ip_address="10.0.0.2", identity="lab-router", seen_at=time.time()
        ),
    )

    result = service.test_connection(db=_FakeDb())

    assert result.success is True
    assert result.method == "api"
    assert result.resolved_via_mac is True
    assert result.updated_host == "10.0.0.2"
    assert device.host == "10.0.0.2"  # se persistió el cambio en el modelo


def test_test_connection_ignores_stale_mac_discovery(monkeypatch):
    device = MikrotikDevice(
        name="Router Lab",
        host="10.0.0.1",
        mac_address="00:0C:42:01:02:03",
        api_port=8728,
        api_use_tls=False,
        ssh_port=22,
        username="admin",
        encrypted_password="unused-in-test",
    )
    service = DeviceService(device, password="whatever")

    @contextmanager
    def always_fails_api(**kwargs):
        raise device_service_module.api_client.RouterOsApiError("no responde")
        yield  # pragma: no cover

    @contextmanager
    def always_fails_ssh(**kwargs):
        raise device_service_module.ssh_client.RouterOsSshError("no responde")
        yield  # pragma: no cover

    monkeypatch.setattr(device_service_module.api_client, "api_connection", always_fails_api)
    monkeypatch.setattr(device_service_module.ssh_client, "ssh_connection", always_fails_ssh)
    monkeypatch.setattr(
        discovery.listener,
        "get_by_mac",
        lambda mac: DiscoveredDevice(
            mac_address=mac,
            ip_address="10.0.0.2",
            seen_at=time.time() - 3600,  # visto hace 1h: se considera obsoleto
        ),
    )

    result = service.test_connection(db=_FakeDb())

    assert result.success is False
    assert device.host == "10.0.0.1"  # no se tocó: el dato de MNDP era viejo
