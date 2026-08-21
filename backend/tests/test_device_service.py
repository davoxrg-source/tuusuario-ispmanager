from contextlib import contextmanager

from app.models.mikrotik_device import MikrotikDevice
from app.services.mikrotik import device_service as device_service_module
from app.services.mikrotik.device_service import DeviceService


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
